import pandas as pd
from sqlalchemy import text
from .submissions import identifier, validate_table


def tracking_filter(dtypes, dtype, eng, values):
    if dtype not in dtypes:
        raise ValueError('Choose a valid datatype.')
    fields = [field['fieldname'] for field in dtypes[dtype]['login_fields']]
    if not set(values).issubset(fields):
        raise ValueError('Unknown login fields.')
    validate_table(eng, 'submission_tracking_table')
    columns = pd.read_sql(text(
        "SELECT column_name FROM information_schema.columns WHERE table_schema = 'sde' AND table_name = 'submission_tracking_table'"
    ), eng).column_name.tolist()
    if not all('login_' + field in columns for field in fields):
        raise ValueError('No submission tracking login fields are available for this datatype.')
    conditions = ["submit = 'yes'", 'deleted_at IS NULL', 'datatype = :dtype']
    params = {'dtype': dtype}
    for field, value in values.items():
        conditions.append(f'{identifier("login_" + field)} = :{field}')
        params[field] = value
    return ' AND '.join(conditions), params, fields


def get_login_field(dtypes, dtype, field, eng, **kwargs):
    conditions, params, fields = tracking_filter(dtypes, dtype, eng, kwargs)
    if field not in fields:
        raise ValueError('Unknown login field.')
    column = identifier('login_' + field)
    return pd.read_sql(text(
        f'SELECT DISTINCT {column} AS value FROM sde.submission_tracking_table WHERE {conditions} ORDER BY 1'
    ), eng, params=params).value.tolist()


def get_submission_ids(dtypes, eng, dtype=None, **kwargs):
    conditions, params, fields = tracking_filter(dtypes, dtype, eng, kwargs)
    submissions = pd.read_sql(text(
        'SELECT DISTINCT submissionid, created_date AS submissiondate '
        f'FROM sde.submission_tracking_table WHERE {conditions} ORDER BY 1'
    ), eng, params=params)
    submissions.submissiondate = submissions.submissiondate.apply(
        lambda value: value.strftime('%Y-%m-%d %H:%M:%S') if pd.notnull(value) else ''
    )
    return submissions.to_dict('records')