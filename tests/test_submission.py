import importlib.util
import ast
from contextlib import redirect_stdout
from datetime import datetime, date
from decimal import Decimal
import io
import json
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
from unittest.mock import patch
import unittest

import pandas as pd
from psycopg2.extensions import adapt


ROOT = Path(__file__).resolve().parents[1]


def load_helper(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / 'proj' / 'utils' / f'{name}.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


workbooks = load_helper('workbooks')
comparison = load_helper('comparison')


def load_functions(relative_path, namespace):
    tree = ast.parse((ROOT / relative_path).read_text())
    functions = [node for node in tree.body if isinstance(node, ast.FunctionDef)]
    for function in functions:
        function.decorator_list = []
    exec(compile(ast.Module(body=functions, type_ignores=[]), relative_path, 'exec'), namespace)
    return SimpleNamespace(**namespace)


artifacts = load_functions('proj/utils/request_artifacts.py', {
    'pd': pd, 'adapt': adapt, 'json': json, 'datetime': datetime, 'date': date, 'Decimal': Decimal,
})


class Frame:
    def __init__(self, columns, empty=False):
        self.columns = columns
        self.empty = empty


class WorkbookTests(unittest.TestCase):
    def test_report_names_are_unique_and_short(self):
        tables = ['tbl_flow', 'mobile_monitoringstation']
        rows = workbooks.report_index(tables)
        self.assertEqual(len({row['sheet_name'] for row in rows}), 8)
        self.assertTrue(all(len(row['sheet_name']) <= 31 for row in rows))
        self.assertEqual(rows[-1]['sheet_name'], workbooks.report_sheets(tables)[tables[-1]]['Deleted'])

    def test_missing_sheet_is_unchanged(self):
        resolved, missing = workbooks.resolve_sheets({'tbl_flow': Frame(['key'])}, {'tbl_flow': ['key'], 'tbl_waterquality': ['key']})
        self.assertEqual(list(resolved), ['tbl_flow'])
        self.assertEqual(missing, ['tbl_waterquality'])

    def test_column_fallback(self):
        resolved, missing = workbooks.resolve_sheets({'Renamed': Frame(['key'])}, {'tbl_flow': ['key']})
        self.assertEqual(list(resolved), ['tbl_flow'])
        self.assertEqual(missing, [])

    def test_reject_ambiguous_duplicate_unknown_and_empty_sheets(self):
        cases = [
            ({'Renamed': Frame(['key'])}, {'first': ['key'], 'second': ['key']}),
            ({'first': Frame(['key']), 'Renamed': Frame(['key'])}, {'first': ['key']}),
            ({'first': Frame(['unexpected'])}, {'first': ['key']}),
            ({'first': Frame(['key'], empty=True)}, {'first': ['key']}),
        ]
        for sheets, columns in cases:
            with self.subTest(sheets=sheets), self.assertRaises(ValueError):
                workbooks.resolve_sheets(sheets, columns)


class LineageTests(unittest.TestCase):
    def setUp(self):
        self.original = pd.DataFrame([
            {'key': 'first', 'value': 'old', 'objectid': 41, 'login_email': 'original@example.org', 'submissionid': 123},
            {'key': 'second', 'value': 'untouched', 'objectid': 42, 'login_email': 'original@example.org', 'submissionid': 123},
        ])

    def compare(self, modified):
        with redirect_stdout(io.StringIO()):
            return comparison.compare(self.original, modified, ['key'], ['login_email', 'submissionid'])

    def test_immutable_values_restored_on_changed_record(self):
        modified = self.original.copy()
        modified.loc[0, ['value', 'objectid', 'login_email', 'submissionid']] = ['new', 999, 'spoof@example.org', 456]
        added, deleted, changed, cells, originals = self.compare(modified)
        self.assertTrue(added.empty and deleted.empty)
        self.assertEqual(changed.iloc[0].objectid, 41)
        self.assertEqual(changed.iloc[0].login_email, 'original@example.org')
        self.assertEqual(changed.iloc[0].submissionid, 123)
        self.assertEqual([cell['colname'] for cell in cells], ['value'])
        self.assertEqual(originals.iloc[0].value, 'old')

    def test_immutable_only_edit_is_noop(self):
        modified = self.original.copy()
        modified['objectid'] = [0, 1]
        modified['login_email'] = 'spoof@example.org'
        modified['submissionid'] = 456
        added, deleted, changed, cells, originals = self.compare(modified)
        self.assertTrue(added.empty and deleted.empty and changed.empty and originals.empty)
        self.assertEqual(cells, [])

    def test_login_columns_are_immutable_even_without_configuration(self):
        modified = self.original.copy()
        modified['login_email'] = 'spoof@example.org'
        with redirect_stdout(io.StringIO()):
            added, deleted, changed, cells, originals = comparison.compare(self.original, modified, ['key'])
        self.assertTrue(changed.empty)
        self.assertEqual(cells, [])

    def test_primary_key_change_is_addition_and_deletion(self):
        modified = self.original.copy()
        modified.loc[0, 'key'] = 'replacement'
        added, deleted, changed, cells, originals = self.compare(modified)
        self.assertEqual(added.iloc[0]['key'], 'replacement')
        self.assertEqual(deleted.iloc[0].to_dict(), self.original.iloc[0].to_dict())
        self.assertTrue(changed.empty)

    def test_sql_literals_are_data_not_functions(self):
        self.assertEqual(artifacts.sql_literal("sde.next_rowid('sde','tbl_flow')"), "'sde.next_rowid(''sde'',''tbl_flow'')'")
        self.assertEqual(artifacts.sql_literal(None), 'NULL')
        self.assertEqual(artifacts.sql_literal('100%'), "'100%'")
        self.assertIn("O''Brien", artifacts.sql_literal("O'Brien"))
        self.assertIn('END;', artifacts.guard('TRUE', 'Stop'))


class BrowserCorrectionTests(unittest.TestCase):
    def test_omitted_sheet_empty_report_does_not_block_corrections(self):
        main = load_functions('proj/main.py', {})
        frames = {'first': pd.DataFrame({'objectid': [0], 'value': ['a']})}
        main.apply_browser_edits(frames, {'first': [{'row': 0, 'values': {'value': 'fixed'}}], 'omitted': []},
                                 {'first': ['value']}, {'first': [0], 'omitted': []})
        self.assertEqual(frames['first'].value.tolist(), ['fixed'])

    def test_corrections_keep_other_rows_and_tables(self):
        main = load_functions('proj/main.py', {})
        frames = {'first': pd.DataFrame({'objectid': [0, 1], 'value': ['a', 'b']}),
                  'second': pd.DataFrame({'objectid': [0], 'value': ['c']})}
        main.apply_browser_edits(frames, {'first': [{'row': 1, 'values': {'value': 'fixed', 'objectid': 999}}]},
                                 {'first': ['value', 'objectid']}, {'first': [1]})
        self.assertEqual(frames['first'].value.tolist(), ['a', 'fixed'])
        self.assertEqual(frames['first'].objectid.tolist(), [0, 1])
        self.assertEqual(frames['second'].value.tolist(), ['c'])

    def test_unreported_row_rejected(self):
        main = load_functions('proj/main.py', {})
        with self.assertRaises(ValueError):
            main.apply_browser_edits({'first': pd.DataFrame({'value': ['a', 'b']})},
                                     {'first': [{'row': 0, 'values': {'value': 'bad'}}]},
                                     {'first': ['value']}, {'first': [1]})


class BatchTests(unittest.TestCase):
    def test_large_history_is_bounded_and_complete(self):
        helpers = load_functions('proj/utils/submissions.py', {})
        batches = list(helpers.history_batches({'record': index} for index in range(1201)))
        self.assertEqual([len(batch) for batch in batches], [500, 500, 201])
        self.assertEqual(batches[-1][-1]['record'], 1200)


class ArtifactTests(unittest.TestCase):
    def test_multitable_deletion_archives_exact_json_and_only_emits_sql(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            originals = {
                'tbl_flow': [(41, '{"objectid":41,"key":"first","value":1.234567890123456789,"submissionid":123,"login_email":"original@example.org","globalid":"original-id","created_date":"2020-01-01T01:02:03.123456","nullable":null}')],
                'mobile_monitoringstation': [(42, '{"objectid":42,"key":"second","value":"O\u0027Brien","submissionid":123,"login_email":"original@example.org"}')],
            }
            differences = {}
            metadata = {}
            for table, records in originals.items():
                frame = pd.DataFrame([json.loads(record) for objectid, record in records])
                empty = frame.iloc[0:0].copy()
                differences[table] = {'Original': empty, 'Modified': empty, 'Added': empty, 'Deleted': frame, 'changes': []}
                metadata[table] = (list(frame.columns), ['objectid', 'key', 'value'])
            written_sheets = {}
            writer = SimpleNamespace(book=SimpleNamespace(add_format=lambda value: value), sheets={})

            class WriterContext:
                def __enter__(self):
                    return writer

                def __exit__(self, *args):
                    return False

            def write_sheet(frame, writer, sheet_name, index):
                written_sheets[sheet_name] = frame.copy()
                writer.sheets[sheet_name] = object()

            namespace = {
                'pd': pd, 'adapt': adapt, 'json': json, 'datetime': datetime, 'date': date, 'Decimal': Decimal,
                'os': SimpleNamespace(environ={'CHANGE_HISTORY_TABLE': 'change_history'}),
                'session': {'sessionid': 456, 'submissionid': 123, 'tables': list(originals), 'dtype': 'test', 'session_user_email': 'requester@example.org'},
                'current_app': SimpleNamespace(dtypes={'test': {'tables': [*originals, 'tbl_empty']}}),
                'request_directory': lambda change_id: directory,
                'validate_table': lambda eng, table: '"sde"."' + table + '"',
                'identifier': lambda column: '"' + column + '"',
                'report_sheets': workbooks.report_sheets, 'report_index': workbooks.report_index,
                'REPORT_INDEX': workbooks.REPORT_INDEX, 'change_date': lambda change_id: datetime(2026, 1, 1),
                'highlight_changes': lambda *args: None,
            }
            helpers = load_functions('proj/utils/request_artifacts.py', namespace)
            namespace['iter_original_json'] = lambda eng, table, change_id: iter(originals[table])
            with patch.object(pd, 'ExcelWriter', return_value=WriterContext()), patch.object(pd.DataFrame, 'to_excel', write_sheet):
                helpers.write_artifacts(object(), differences, metadata, 'delete')
            records = list(helpers.ledger_records(456))
            self.assertEqual(len(records), 2)
            for record in records:
                self.assertEqual(record['original_record'], originals[record['tablename']][0][1])
                self.assertEqual(record['modified_record'], '[]')
            sql = (directory / 'request.sql').read_text()
            self.assertTrue(sql.startswith('BEGIN;'))
            self.assertTrue(sql.endswith('COMMIT;\n'))
            self.assertEqual(sql.count('COMMIT;'), 1)
            self.assertIn('to_jsonb(original)', sql)
            self.assertIn('"sde"."tbl_empty"', sql)
            self.assertIn('"sde"."tbl_empty"', next(line for line in sql.splitlines() if line.startswith('LOCK TABLE')))
            self.assertIn('deletion_change_id = 456', sql)
            self.assertIn("SET change_processed = 'Yes' WHERE change_id = 456", sql)
            self.assertNotIn('DELETE FROM "sde"."submission_tracking_table"', sql)
            self.assertLess(sql.index('DELETE FROM "sde"."mobile_monitoringstation"'), sql.index('DELETE FROM "sde"."tbl_flow"'))
            self.assertEqual(written_sheets['Index'].to_dict('records'), workbooks.report_index(list(originals)))
            self.assertEqual(len(written_sheets), 9)

            first = differences['tbl_flow']
            first['Original'] = first['Deleted'].copy()
            first['Modified'] = first['Deleted'].copy()
            first['Modified']['value'] = Decimal('9.1234567890123456789')
            first['Deleted'] = first['Deleted'].iloc[0:0].copy()
            first['changes'] = [{'objectid': 41, 'colname': 'value', 'rownumber': 1}]
            second = differences['mobile_monitoringstation']
            second['Added'] = second['Deleted'].copy()
            second['Added']['key'] = 'third'
            second['Added']['value'] = "sde.next_rowid('sde','unexpected')"
            second['Added']['login_email'] = 'spoof@example.org'
            second['Deleted'] = second['Deleted'].iloc[0:0].copy()
            with patch.object(pd, 'ExcelWriter', return_value=WriterContext()), patch.object(pd.DataFrame, 'to_excel', write_sheet):
                helpers.write_artifacts(object(), differences, metadata, 'edit')
            records = list(helpers.ledger_records(456))
            self.assertEqual(len(records), 2)
            self.assertEqual(records[0]['original_record'], originals['tbl_flow'][0][1])
            self.assertEqual(records[1]['original_record'], '[]')
            added = json.loads(records[1]['modified_record'])
            self.assertEqual(added['login_email'], 'original@example.org')
            self.assertEqual(added['submissionid'], 123)
            sql = (directory / 'request.sql').read_text()
            self.assertIn('9.1234567890123456789', sql)
            self.assertIn("'sde.next_rowid(''sde'',''unexpected'')'", sql)
            self.assertNotIn('SET deleted_at', sql)
            self.assertEqual(sql.count('COMMIT;'), 1)

    def test_history_writes_are_bound_batched_and_atomic(self):
        calls = []

        class Connection:
            def __enter__(self):
                calls.append('begin')
                return self

            def __exit__(self, *args):
                calls.append('end')

            def execute(self, sql, params):
                calls.append((sql, params))
                return SimpleNamespace(scalar=lambda: 0)

        connection = Connection()
        records = [
            {'tablename': 'tbl_flow', 'original_record': '{"value":"O\u0027Brien"}', 'modified_record': '[]'}
            for index in range(1201)
        ]
        batching = load_functions('proj/utils/submissions.py', {})
        helpers = load_functions('proj/finalize.py', {
            'json': json, 'os': SimpleNamespace(environ={'CHANGE_HISTORY_TABLE': 'change_history'}),
            'session': {'submissionid': 123, 'login_fields': {'agency': "O'Brien"}},
            'current_user': SimpleNamespace(organization='agency', email='requester@example.org'),
            'validate_table': lambda eng, table: '"sde"."change_history"',
            'text': lambda sql: sql, 'change_date': lambda value: datetime(2026, 1, 1),
            'ledger_records': lambda change_id: iter(records), 'history_batches': batching.history_batches,
        })
        helpers.save_history(SimpleNamespace(begin=lambda: connection), 456, 'delete', "O'Brien\n100%", 1201)
        inserts = [(sql, params) for entry in calls if isinstance(entry, tuple) for sql, params in [entry] if 'INSERT INTO' in sql]
        self.assertEqual([len(params) for sql, params in inserts], [500, 500, 201])
        self.assertEqual(calls[0], 'begin')
        self.assertEqual(calls[-1], 'end')
        for sql, params in inserts:
            self.assertIn(':tablename', sql)
            self.assertNotIn("O'Brien", sql)
            self.assertEqual(params[0]['change_comment'], "O'Brien\n100%")
            self.assertEqual(params[0]['modified_record'], '[]')
            self.assertEqual(params[0]['request_type'], 'delete')

    def test_snapshots_write_only_tmp_without_inherited_defaults(self):
        calls = []

        class Connection:
            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def execute(self, sql, params=None):
                calls.append((sql, params))

        namespace = {'text': lambda sql: sql, 're': __import__('re')}
        helpers = load_functions('proj/utils/submissions.py', namespace)
        namespace['validate_table'] = lambda eng, table: '"sde"."' + table + '"'
        helpers.create_snapshots(SimpleNamespace(begin=lambda: Connection()), ['tbl_flow', 'tbl_waterquality'], 123, 456)
        creates = [(sql, params) for sql, params in calls if sql.startswith('CREATE')]
        self.assertEqual(len(creates), 4)
        self.assertTrue(all(sql.startswith('CREATE TABLE tmp.') for sql, params in creates))
        self.assertTrue(all('INCLUDING' not in sql and 'next_rowid' not in sql for sql, params in creates))
        self.assertEqual(creates[0][1], {'submissionid': 123})

    def test_confirmation_and_comment_are_enforced_before_database_access(self):
        from flask import Flask
        app = Flask('offline-finalization-test')
        state = {'ready': True, 'request_type': 'delete', 'revision': 1}

        class Lock:
            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

        from flask import request, jsonify
        helpers = load_functions('proj/finalize.py', {
            'session': {'sessionid': 456, 'submissionid': 123, 'tables': ['tbl_flow'], 'login_fields': {'agency': 'Agency'}},
            'request': request, 'jsonify': jsonify,
            'current_user': SimpleNamespace(email_confirmed='yes', is_authorized='yes', is_admin='no', organization='Agency'),
            'current_app': SimpleNamespace(user_management={'organization_login_field': 'agency'}),
            'request_lock': lambda change_id: Lock(), 'read_state': lambda change_id: state,
        })
        for form in ({'revision': 1, 'comment': ' ', 'confirmation': '123'},
                     {'revision': 1, 'comment': 'reason', 'confirmation': 'wrong'},
                     {'revision': 0, 'comment': 'reason', 'confirmation': '123'}):
            with app.test_request_context(method='POST', data=form):
                response, status = helpers.savechanges()
                self.assertIn(status, (400, 409))
                self.assertTrue(response.json['message'])


if __name__ == '__main__':
    unittest.main()