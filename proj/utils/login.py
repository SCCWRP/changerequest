import pandas as pd

def get_login_field(dtypes, dtype, field, eng, **kwargs):
    # dtypes is a dictionary that needs to be configured a certain way
    login_fields = [dt.get('fieldname') for dt in dtypes.get(dtype).get('login_fields')]
    assert set(kwargs.keys()).issubset(set(login_fields)), \
        f"The keyword args {', '.join(kwargs.keys())} not found in the valid login fields: {', '.join(login_fields)}"

    assert field in login_fields, \
        f"The fieldname {field} not found in the valid login fields: {', '.join(login_fields)}"


    if (len(kwargs) == 0):
        sql = f"SELECT DISTINCT login_{field} AS {field} FROM submission_tracking_table WHERE submit = 'yes' ORDER BY 1;"
    else:
        sql = f"""
        SELECT DISTINCT login_{field} AS {field} FROM submission_tracking_table 
        WHERE submit = 'yes'
        AND 
        {
            ' AND '.join([f"login_{k} = '{v}'" for k,v in kwargs.items() if k not in ('field','dtype')])
        }
        ORDER BY 1;
        """
    print(sql)
    # object of type ndarray is not json serializable, so we have to return a list rather than a numpy array
    vals = pd.read_sql(sql, eng)[field].tolist()
    return vals


def get_submission_ids(dtypes, eng, dtype = None, **kwargs):
    # dtypes is a dictionary that needs to be configured a certain way
    kwargs_cols = [f'login_{k}' for k in kwargs.keys()]
    stt_cols = pd.read_sql("SELECT column_name FROM information_schema.columns WHERE table_name = 'submission_tracking_table'", eng).column_name.values
    
    assert set(kwargs_cols).issubset(set(stt_cols)), \
        "kwargs keys {} not in columns of submission tracking table {}".format(
            ','.join([f'login_{k}' for k in kwargs.keys()]),
            ','.join(stt_cols)
        )
    
    # -------- NOTE -------# 
    # For this query to work it is absolutely critical that the dtypes in the datasets dictionary are the same and those of the checker application
    # We will query submission ID's also based on the extended checks type, which is the same as a datatype
    # TODO We will definitely need to somehow use psycopg2's classes, methods and functions for preventing SQL injection
    # such as psycopg2.sql.Identifier, or psycopg2.sql.Literal
    sql = f"""
        SELECT DISTINCT submissionid, created_date AS submissiondate FROM submission_tracking_table 
        WHERE submit = 'yes'
        AND 
        {
            ' AND '.join([ f"login_{k} = '{v}'" for k,v in kwargs.items() ])
        }
        AND datatype = '{dtype.replace(';','').replace("'","")}'
        ORDER BY 1;
    """
    print(sql)
    # object of type ndarray is not json serializable, so we have to return a list rather than a numpy array
    subs = pd.read_sql(sql, eng)

    # print("dtypes")
    # print(dtypes)
    # print(dtypes.get(dtype).get('tables'))
    # submissionid_sql = "({})".format(") UNION (".join([f"SELECT DISTINCT submissionid FROM {table}" for table in dtypes.get(dtype).get('tables')]))
    # print(submissionid_sql)
    # print( pd.read_sql(submissionid_sql, eng).submissionid.values)
    # subs = subs[
    #     subs.submissionid.isin(
    #         pd.read_sql(submissionid_sql, eng).submissionid.values
    #     )
    # ]
    

    # subs = subs.apply(lambda row: f"Submission ID: {row.submissionid} (submitted {row.submissiondate.strftime('%Y-%m-%d %H:%M:%S')})", axis = 1).tolist() \
    #     if not subs.empty else []
    subs.submissiondate = subs.submissiondate.apply(lambda x: x.strftime('%Y-%m-%d %H:%M:%S'))
    subs = subs.to_dict('records')
    print(subs)
    return subs
