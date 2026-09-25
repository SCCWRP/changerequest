from contextlib import contextmanager
from datetime import datetime
import fcntl
import json
import os
from pathlib import Path
import re
import time

import pandas as pd
from sqlalchemy import text


def identifier(value):
    if not re.fullmatch(r'[a-z_][a-z0-9_]*', value):
        raise ValueError('Invalid database identifier.')
    return '"' + value + '"'


def validate_table(eng, table, schema='sde'):
    found = pd.read_sql(text(
        'SELECT table_name FROM information_schema.tables '
        'WHERE table_schema = :schema AND table_name = :table'
    ), eng, params={'schema': schema, 'table': table})
    if found.empty:
        raise ValueError(f'Table {schema}.{table} was not found.')
    return f'{identifier(schema)}.{identifier(table)}'


def table_metadata(eng, table, system_fields):
    validate_table(eng, table)
    columns = pd.read_sql(text(
        'SELECT column_name FROM information_schema.columns '
        'WHERE table_schema = :schema AND table_name = :table ORDER BY ordinal_position'
    ), eng, params={'schema': 'sde', 'table': table}).column_name.tolist()
    order = []
    exists = pd.read_sql(text(
        "SELECT table_name FROM information_schema.tables WHERE table_schema = 'sde' AND table_name = 'column_order'"
    ), eng)
    if not exists.empty:
        order = pd.read_sql(text(
            'SELECT column_name FROM sde.column_order WHERE table_name = :table '
            'ORDER BY custom_column_position, column_name'
        ), eng, params={'table': table}).column_name.tolist()
    order = list(dict.fromkeys([name for name in order if name in columns] + columns))
    editable = [name for name in order if name not in system_fields and not name.startswith('login_')]
    return columns, editable


def submission_tables(eng, configured_tables, submissionid):
    tables = []
    for table in configured_tables:
        qualified = validate_table(eng, table)
        rows = pd.read_sql(text(
            f'SELECT 1 FROM {qualified} WHERE submissionid = :submissionid LIMIT 1'
        ), eng, params={'submissionid': int(submissionid)})
        if not rows.empty:
            tables.append(table)
    return tables


def request_directory(change_id):
    return Path.cwd() / 'files' / 'requests' / str(int(change_id))


def allocate_request():
    change_id = int(time.time())
    while True:
        try:
            request_directory(change_id).mkdir(parents=True, mode=0o700)
            return change_id
        except FileExistsError:
            change_id += 1


@contextmanager
def request_lock(change_id):
    with (request_directory(change_id) / 'lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(lock, fcntl.LOCK_UN)


def temp_name(table, change_id, kind):
    name = f'{kind}_{table}_{int(change_id)}'
    identifier(name)
    if len(name) > 63:
        raise ValueError('Temporary table name exceeds PostgreSQL identifier limit.')
    return name


def create_snapshots(eng, tables, submissionid, change_id):
    with eng.begin() as connection:
        connection.execute(text('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ'))
        for table in tables:
            qualified = validate_table(connection, table)
            original = identifier(temp_name(table, change_id, 'orig'))
            modified = identifier(temp_name(table, change_id, 'mod'))
            connection.execute(text(
                f'CREATE TABLE tmp.{original} AS SELECT * FROM {qualified} '
                'WHERE submissionid = :submissionid'
            ), {'submissionid': int(submissionid)})
            connection.execute(text(f'CREATE TABLE tmp.{modified} AS SELECT * FROM {qualified} WITH NO DATA'))


def drop_snapshots(eng, tables, change_id):
    with eng.begin() as connection:
        for table in tables:
            validate_table(connection, table)
            for kind in ('orig', 'mod'):
                name = identifier(temp_name(table, change_id, kind))
                connection.execute(text(f'DROP TABLE IF EXISTS tmp.{name}'))


def read_snapshot(eng, table, change_id, columns=None, kind='orig'):
    qualified = validate_table(eng, temp_name(table, change_id, kind), 'tmp')
    selection = ', '.join(identifier(column) for column in columns) if columns else '*'
    return pd.read_sql(text(f'SELECT {selection} FROM {qualified} ORDER BY objectid'), eng, coerce_float=False)


def store_candidate(eng, table, change_id, frame):
    name = temp_name(table, change_id, 'mod')
    qualified = validate_table(eng, name, 'tmp')
    with eng.begin() as connection:
        connection.execute(text(f'DELETE FROM {qualified}'))
        frame.to_sql(name, connection, schema='tmp', if_exists='append', index=False, chunksize=500)


def write_state(change_id, state):
    directory = request_directory(change_id)
    with (directory / 'state.new').open('w') as output:
        json.dump(state, output)
    os.replace(directory / 'state.new', directory / 'state.json')


def read_state(change_id):
    with (request_directory(change_id) / 'state.json').open() as source:
        return json.load(source)


def pending_deletion(eng, history_table, submissionid):
    qualified = validate_table(eng, history_table)
    return not pd.read_sql(text(
        f'SELECT 1 FROM {qualified} WHERE submissionid = :submissionid '
        "AND change_processed = 'No' AND request_type = 'delete' LIMIT 1"
    ), eng, params={'submissionid': int(submissionid)}).empty


def history_batches(records, size=500):
    batch = []
    for record in records:
        batch.append(record)
        if len(batch) == size:
            yield batch
            batch = []
    if batch:
        yield batch


def change_date(change_id):
    return datetime.utcfromtimestamp(int(change_id))