import os

import pandas as pd
from flask import Blueprint, request, redirect, url_for, jsonify, session, render_template, current_app, g
from flask_login import login_required, current_user

from .utils.login import get_login_field, get_submission_ids
from .utils.db import get_primary_key
from .utils.submissions import (
    allocate_request, change_date, create_snapshots, drop_snapshots, pending_deletion,
    read_snapshot, request_directory, request_lock, submission_tables, table_metadata, write_state,
)


login = Blueprint('login', __name__)


@login.route('/')
@login_required
def index():
    if session.get('tables') and session.get('sessionid'):
        with request_lock(session['sessionid']):
            drop_snapshots(g.eng, session['tables'], session['sessionid'])
    for key in ('tables', 'sessionid', 'submissionid', 'submissiondate', 'dtype', 'login_fields',
                'tablename', 'origin_tablename', 'modified_tablename', 'column_order',
                'submission_colnames', 'original_data_filepath', 'original_data_sql',
                'comparison_path', 'sql_filepath', 'comment'):
        session.pop(key, None)
    return render_template('index.jinja2', dtypes=current_app.dtypes)


@login.route('/edit-submission')
@login_required
def edit_data():
    if not session.get('tables'):
        return redirect(url_for('login.index'))
    pkeys = {table: get_primary_key(table, g.eng) for table in session['tables']}
    return render_template(
        'edit-submission.jinja2', login_fields=session['login_fields'], pkeys=pkeys,
        pending_deletion=pending_deletion(g.eng, os.environ['CHANGE_HISTORY_TABLE'], session['submissionid']),
        deletion_mode=request.args.get('action') == 'delete',
    )


@login.route('/login_values')
@login_required
def login_values():
    try:
        return jsonify(data=get_login_field(dtypes=current_app.dtypes, eng=g.eng, **request.args))
    except ValueError as error:
        return jsonify(data=[], user_error_msg=str(error)), 400


@login.route('/submissions')
@login_required
def submissions():
    try:
        data = get_submission_ids(dtypes=current_app.dtypes, eng=g.eng, **request.args)
        return jsonify(submissions=data, message='' if data else 'No completed, non-deleted submissions were found for these login fields and datatype.')
    except ValueError as error:
        return jsonify(submissions=[], message=str(error)), 400


@login.route('/post-session-data', methods=['POST'])
@login_required
def sessiondata():
    dtype = request.form.get('dtype')
    if dtype not in current_app.dtypes:
        return jsonify(user_error_msg='Choose a valid datatype.'), 400
    fields = {field['fieldname']: request.form.get(field['fieldname'], '')
              for field in current_app.dtypes[dtype]['login_fields']}
    organization_field = current_app.user_management['organization_login_field']
    login_organization = fields.get(organization_field, fields.get('dataprovider'))
    if current_user.email_confirmed != 'yes' or current_user.is_authorized != 'yes':
        return jsonify(user_error_msg='Your email must be confirmed and your account approved before requesting changes.'), 403
    if current_user.is_admin != 'yes' and current_user.organization != login_organization:
        return jsonify(user_error_msg='You are not authorized to request changes for this organization.'), 403
    try:
        submissionid = int(request.form.get('submissionid', ''))
        available = get_submission_ids(current_app.dtypes, g.eng, dtype, **fields)
        if submissionid not in [int(row['submissionid']) for row in available]:
            raise ValueError('No completed, non-deleted submission matches these login fields and datatype.')
        tables = submission_tables(g.eng, current_app.dtypes[dtype]['tables'], submissionid)
        if not tables:
            raise ValueError('This submission has no data in the configured tables. Contact SCCWRP if this is Survey123 metadata.')
    except (ValueError, TypeError) as error:
        return jsonify(user_error_msg=str(error)), 400
    if session.get('tables') and session.get('sessionid'):
        with request_lock(session['sessionid']):
            drop_snapshots(g.eng, session['tables'], session['sessionid'])
    change_id = allocate_request()
    create_snapshots(g.eng, tables, submissionid, change_id)
    directory = request_directory(change_id)
    with pd.ExcelWriter(directory / 'submission.xlsx', engine='xlsxwriter',
                        engine_kwargs={'options': {'strings_to_formulas': False, 'strings_to_urls': False}}) as writer:
        for table in tables:
            columns, editable = table_metadata(g.eng, table, current_app.system_fields)
            read_snapshot(g.eng, table, change_id, editable).to_excel(writer, sheet_name=table, index=False)
    write_state(change_id, {'ready': False, 'submitted': False, 'request_type': 'edit', 'missing': []})
    for key in ('tablename', 'origin_tablename', 'modified_tablename', 'column_order',
                'submission_colnames', 'original_data_filepath', 'original_data_sql',
                'comparison_path', 'sql_filepath', 'comment'):
        session.pop(key, None)
    session.update(
        tables=tables, sessionid=change_id, submissionid=submissionid, dtype=dtype,
        submissiondate=change_date(submissionid).strftime('%Y-%m-%d %H:%M:%S'), login_fields=fields,
    )
    return jsonify(message='Success')