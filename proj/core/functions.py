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

        # if the type is an int, and it got this far, at least the literal matches that of a number
        # if it matches the float pattern though, we have a problem
        if (t == int):

            # remove negative sign
            # remove decimal part if all zeros, retain if there is a non zero digit
            # then call the isdigit method to see if all values in the string are digits, thus meaning it is an integer value
            return re.sub(r'\.0*$','',(str(x)[1:] if str(x).startswith('-') else str(x))).isdigit()
            
            # floatpat = re.compile(r"^\d+\.0*[1-9]+")
            # # If it matches a float we want to return False
            # return not bool(re.match(floatpat, str(x)))
        
        if t == pd.Timestamp:
            # checking for a valid postgres timestamp literal
            # Postgres technically also accepts the format like "January 8 00:00:00 1999" but we won't be checking for that unless it becomes a problem
            datepat = re.compile("\d{4}-\d{1,2}-\d{1,2}\s*(\d{1,2}:\d{1,2}:\d{2}(\.\d+){0,1}){0,1}$")
            return bool(re.match(datepat, str(x)))
        
        return True
    except Exception as e:
        if t == pd.Timestamp:
            # checking for a valid postgres timestamp literal
            # Postgres technically also accepts the format like "January 8 00:00:00 1999" but we won't be checking for that unless it becomes a problem
            datepat = re.compile("\d{4}-\d{1,2}-\d{1,2}\s*(\d{1,2}:\d{1,2}:\d{2}(\.\d+){0,1}){0,1}$")
            return bool(re.match(datepat, str(x)))
        
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

    try:
        if not isinstance(x, (int, float)):
            x = float(str(x))
    except Exception as e:
        # If an exception occurs here, their data must be really messed up and we'll have to trust that checkDataTypes will flag it
        return True
    

    x = abs(x)
    
    if 0 < x < 1:
        # if x is a fraction, it doesnt matter. it should be able to go into a numeric field regardless
        return True
    left = int(log10(x)) + 1 if x > 0 else 1
    if 'e-' in str(x):
        # The idea is if the number comes in in scientific notation
        # it will look like 7e11 or something like that
        # We dont care if it is to a positive power of 10 since that doesnt affect the digits to the right
        # we care if it's a negative power, which looks like 7.23e-5 (.0000723)
        powerof10 = int(str(x).split('e-')[-1])
        
        # search for the digits to the right of the decimal place
        rightdigits = re.search("\.(\d+)",str(x).split('e-')[0])
        
        if rightdigits: # if its not a NoneType, it found a match
            rightdigits = rightdigits.groups()[0]
            right = powerof10 + len(rightdigits)
        else:
            right = 0
    else:
        # frac part is zero if there is no decimal place, or if it came in with scientific notation
        # because this else block represents the case where the power was positive
        
        frac_part = abs(int(re.sub("\d*\.","",str(x)))) if ( '.' in str(x) ) and ('e' not in str(x)) else 0
        
        # remove trailing zeros (or zeroes?)
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
    
    try:
        if not isinstance(x, (int, float)):
            x = float(str(x))
    except Exception as e:
        # If an exception occurs here, their data must be really messed up and we'll have to trust that checkDataTypes will flag it
        return True
    
    x = abs(x)
    if 'e-' in str(x):
        # The idea is if the number comes in in scientific notation
        # it will look like 7e11 or something like that
        # We dont care if it is to a positive power of 10 since that doesnt affect the digits to the right
        # we care if it's a negative power, which looks like 7.23e-5 (.0000723)
        powerof10 = int(str(x).split('e-')[-1])
        
        # search for the digits to the right of the decimal place
        rightdigits = re.search("\.(\d+)",str(x).split('e-')[0])
        
        if rightdigits: # if its not a NoneType, it found a match
            rightdigits = rightdigits.groups()[0]
            right = powerof10 + len(rightdigits)
        else:
            right = 0
    else:
        # frac part is zero if there is no decimal place, or if it came in with scientific notation
        # because this else block represents the case where the power was positive
        #print('HERE')
        #print(x)
        #print(str(x))
        frac_part = abs(int(re.sub("\d*\.","",str(x)))) if ( '.' in str(x) ) and ('e' not in str(x)) else 0
        #print('NO')
        
        # remove trailing zeros (or zeroes?)
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
    '''
    table is the tablename you want the primary key for
    eng is the database connection
    '''

    sql = f'''
        SELECT
            tc.TABLE_NAME,
            C.COLUMN_NAME,
            C.data_type 
        FROM
            information_schema.table_constraints tc
            JOIN information_schema.constraint_column_usage AS ccu USING ( CONSTRAINT_SCHEMA, CONSTRAINT_NAME )
            JOIN information_schema.COLUMNS AS C ON C.table_schema = tc.CONSTRAINT_SCHEMA 
            AND tc.TABLE_NAME = C.TABLE_NAME 
            AND ccu.COLUMN_NAME = C.COLUMN_NAME 
        WHERE
            constraint_type = 'PRIMARY KEY' 
            AND tc.TABLE_NAME = '{tablename}';
    '''

    return pd.read_sql(sql, eng).column_name.tolist()


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

def coalesce(val, default = ''):
    return val if not pd.isnull(val) else default