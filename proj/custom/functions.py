import json, os
from pandas import isnull, DataFrame

def checkData(dataframe, tablename, badrows, badcolumn, error_type, is_core_error = False, error_message = "Error", errors_list = [], q = None):
    
    # See comments on the get_badrows function
    # doesnt have to be used but it makes it more convenient to plug in a check
    # that function can be used to get the badrows argument that would be used in this function
    
    if len(badrows) > 0:
        if q is not None:
            # This is the case where we run with multiprocessing
            # q would be a mutliprocessing.Queue() 
            q.put({
                "table": tablename,
                "rows":badrows,
                "columns":badcolumn,
                "error_type":error_type,
                "is_core_error" : is_core_error,
                "error_message":error_message
            })

        return {
            "table": tablename,
            "rows":badrows,
            "columns":badcolumn,
            "error_type":error_type,
            "is_core_error" : is_core_error,
            "error_message":error_message
        }
    return {}
        

def get_badrows(df_badrows, badcol = None, message = ""):
    """
    df_badrows is a dataframe filtered down to the rows which DO NOT meet the criteria of the check. 
    errmsg is self explanatory
    """

    assert isinstance(df_badrows, DataFrame), "in function get_badrows, df_badrows argument is not a pandas DataFrame"
    

    if df_badrows.empty:
        return []

    return [
        {
            # row number is the row number in the excel file
            'row_number': int(rownum),
            'objectid': objid,
            'value': val if not isnull(val) else '',
            # Individualized error message is mainly for the Lookup list error in core checks
            # But for consistency we will retain it here
            # Since this "message" key, value pair in the "rows" dictionary was for error messages which contain the 
            #  value the user entered
            'message': str(message).replace('__value__', str(val)) if val else message
        } 
        for rownum, objid, val in
        df_badrows \
        .apply(
            lambda row:
            (
                row.name + 1,
                row['objectid'],
                row[badcol] if badcol else None
            ),
            axis = 1
        ) \
        .values
    ]



# When the app starts up, it will check to see if all the custom checks functions exist if they were specified in the config file
# If they were not specified, it will create the file and the function
def add_custom_checks_function(directory, func_name):
    func_name = str(func_name).lower()
    
    newfilepath = os.path.join(directory, f"{func_name}_custom.py")
    
    if os.path.exists(newfilepath):
        print(f"{newfilepath} already exists")
        return
        
    # The reason i do an if statement rather than an assert is because i dont want to prevent the app from running altogether
    templatefilepath = os.path.join(directory, f"example.py")
    if not os.path.exists(templatefilepath):
        print(f"example.py not found in {directory}")

    newfile = open(newfilepath, 'w')
    templatefile = open(templatefilepath, 'r')

    for line in templatefile:
        newfile.write(line.replace('__example__', func_name))
    
    newfile.close()
    templatefile.close()

    initfile = open(os.path.join(directory, '__init__.py'), 'a')
    initfile.write(f'\nfrom .{func_name}_custom import {func_name}')

    if os.path.exists(newfilepath):
        print("Success")
        return True
    else:
        print("Something went wrong")
        return False
    
