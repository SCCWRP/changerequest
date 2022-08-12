import pandas as pd
from .functions import checkData, get_badrows
from flask import current_app, session, request

# q is a multiprocessing.Queue()
# pass it in in the case that this is done with multiprocessing
# multitask function passes in a multiprocessing Queue() as the last argument for each function that gets passed into it
# therefore to pass a function to the multitask function we would need to allow for that queue to be passed into it
def checkLookUpLists(dataframe, tablename, eng, dtype, *args, output = None, **kwargs):
    print("BEGIN checkLookupLists")
    #assert dtype in tbl_tablenames.keys(), "Invalid Datatype in checkLookUpCodes function call"
    
    # The script root shouldnt need to be hard coded into some configuration
    # It should be accessible off the "request" object, request.script_root
    
    script_root = request.script_root

    lookup_sql = f"""
        SELECT
            kcu.column_name, 
            ccu.table_name AS foreign_table_name,
            ccu.column_name AS foreign_column_name 
        FROM 
            information_schema.table_constraints AS tc 
            JOIN information_schema.key_column_usage AS kcu
            ON tc.constraint_name = kcu.constraint_name
            AND tc.table_schema = kcu.table_schema
            JOIN information_schema.constraint_column_usage AS ccu
            ON ccu.constraint_name = tc.constraint_name
            AND ccu.table_schema = tc.table_schema
        WHERE tc.constraint_type = 'FOREIGN KEY' 
        AND tc.table_name='{tablename}'
        AND ccu.table_name LIKE 'lu_%%';
    """

    # fkeys = foreign keys
    fkeys = pd.read_sql(lookup_sql, eng)
    # dont check lookup lists for columns that are not in unified table
    fkeys = fkeys[fkeys.column_name.isin(dataframe.columns)]
    # print("fkeys")
    # print(fkeys)
    # print("lookup_sql")
    # print(lookup_sql)


    out = fkeys.apply(
        lambda x: 
        checkData(
            dataframe = dataframe,
            tablename = session.get('tablename'),
            # dtype = dtype,
            badrows = [
                {
                    'row_number': rownum,
                    'objectid': objid,
                    'value': val if not pd.isnull(val) else str(val),
                    'message': msg
                } 
                for rownum, objid, val, msg in
                    dataframe[
                        # Exclude null values from lookup list check
                        ~pd.isnull(dataframe[x['column_name']].replace('', pd.NA)) & 
                        (
                            ~dataframe[x['column_name']] \
                            .isin(
                                pd.read_sql(f"SELECT {x['foreign_column_name']} FROM {x['foreign_table_name']};", eng) \
                                [x['foreign_column_name']] \
                                .values
                            )
                        )
                    ] \
                    .apply(
                        lambda row:
                        (
                            row.name + 1,
                            row['objectid'],
                            row[x['column_name']], 
                            f"""The value you entered here ({row[x['column_name']]}) does not match the 
                            <a href=\\\"{script_root}/scraper?action=help&layer={x['foreign_table_name']}\\\"> 
                            Lookup List
                            </a>"""
                        ),
                        axis = 1
                    ) \
                    .values
            ],
            badcolumn = x['column_name'],
            error_type = "Lookup List Fail",
            is_core_error = True,
            error_message = f"Item not in the <a href=\"{script_root}/scraper?action=help&layer={x['foreign_table_name']}\" target=\"blank\">Lookup List</a>",
            q = output
        ) 
        if not 
            dataframe[
                ~dataframe[x['column_name']] \
                .isin(
                    pd.read_sql(f"SELECT {x['foreign_column_name']} FROM {x['foreign_table_name']};", eng) \
                    [x['foreign_column_name']] \
                    .values
                )
            ].empty
        else
            {}
        , axis = 1
    )

    out = out.tolist() if len(out) > 0 else []


    if output:
        output.put(out)

    print("END checkLookupLists")
    return out