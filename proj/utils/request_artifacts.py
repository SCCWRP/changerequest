from datetime import date, datetime
from decimal import Decimal
import json
import os

import pandas as pd
from flask import current_app, session
from psycopg2.extensions import adapt
from sqlalchemy import text

from .comparison import highlight_changes
from .submissions import change_date, identifier, request_directory, temp_name, validate_table
from .workbooks import REPORT_INDEX, report_index, report_sheets


def scalar(value):
    if value is None or (not isinstance(value, (dict, list)) and pd.isnull(value)):
        return None
    if hasattr(value, 'item'):
        return value.item()
    if isinstance(value, pd.Timestamp):
        return value.to_pydatetime()
    return value


def sql_literal(value):
    value = scalar(value)
    if isinstance(value, (dict, list)):
        value = json.dumps(value)
    adapted = adapt(value)
    if isinstance(value, str):
        adapted.encoding = 'utf8'
    return adapted.getquoted().decode('utf8')


def json_default(value):
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    raise TypeError(f'Unsupported record value: {type(value).__name__}')


def record_json(record):
    return json.dumps({column: scalar(value) for column, value in record.items()}, default=json_default, allow_nan=False)


def guard(condition, message):
    body = f'BEGIN IF {condition} THEN RAISE EXCEPTION {sql_literal(message)}; END IF; END;'
    return f'DO {sql_literal(body)};\n'


def iter_original_json(eng, table, change_id):
    qualified = validate_table(eng, temp_name(table, change_id, 'orig'), 'tmp')
    with eng.connect() as connection:
        result = connection.execution_options(stream_results=True).execute(text(
            f'SELECT objectid, row_to_json(original)::text AS record FROM {qualified} AS original ORDER BY objectid'
        ))
        try:
            for row in result:
                yield int(row.objectid), row.record
        finally:
            result.close()


def ledger_records(change_id):
    with (request_directory(change_id) / 'history.jsonl').open() as source:
        for line in source:
            yield json.loads(line)


def write_artifacts(eng, differences, metadata, request_type):
    change_id = session['sessionid']
    submissionid = int(session['submissionid'])
    directory = request_directory(change_id)
    tables = session['tables']
    qualified = {table: validate_table(eng, table) for table in tables}
    deletion_tables = {
        table: validate_table(eng, table) for table in current_app.dtypes[session['dtype']]['tables']
    } if request_type == 'delete' else {}
    history = validate_table(eng, os.environ['CHANGE_HISTORY_TABLE'])
    tracking = validate_table(eng, 'submission_tracking_table')
    sheets = report_sheets(tables)
    timestamp = change_date(change_id)
    email = session['session_user_email']
    with pd.ExcelWriter(directory / 'comparison.xlsx', engine='xlsxwriter',
                        engine_kwargs={'options': {'strings_to_formulas': False, 'strings_to_urls': False}}) as writer:
        pd.DataFrame(report_index(tables)).to_excel(writer, sheet_name=REPORT_INDEX, index=False)
        for table in tables:
            for kind, sheet in sheets[table].items():
                frame = differences[table][kind]
                frame = frame[[column for column in metadata[table][1] if column in frame.columns]]
                frame.to_excel(writer, sheet_name=sheet, index=False)
                if kind == 'Modified':
                    color = writer.book.add_format({'bg_color': '#42f590'})
                    positions = {int(value): position + 1 for position, value in enumerate(frame.objectid)}
                    cells = [(positions[change['objectid']], frame.columns.get_loc(change['colname']))
                             for change in differences[table]['changes'] if change['colname'] in frame.columns]
                    highlight_changes(writer.sheets[sheet], color, cells)

    with (directory / 'request.sql').open('w') as output, (directory / 'history.jsonl').open('w') as ledger:
        output.write('BEGIN;\nSET LOCAL standard_conforming_strings = off;\n')
        locked_tables = deletion_tables if request_type == 'delete' else qualified
        output.write(f'LOCK TABLE {", ".join([*locked_tables.values(), tracking, history])} IN SHARE ROW EXCLUSIVE MODE;\n')
        output.write(guard(
            f"NOT EXISTS (SELECT 1 FROM {history} WHERE change_id = {int(change_id)} AND change_processed = 'No')",
            'This request is not recorded as pending in change_history.',
        ))
        output.write(guard(
            f'NOT EXISTS (SELECT 1 FROM {tracking} WHERE submissionid = {submissionid} AND deleted_at IS NULL)',
            'Submission is missing or already deleted.',
        ))
        if request_type == 'delete':
            for table, data_table in deletion_tables.items():
                count = len(differences[table]['Deleted']) if table in differences else 0
                output.write(guard(
                    f'(SELECT count(*) FROM {data_table} WHERE submissionid = {submissionid}) <> {count}',
                    f'{table}: submission row count changed; prepare a new deletion request.',
                ))
        for table in tables:
            output.write(f'\n-- {table}: verify original records --\n')
            delta = differences[table]
            modified = {int(row['objectid']): row for row in delta['Modified'].to_dict('records')}
            deleted = set(int(value) for value in delta['Deleted'].objectid)
            changed_columns = {}
            for change in delta['changes']:
                changed_columns.setdefault(change['objectid'], []).append(change['colname'])
            lineage = None
            for objectid, original_json in iter_original_json(eng, table, change_id):
                if lineage is None:
                    lineage = json.loads(original_json)
                if objectid not in deleted and objectid not in modified:
                    continue
                output.write(guard(
                    f'NOT EXISTS (SELECT 1 FROM {qualified[table]} AS original WHERE objectid = {objectid} '
                    f'AND submissionid = {submissionid} AND to_jsonb(original) = {sql_literal(original_json)}::jsonb)',
                    f'{table} objectid {objectid}: original record changed; prepare a new request.',
                ))
                if objectid in deleted:
                    modified_json = '[]'
                else:
                    record = json.loads(original_json)
                    record.update({column: scalar(modified[objectid][column]) for column in changed_columns[objectid]})
                    if 'last_edited_user' in record:
                        record['last_edited_user'] = email
                    if 'last_edited_date' in record:
                        record['last_edited_date'] = timestamp
                    modified_json = record_json(record)
                ledger.write(json.dumps({'tablename': table, 'original_record': original_json, 'modified_record': modified_json}) + '\n')
            delta['lineage'] = lineage or {}
        for table in reversed(tables):
            output.write(f'\n-- {table}: deleted records --\n')
            for objectid in differences[table]['Deleted'].objectid:
                output.write(f'DELETE FROM {qualified[table]} WHERE objectid = {int(objectid)} AND submissionid = {submissionid};\n')
        for table in tables:
            output.write(f'\n-- {table}: modified and added records --\n')
            delta = differences[table]
            columns = metadata[table][0]
            modified = {int(row['objectid']): row for row in delta['Modified'].to_dict('records')}
            changed_columns = {}
            for change in delta['changes']:
                changed_columns.setdefault(change['objectid'], []).append(change['colname'])
            for objectid, names in changed_columns.items():
                values = {column: modified[objectid][column] for column in names}
                values.update({column: value for column, value in {
                    'last_edited_user': email, 'last_edited_date': timestamp,
                }.items() if column in columns})
                assignments = ', '.join(f'{identifier(column)} = {sql_literal(value)}' for column, value in values.items())
                output.write(f'UPDATE {qualified[table]} SET {assignments} WHERE objectid = {int(objectid)} AND submissionid = {submissionid};\n')
            for record in delta['Added'].to_dict('records'):
                record.update({column: value for column, value in delta['lineage'].items() if column.startswith('login_')})
                record.update({column: value for column, value in {
                    'submissionid': submissionid, 'created_user': 'change request app', 'created_date': timestamp,
                    'last_edited_user': email, 'last_edited_date': timestamp,
                }.items() if column in columns})
                record.pop('objectid', None)
                record.pop('globalid', None)
                expressions = {column: sql_literal(value) for column, value in record.items()}
                if 'objectid' in columns:
                    expressions['objectid'] = f"sde.next_rowid('sde', {sql_literal(table)})"
                if 'globalid' in columns:
                    expressions['globalid'] = 'sde.next_globalid()'
                output.write(f'INSERT INTO {qualified[table]} ({", ".join(identifier(column) for column in expressions)}) '
                             f'VALUES ({", ".join(expressions.values())});\n')
                ledger.write(json.dumps({'tablename': table, 'original_record': '[]', 'modified_record': record_json(record)}) + '\n')
        if request_type == 'delete':
            output.write(f'\nUPDATE {tracking} SET deleted_at = CURRENT_TIMESTAMP, deleted_by = {sql_literal(email)}, '
                         f'deletion_change_id = {int(change_id)} WHERE submissionid = {submissionid};\n')
        output.write(f"\nUPDATE {history} SET change_processed = 'Yes' WHERE change_id = {int(change_id)};\nCOMMIT;\n")