import re
from pandas import isnull, read_sql, concat
from .functions import checkData, coalesce, get_primary_key
from flask import current_app, session

# All the functions for the Core Checks should have the dataframe and the datatype as the two main arguments
# This is to allow the multiprocessing to work, so it can pass in the same args to all the functions
# Of course it would be possible to do it otherwise, but the mutlitask function we wrote in utils assumes 
# the case that all of the functions have the same arguments
def checkDuplicates(dataframe, tablename, eng, *args, output = None, **kwargs):
    """
    check for duplicates in session only
    """
    print("BEGIN function - checkDuplicates")
    
    pkey = get_primary_key(tablename, eng)

    # We dont want the primary key columns to be part of the system fields
    # reduce the primary key to be those not found in the system fields
    pkey = [col for col in pkey if col not in current_app.system_fields]

    # initialize return value
    ret = []

    if len(pkey) == 0:
        print("No Primary Key")
        return ret

    if any(dataframe.duplicated(pkey)):

        badrows = [
            {
                'row_number': rownum,
                'objectid': objid,
                'value': coalesce(val),
                'message': msg
            }
            for rownum, objid, val, msg in
            dataframe[dataframe.duplicated(pkey, keep = False)].apply(
                lambda row:
                (
                    row.name + 1,
                    row['objectid'],
                    None,
                    'This is a duplicated row'
                ),
                axis = 1
            ).values
        ]
        ret = [
            checkData(
                dataframe = dataframe,
                tablename = tablename,
                badrows = badrows,
                badcolumn = ','.join(pkey),
                error_type = "Duplicated Rows",
                is_core_error = True,
                error_message = "You have duplicated rows{}".format( 
                    f" based on the primary key fields {', '.join(pkey)}"
                )
            )
        ]

        if output:
            output.put(ret)

        
    print("END function - checkDuplicates")
    return ret

def checkDuplicatesInProduction(dataframe, tablename, eng, *args, output = None, **kwargs):
    """
    check for duplicates in Production only
    """
    print("BEGIN function - checkDuplicatesInProduction")
    
    pkey = get_primary_key(tablename, eng)
    print(pkey)
    
    # initialize return values
    ret = []

    if len(pkey) == 0:
        print("No Primary Key")
        return ret

    # The current records selected will be based on submissionid that is not a part of the session submission. The query is specifically for all records with a submissionid that 
    # is not selected from session. This is to prevent the addition and deletion of records to and from the database when submitting the change request.
    # The session submissionid is omitted from the query because there will be records that exist in the database with the same primary key as the data dropped for the change request.
    current_recs = read_sql(f"SELECT DISTINCT {','.join(pkey)} FROM {tablename} WHERE submissionid != {session.get('submissionid')}", eng)
    
    
    import time
    print("are there current_recs in the database?")
    print(not current_recs.empty)
    time.sleep(1)
    if not current_recs.empty:

    
        for dt in list(zip(current_recs.dtypes.index, current_recs.dtypes)):
            col = dt[0]
            typ = dt[1]
            assert len(dt) > 1, "Error in dupes - some item in current_recs.dtypes didnt have a length greater than 1"
            assert col in dataframe.columns, f"supposed primary key column {col} not found in columns of the dataframe that was matched with {tablename}"

            try:
                # Coerce datatypes of primary key columns to match so that the two dataframes can merge 
                if typ == 'object':
                    dataframe[col] = dataframe[col].astype(typ).apply(lambda x: str(x).strip())
                    current_recs[col] = current_recs[col].astype(typ).apply(lambda x: str(x).strip())
                else:
                    dataframe[col] = dataframe[col].astype(typ)
            except Exception as e:
                # An exception should only occur if the column was not able to be coerced to the correct datatype, in which case the datatypes check should have caught it
                print(e)
                if output:
                    output.put(ret)
                return ret
                

        # tack on a column to identify records that have been prviously submitted
        current_recs = current_recs.assign(already_in_db = True)

        # merge current recs with a left merge and tack on that "already_in_db" column
        dataframe = dataframe.merge(current_recs, on = pkey, how = 'left')
        dataframe.already_in_db = dataframe.already_in_db.fillna(False)
        # originally
        #badrows = dataframe[dataframe.already_in_db == True].index.tolist() 
        # replace with list of dictionaries, refer to checkDuplicates function above

        # might need to add the if condition before this 

        badrows = [
            {
                'row_number': rownum,
                'objectid': objid,
                'value': coalesce(val),
                'message': msg
            }
            for rownum, objid, val, msg in
            dataframe[dataframe.already_in_db].apply(
                lambda row:
                (
                    row.name + 1,
                    row['objectid'],
                    None,
                    'This is a duplicated row'
                ),
                axis = 1
            ).values
        ]

        print("badrows")
        print(badrows)
        
        print("tablename")
        print(tablename)
        time.sleep(1)

        ret = [
            checkData(
                dataframe = dataframe,
                tablename = tablename,
                badrows = badrows,
                badcolumn = ','.join([col for col in pkey if col not in current_app.system_fields]),
                error_type = "Duplicate",
                is_core_error = True,
                error_message = "This is a record which already exists in the database"
            )
        ]

        if output:
            output.put(ret)

        
    print("END function - checkDuplicatesInProduction")
    return ret

