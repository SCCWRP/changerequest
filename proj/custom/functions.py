import os, glob, re
from pandas import isnull, DataFrame

from proj import custom

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

    initpath = os.path.join(directory, '__init__.py')
    assert(os.path.exists(initpath)), f"{initpath} not found"

    with open(initpath, 'a') as f:
        f.write(f"from .{func_name}_custom import {func_name}")

    if os.path.exists(newfilepath):
        print("Success")
        print(f"Custom check file {newfilepath} added.")
        print("fix_custom_imports function must run to import it into proj/custom/__init__.py so the function can be imported into main.py")
        return True
    else:
        print("Something went wrong")
        return False
    

def fix_custom_imports(directory):
    initpath = os.path.join(directory, '__init__.py')
    assert os.path.exists(initpath), f"{initpath} not found"
    custom_files_glob = glob.glob(os.path.join(directory, '*_custom.py'))

    print("custom checks files:")
    print(custom_files_glob)

    # function names should be the same as that which is before _custom.py
    # these function names should also match the keys of the datasets dictionary defined in the datasets.json configuration file
    # custom import statements would be all the import statements that should be in theory in the __init__.py file for the app to be correctly configured
    custom_import_statements = [
        f"""from .{f.rsplit('/', 1)[-1].rsplit('_',1)[0].strip()}_custom import {f.rsplit('/', 1)[-1].rsplit('_',1)[0].strip()}"""
        for f in custom_files_glob
    ]
    print(custom_import_statements)

    # current imports would be the import statements currently in the __init__.py file
    # An app that is configured correctly would have custom_import_statments the same as current_imports
    import_pattern = re.compile('from\s+\.(\w+)_custom\s+import\s+(\w+)')
    with open(initpath,'r') as initfile:
        # store all lines of the original init file
        initfile_all_lines_orig = [l.strip() for l in initfile.readlines()]
        current_imports = [imp.strip() for imp in initfile_all_lines_orig if bool(re.search(import_pattern, imp))]
        initfile.close()

    imports_to_delete = set(current_imports) - set(custom_import_statements)
    imports_to_add = set(custom_import_statements) - set(current_imports)
    
    with open(initpath,'w') as initfile:
        for line in initfile_all_lines_orig:
            if line.strip() not in imports_to_delete:
                initfile.write(f"{line}\n")
            
        for imp in imports_to_add:
            initfile.write(f"{imp}\n")
        initfile.close()

    print("custom imports updated")
    print(f"Current contents of {initpath}:")
    with open(initpath, 'r') as f:
        print(f.read())
        f.close()
    return