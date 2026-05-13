from flask import session

def checkData(dataframe, dtype, tablename, badrows, badcolumn, error_type, is_core_error, error_message, q = None):
    assert session.get("errors") is not None, "The errors session variable is not yet defined"
    if len(badrows) > 0:
        if q is None:
            session["errors"].append({
                "table": tablename,
                "dtype": dtype,
                "rows":badrows,
                "columns":badcolumn,
                "error_type":error_type,
                "core_error" : is_core_error,
                "error_message":error_message
            })
        else:
            # This is the case where we run with multiprocessing
            # q would be a mutliprocessing.Queue() 
            q.put({
                "table": tablename,
                "dtype": dtype,
                "rows":badrows,
                "columns":badcolumn,
                "error_type":error_type,
                "core_error" : is_core_error,
                "error_message":error_message
            })

