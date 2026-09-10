import json
import os

import pandas as pd
from flask import Blueprint, session, render_template, g, jsonify, current_app, request
from flask_login import login_required, current_user
from sqlalchemy import text

from .utils.mail import send_mail
from .utils.request_artifacts import ledger_records
from .utils.submissions import (
    change_date, drop_snapshots, history_batches, read_state, request_directory,
    request_lock, validate_table, write_state,
)
from .utils.workbooks import REPORT_INDEX, report_index, report_sheets


finalize = Blueprint('finalize', __name__)


def validate_artifacts(change_id, tables):
    directory = request_directory(change_id)
    counts = {}
    with pd.ExcelFile(directory / 'comparison.xlsx') as workbook:
        index = pd.read_excel(workbook, sheet_name=REPORT_INDEX).to_dict('records')
        if index != report_index(tables):
            raise ValueError('The comparison workbook index does not match this request.')
        for table, sheets in report_sheets(tables).items():
            counts[table] = sum(len(pd.read_excel(workbook, sheet_name=sheets[kind]))
                                for kind in ('Modified', 'Added', 'Deleted'))
    archived = dict.fromkeys(tables, 0)
    for record in ledger_records(change_id):
        if record['tablename'] not in archived:
            raise ValueError('The record archive contains an unexpected table.')
        archived[record['tablename']] += 1
        original = json.loads(record['original_record'])
        modified = json.loads(record['modified_record'])
        if not isinstance(original, dict) and original != []:
            raise ValueError('Invalid original record archive.')
        if not isinstance(modified, dict) and modified != []:
            raise ValueError('Invalid modified record archive.')
    if counts != archived or not sum(archived.values()):
        raise ValueError('The record archive does not match the comparison workbook.')
    if not (directory / 'request.sql').is_file():
        raise ValueError('The staff SQL file is missing.')
    return sum(archived.values())


def save_history(eng, change_id, request_type, comment, expected_count):
    history = validate_table(eng, os.environ['CHANGE_HISTORY_TABLE'])
    statement = text(f'''
        INSERT INTO {history} (
            original_record, modified_record, change_id, submissionid, login_fields,
            requesting_agency, requesting_person, change_date, change_comment,
            change_processed, tablename, request_type
        ) VALUES (
            CAST(:original_record AS json), CAST(:modified_record AS json), :change_id, :submissionid,
            CAST(:login_fields AS json), :requesting_agency, :requesting_person, :change_date,
            :change_comment, :change_processed, :tablename, :request_type
        )
    ''')
    common = {
        'change_id': int(change_id), 'submissionid': int(session['submissionid']),
        'login_fields': json.dumps(session['login_fields']),
        'requesting_agency': current_user.organization, 'requesting_person': current_user.email,
        'change_date': change_date(change_id), 'change_comment': comment,
        'change_processed': 'No', 'request_type': request_type,
    }
    with eng.begin() as connection:
        connection.execute(text('SELECT pg_advisory_xact_lock(:change_id)'), {'change_id': int(change_id)})
        existing = connection.execute(text(
            f'SELECT count(*) FROM {history} WHERE change_id = :change_id'
        ), {'change_id': int(change_id)}).scalar()
        if existing:
            if existing != expected_count:
                raise ValueError('The existing change history count differs from this request. Contact SCCWRP.')
            return
        records = (dict(common, **record) for record in ledger_records(change_id))
        for batch in history_batches(records):
            connection.execute(statement, batch)


@finalize.route('/final_submit', methods=['POST'])
@login_required
def savechanges():
    if not session.get('sessionid') or not session.get('tables'):
        return jsonify(message='Your session expired. Select the submission again.'), 400
    if current_user.email_confirmed != 'yes' or current_user.is_authorized != 'yes':
        return jsonify(message='Your account is not approved for change requests.'), 403
    organization_field = current_app.user_management['organization_login_field']
    organization = session['login_fields'].get(organization_field, session['login_fields'].get('dataprovider'))
    if current_user.is_admin != 'yes' and current_user.organization != organization:
        return jsonify(message='You are not authorized for this submission.'), 403
    change_id = session['sessionid']
    with request_lock(change_id):
        state = read_state(change_id)
        if not state.get('ready'):
            return jsonify(message='Compare a valid workbook or prepare a deletion request before finalizing.'), 400
        if str(request.form.get('revision')) != str(state.get('revision')):
            return jsonify(message='This report is out of date. Review the submission again.'), 409
        comment = request.form.get('comment', '').strip()
        if not comment:
            return jsonify(message='A non-empty comment is required.'), 400
        request_type = state['request_type']
        if request_type == 'delete' and request.form.get('confirmation', '').strip() != str(session['submissionid']):
            return jsonify(message='Type the exact submission ID to confirm deletion.'), 400
        try:
            count = validate_artifacts(change_id, session['tables'])
            if not state.get('submitted'):
                state['comment'] = comment
                write_state(change_id, state)
                save_history(g.eng, change_id, request_type, comment, count)
                state['submitted'] = True
                write_state(change_id, state)
            directory = request_directory(change_id)
            label = 'Submission Deletion Request' if request_type == 'delete' else 'Submission Edit Request'
            body = (
                f'{label} from {current_user.email}\n\nDatatype: {session["dtype"]}\n'
                f'Original Submission Date: {session["submissiondate"]}\nSubmission ID: {session["submissionid"]}\n'
                f'Change ID: {change_id}\nTables: {", ".join(session["tables"])}\n'
                f'Affected records: {count}\nComment: {state["comment"]}\n\n'
                'This records a request only. SCCWRP staff must review and run the SQL before production data changes.'
            )
            if not state.get('staff_notified'):
                send_mail(current_app.send_from, current_app.maintainers,
                          f'{label} for {current_app.config["projectname"]}', body,
                          files=[str(directory / 'comparison.xlsx'), str(directory / 'request.sql')],
                          server=current_app.config['MAIL_SERVER'])
                state['staff_notified'] = True
                write_state(change_id, state)
            if not state.get('requester_notified'):
                send_mail(current_app.send_from, [current_user.email],
                          f'{label} for {current_app.config["projectname"]}', body,
                          files=[str(directory / 'comparison.xlsx')], server=current_app.config['MAIL_SERVER'])
                state['requester_notified'] = True
                write_state(change_id, state)
            drop_snapshots(g.eng, session['tables'], change_id)
            return render_template(
                'thankyou.jinja2', success=True, datatype=session['dtype'], session_user_email=current_user.email,
                submissiondate=session['submissiondate'], submissionid=session['submissionid'],
                login_fields=session['login_fields'], change_id=change_id, request_type=request_type,
            )
        except Exception:
            current_app.logger.exception('Finalization failed for change %s', change_id)
            return jsonify(message='Finalization could not finish. Retry this request; any recorded history will not be duplicated. Contact SCCWRP if the problem persists.'), 500