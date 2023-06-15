import re
from pandas import isnull, read_sql, concat
from .functions import checkData, coalesce, get_primary_key
from flask import current_app

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

    # For duplicates within session, dataprovider is not necessary to check
    # Since it is assumed that all records within the submission are from the same dataprovider
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


