from copy import deepcopy
import os

import pandas as pd
from flask import Blueprint, request, jsonify, session, current_app, g
from flask_login import login_required

from . import custom as custom_checks
from .core import core
from .utils.comparison import compare
from .utils.db import get_primary_key
from .utils.html import htmltable
from .utils.request_artifacts import write_artifacts
from .utils.submissions import (
    read_snapshot, read_state, request_directory, request_lock, store_candidate,
    submission_tables, table_metadata, write_state,
)
from .utils.workbooks import resolve_sheets


comparison = Blueprint('comparison', __name__)


def check_submission(frames):
    results = {}
    for table, frame in frames.items():
        output = core(df=deepcopy(frame), tblname=table, eng=g.eng, debug=True)
        errors = [error for error in output['core_errors'] if error]
        warnings = [warning for warning in output['core_warnings'] if warning]
        if not errors:
            store_candidate(g.eng, table, session['sessionid'], frame)
            frame = read_snapshot(g.eng, table, session['sessionid'], list(frame.columns), kind='mod')
            frames[table] = frame
            function_name = current_app.dtypes[session['dtype']]['custom_checks_functions'][table]
            output = getattr(custom_checks, function_name)(deepcopy(frame), table)
            errors.extend(error for error in output['errors'] if error)
            warnings.extend(warning for warning in output['warnings'] if warning)
        results[table] = {'errors': errors, 'warnings': warnings}
    return results


def table_report(frame, added, deleted, changes, checks, edit_rows):
    rejected = [
        {'rownumber': row['row_number'], 'colname': error['columns'], 'objectid': row['objectid']}
        for error in checks['errors'] for row in error['rows']
    ]
    return {
        'tbl': htmltable(frame, _id='changes-display-table'),
        'addtbl': htmltable(added, editable=False),
        'deltbl': htmltable(deleted, editable=False),
        'changed_indices': changes or rejected,
        'accepted_changes': changes,
        'rejected_changes': rejected,
        'errors': checks['errors'], 'warnings': checks['warnings'], 'edit_rows': edit_rows,
        'counts': {'modified': len(frame) if not checks['errors'] else 0, 'added': len(added), 'deleted': len(deleted)},
    }


def compare_submission(frames, metadata, missing):
    checked = {table: frame for table, frame in frames.items() if table not in missing}
    checks = check_submission(checked)
    reports = {}
    differences = {}
    for table in session['tables']:
        columns, editable = metadata[table]
        original = read_snapshot(g.eng, table, session['sessionid'], editable)
        empty = original.iloc[0:0].copy()
        if table in missing:
            reports[table] = table_report(empty, empty, empty, [], {'errors': [], 'warnings': []}, [])
            differences[table] = {'Original': empty, 'Modified': empty, 'Added': empty, 'Deleted': empty, 'changes': []}
            continue
        frame = checked[table]
        if checks[table]['errors']:
            reports[table] = table_report(frame, empty, empty, [], checks[table], [int(value) for value in frame.objectid])
            continue
        primary_key = get_primary_key(table, g.eng)
        if not primary_key:
            raise ValueError(f'{table} has no primary key; SCCWRP must configure it before editing.')
        immutable = list(set(current_app.immutable_fields) | {column for column in columns if column.startswith('login_')})
        added, deleted, modified, changes, originals = compare(
            original, frame, primary_key, immutable,
            current_app.dtypes[session['dtype']].get('special_numeric_columns', []),
        )
        for records in (modified, deleted, originals):
            records['objectid'] = records.objectid.astype(int)
        added['objectid'] = -220
        differences[table] = {'Original': originals, 'Modified': modified, 'Added': added, 'Deleted': deleted, 'changes': changes}
        source_rows = modified[primary_key].merge(
            frame[primary_key + ['objectid']], on=primary_key, how='left', validate='one_to_one'
        ).objectid.tolist() if not modified.empty else []
        reports[table] = table_report(modified, added, deleted, changes, checks[table], [int(value) for value in source_rows])
    return reports, differences


def apply_browser_edits(frames, edits, editable_columns, allowed_rows):
    if not isinstance(edits, dict) or not edits:
        raise ValueError('No browser corrections were supplied.')
    for table, rows in edits.items():
        if table not in allowed_rows:
            raise ValueError('Unknown submission table.')
        if not rows:
            continue
        if table not in frames:
            raise ValueError('Unknown submission table.')
        for patch in rows:
            row_number = int(patch['row'])
            if row_number not in allowed_rows[table] or row_number not in frames[table].index:
                raise ValueError('The report is out of date. Upload the workbook again.')
            values = patch['values']
            if not set(values).issubset(editable_columns[table]):
                raise ValueError('Unknown column in browser corrections.')
            for column, value in values.items():
                if column != 'objectid':
                    frames[table].at[row_number, column] = value if value != '' else None


@comparison.route('/compare', methods=['POST'])
@login_required
def main():
    if not session.get('tables'):
        return jsonify(message='Your editing session expired. Select the submission again.'), 400
    change_id = session['sessionid']
    with request_lock(change_id):
        state = read_state(change_id)
        if state.get('submitted'):
            return jsonify(message='This request has already been submitted.'), 409
        state['ready'] = False
        write_state(change_id, state)
        try:
            metadata = {table: table_metadata(g.eng, table, current_app.system_fields) for table in session['tables']}
            editable_columns = {table: details[1] for table, details in metadata.items()}
            directory = request_directory(change_id)
            files = request.files.getlist('files[]')
            if files:
                if len(files) != 1 or not files[0].filename.lower().endswith('.xlsx'):
                    raise ValueError('Upload exactly one .xlsx workbook.')
                sheets = pd.read_excel(files[0], sheet_name=None,
                                       dtype={'result': object, 'mdl': object, 'bioaccumulationsampleid': object},
                                       keep_default_na=False, na_values=[''])
                frames, missing = resolve_sheets(sheets, editable_columns)
                for table, frame in frames.items():
                    frame['objectid'] = frame.index
                state['missing'] = missing
            else:
                if not (directory / 'candidates.pkl').exists():
                    raise ValueError('Upload a workbook before making browser corrections.')
                frames = pd.read_pickle(directory / 'candidates.pkl')
                missing = state['missing']
                body = request.get_json(silent=True) or {}
                if body.get('revision') != state.get('revision'):
                    raise ValueError('The report is out of date. Upload the workbook again.')
                apply_browser_edits(frames, body.get('tables'), editable_columns, state.get('edit_rows', {}))
            pd.to_pickle(frames, directory / 'candidates.pkl')
            reports, differences = compare_submission(frames, metadata, missing)
            has_errors = any(report['errors'] for report in reports.values())
            has_changes = any(sum(report['counts'].values()) for report in reports.values())
            if not has_errors and has_changes:
                write_artifacts(g.eng, differences, metadata, 'edit')
            state.update(ready=not has_errors and has_changes, request_type='edit',
                         revision=state.get('revision', 0) + 1,
                         edit_rows={table: report['edit_rows'] for table, report in reports.items()})
            write_state(change_id, state)
            return jsonify(
                tables=reports, ready=state['ready'], revision=state['revision'], request_type='edit',
                warnings=[f'{table}: sheet omitted; no changes requested.' for table in missing],
                message='' if has_changes or has_errors else 'No changes were found in this submission.',
            )
        except ValueError as error:
            return jsonify(message=str(error)), 400


@comparison.route('/request-deletion', methods=['POST'])
@login_required
def request_deletion():
    if not session.get('tables'):
        return jsonify(message='Select a submission first.'), 400
    change_id = session['sessionid']
    with request_lock(change_id):
        state = read_state(change_id)
        if state.get('submitted'):
            return jsonify(message='This request has already been submitted.'), 409
        state['ready'] = False
        write_state(change_id, state)
        tables = submission_tables(g.eng, current_app.dtypes[session['dtype']]['tables'], session['submissionid'])
        if tables != session['tables']:
            return jsonify(message='The submission table set changed. Start a new session before requesting deletion.'), 409
        differences = {}
        reports = {}
        metadata = {}
        for table in tables:
            metadata[table] = table_metadata(g.eng, table, current_app.system_fields)
            original = read_snapshot(g.eng, table, change_id, metadata[table][1])
            empty = original.iloc[0:0].copy()
            differences[table] = {'Original': empty, 'Modified': empty, 'Added': empty, 'Deleted': original, 'changes': []}
            reports[table] = table_report(empty, empty, original, [], {'errors': [], 'warnings': []}, [])
        write_artifacts(g.eng, differences, metadata, 'delete')
        state.update(ready=True, request_type='delete', revision=state.get('revision', 0) + 1, edit_rows={})
        write_state(change_id, state)
        return jsonify(tables=reports, ready=True, request_type='delete', revision=state['revision'],
                       warnings=['All listed records will be deleted only after SCCWRP staff run the SQL.'], message='')


@comparison.errorhandler(Exception)
def default_error_handler(error):
    current_app.logger.exception('Submission comparison failed')
    return jsonify(message='The comparison could not be completed. Contact SCCWRP with your change ID.'), 500