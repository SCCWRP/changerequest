import pandas as pd
import multiprocessing as mp
import re, time
from math import log10
from pandas import DataFrame, isnull
from functools import lru_cache

def checkData(dataframe, tablename, badrows, badcolumn, error_type, is_core_error = True, error_message = "Error", errors_list = [], q = None):
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
        
      

# For the sake of checking the data in multiple ways at the same time
def multitask(functions: list, *args):
    '''funcs is a list of functions that will be turned into processes'''
    output = mp.Queue()
    processes = [
        mp.Process(target = function, args = (*args,), kwargs = {'output': output}) 
        for function in functions
    ]

    starttime = time.time()
    for p in processes:
        print("starting a process")
        p.start()
        
    for p in processes:
        print("joining processes")
        p.join()

    finaloutput = []
    while output.qsize() > 0:
        finaloutput.append(output.get())
    print("output from the multitask/mutliprocessing function")
    #print(finaloutput)
    return finaloutput



@lru_cache(maxsize=128, typed=True)
def convert_dtype(t, x):
    try:
        if ((pd.isnull(x)) and (t == int)):
            return True
        t(x)
        return True
    except Exception as e:
        return False

@lru_cache(maxsize=128, typed=True)
def check_precision(x, precision):
    try:
        int(x)
    except Exception as e:
        # if you cant call int on it, its not numeric
        # Meaning it is not valid to check precision
        # thus we return true.
        # if its the wrong datatype it should get picked up by that check
        return True

    if pd.isnull(precision):
        return True

    x = abs(x)
    left = int(log10(x)) + 1 if x > 0 else 1
    frac_part = abs(int(re.sub("\d*\.","",str(x)))) if '.' in str(x) else 0
    if frac_part > 0:
        while (frac_part % 10 == 0):
            frac_part = int(frac_part / 10)
    right = len(str(frac_part)) if frac_part > 0 else 0
    return True if left + right <= precision else False

@lru_cache(maxsize=128, typed=True)
def check_scale(x, scale):
    try:
        int(x)
    except Exception as e:
        # if you cant call int on it, its not numeric
        # Meaning it is not valid to check precision
        # thus we return true.
        # if its the wrong datatype it should get picked up by that check
        return True
    if pd.isnull(scale):
        return True
    x = abs(x)
    frac_part = abs(int(re.sub("\d*\.","",str(x)))) if '.' in str(x) else 0
    if frac_part > 0:
        while (frac_part % 10 == 0):
            frac_part = int(frac_part / 10)
    right = len(str(frac_part)) if frac_part > 0 else 0
    return True if right <= scale else False

@lru_cache(maxsize=128, typed=True)
def check_length(x, maxlength):
    if pd.isnull(maxlength):
        return True
    return True if len(str(x)) <= int(maxlength) else False




def fetch_meta(tablename, eng):

    meta = pd.read_sql(
            f"""
            SELECT 
                table_name, 
                column_name, 
                is_nullable, 
                data_type,
                udt_name, 
                character_maximum_length, 
                numeric_precision, 
                numeric_scale 
            FROM 
                information_schema.columns 
            WHERE 
                table_name = '{tablename}';
            """, 
            eng
        )

    meta['dtype'] = meta \
        .udt_name \
        .apply(
            # This pretty much only works if the columns were defined through Arc
            lambda x: 
            int if 'int' in x 
            else str if x == 'varchar' 
            else pd.Timestamp if x == 'timestamp' 
            else float if x == 'numeric' 
            else None
        )  

    return meta



# This function allows you to put in a table name and get back the primary key fields of the table
def get_primary_key(tablename, eng):
    # eng is a sqlalchemy database connection

    # This query gets us the primary keys of a table. Not in a python friendly format
    # Copy paste to Navicat, pgadmin, or do a pd.read_sql to see what it gives
    pkey_query = f"""
        SELECT 
            conrelid::regclass AS table_from, 
            conname, 
            pg_get_constraintdef(oid) 
        FROM pg_constraint 
        WHERE 
            contype IN ('f', 'p') 
            AND connamespace = 'sde'::regnamespace 
            AND conname LIKE '{tablename}%%' 
        ORDER BY 
            conrelid::regclass::text, contype DESC;
    """
    pkey_df = pd.read_sql(pkey_query, eng)
    
    pkey = []
    # sometimes there is no primary key
    if not pkey_df.empty:
        # pg_get_constraintdef = postgres get constraint definition
        # Get the primary key constraint's definition
        pkey = pkey_df.pg_get_constraintdef.tolist()[0]

        # Remove excess junk to just get the primary key field names
        # split at the commas to get a nice neat python list
        pkey = re.sub(r"(PRIMARY\sKEY\s\()|(\))","",pkey).split(',')

        # remove whitespace from the edges
        pkey = [colname.strip() for colname in pkey]
        
    return pkey


def get_badrows(df_badrows):
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
            'value': val if not isnull(val) else '',
            # Individualized error message is mainly for the Lookup list error in core checks
            # All other checks have generic error messages, and in this case the error message doesnt need to be stored here,
            # Since this "message" key, value pair in the "rows" dictionary was for error messages which contain the 
            #  value the user entered
            'message': ""
        } 
        for rownum, val in
        df_badrows \
        .apply(
            lambda row:
            (
                row.name,

                # We wont be including the specific cell value in the error message for custom checks, 
                # it would be too complicated to implement in the cookie cutter type fashion that we are looking for, 
                # since the cookie cutter model that we have with the other checker proved effective for faster onboarding of new people to writing their own checks. 
                # Plus in my opinion, the inclusion of the specific value is really mostly helpful for the lookup list error. 
                # The only reason why the dictionary still includes this item is for the sake of consistency - 
                # (all the other "badrows" dictionaries are formatted in this way, since there are a few error types in core checks where the specific cell value was included.) 
                # This is ok since Core checks is 99.9% not going to change or have any additional features added, 
                # thus we dont need to make it super convenient for others to add checks

                # Note that for this "get_badrows" function, it works essentially the same way as the previous checker, 
                # where the user basically provides a line of code to subset the dataframe, along with an accompanying error message
                None
            ),
            axis = 1
        ) \
        .values
    ]