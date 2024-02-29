########################################
# This file contains the diff function #
########################################
import os
import pandas as pd
import numpy as np
from flask import Blueprint, request, jsonify, session, current_app, g
from flask_login import login_required
from werkzeug.utils import secure_filename
from copy import deepcopy

# Custom Imports
from .utils.comparison import highlight_changes, compare
from .utils.html import htmltable
from .utils.mail import send_mail
from .utils.db import get_primary_key, get_pkey_constraint_name
from .utils.generic import ordered_columns, history_log_converter
from .core import core
from .custom import *

# To view all data in print statements when debugging
pd.set_option('display.max_columns', None)



###############################################################
# These routes are set up for javascript to fetch information #
###############################################################

comparison = Blueprint('comparison', __name__)
@comparison.route("/compare", methods = ['GET', 'POST'])
@login_required
def main():

    eng = current_app.eng

    # routine to grab the uploaded file
    files = request.files.getlist('files[]')
    print("files")
    print(files)
    if len(files) > 1:
        return "cannot upload multiple files"
    elif len(files) == 1:
        # i'd like to figure a way we can do it without writing the thing to an excel file
        f = files[0]
        filename = secure_filename(f.filename)
        changed_data_path = f'{os.getcwd()}/files/{filename}'
        f.save(changed_data_path)
        # the user's uploaded excel file can now be read into pandas

        # df_modified will be the data the user uploaded
        # I think result and mdl are read in as object since they are character fields in the SMC database
        df_modified = pd.read_excel(changed_data_path, dtype={'result': object, 'mdl': object}, keep_default_na = False, na_values = [''])

        # flush the temporary table if they give us a new file
        eng.execute("DELETE FROM tmp.{};".format(session['modified_tablename']))

    else:
        print("No file given")
        df_modified = pd.DataFrame.from_records(request.get_json())
        df_modified.replace('', np.NaN, inplace = True)


    # Code expects this column to exist
    # NOTE I have edited the code to always overwrite the user's submitted objectid column with the dataframe index
    # The reason was that i submitted data with duplicated objectid's, due to copy pasting rows, and the app crashed trying to put that in the tmp table
    # 8/2/2023 - Robert
    df_modified['objectid'] = df_modified.index


    # df_modified needs to have the object id's filled in
    print("# df_modified needs to have the object id's filled in")
    maxobjid = df_modified.objectid.max()
    df_modified.objectid = df_modified.apply(lambda row: row.name + maxobjid + 1 if pd.isnull(row.objectid) else row.objectid, axis = 1)
    df_modified.objectid = df_modified.objectid.astype(int)
    
    # Remember tablenames is a global variable of key value pairs (dictionary)
    # with keys being the datatype and the values being the corresponding table(s)
    # eventually this will become painful when/if the changes are done on the tbl tables
    tablename = session.get('tablename')
    
    # Get the merging columns (primarykeys of the table based on tablename)
    # session['primary_key'] = pkey_columns
    pkey_columns = get_primary_key(tablename, eng)

    # We need to have a well defined primary key, otherwise, we cant process changes for the table
    assert len(pkey_columns) > 0, f"There is no primary key for the table {tablename}"




    # ------------------------------------------------ CORE CHECKS ---------------------------------------------------------#
    # Here we'll attempt to check the data 
    # First, we run Core checks, load records that pass, display bad records in the browser 
    # if all records pass core checks and are loaded to their tmp table, we will run custom checks
    

    errors = [] # start fresh every time they attempt a change
    warnings = [] # start fresh every time they attempt a change

    # Run checks
    # soon we will want to run this on the entire submission, not just the modified records
    # Core Checks function throws the errors in the session variable, where we will access them here
    
    # We are running core checks on a deepcopy of the dataframe (df_modified) - 
    #  because for some reason, it was modifiying the df_modified object and messing with it even outside the scope of the function, 
    #  i have no idea why
    #  This is related to issue #26 on github
    core_output = core(df = deepcopy(df_modified), tblname = session.get('tablename'), eng = g.eng, debug = True)
    

    errors = [*errors, *core_output.get('core_errors')]
    warnings = [*warnings, *core_output.get('core_warnings')]

    
    badrows = set([r['row_number'] for e in errors for r in e['rows']])
    errors_dataframe = df_modified[df_modified.index.isin([n - 1 for n in badrows])]
    good_dataframe = df_modified[~df_modified.index.isin([n - 1 for n in badrows])]
    
    
    # Records that pass Core checks can go  into the database without integrity errors.
    # Load those records to their table while returning their problematic records for them to examine and possibly edit.
    mod_tbl_pkey_constraint_name = get_pkey_constraint_name(session['modified_tablename'], eng, 'tmp')
    
    # if no primary key constraint name is found, that's a problem
    assert mod_tbl_pkey_constraint_name != '', f"""ERROR - No primary key constraint name found for the modified table {session['modified_tablename']}"""
    
    # Get actual primary key columns
    mod_tbl_pkey_cols = get_primary_key(session['modified_tablename'], eng)
    assert mod_tbl_pkey_cols != [], f"""ERROR - No primary key found for the modified table {session['modified_tablename']}"""
    
    goodrecords_sql = \
        """
        INSERT INTO tmp.{} 
        ({}) 
        VALUES {} 
        ON CONFLICT ON CONSTRAINT {} DO UPDATE SET {}
        """ \
        .format(
            session['modified_tablename'], 
            ','.join(good_dataframe.columns),
            ',\n'.join(
                "({})" \
                .format(
                    ', '.join(
                        [
                            'NULL'
                            if ( (str(i).strip() == '') or (pd.isnull(i)) )
                            else str(i).strip()
                            if ( (isinstance(i, (float, int))) or ("sde.next_" in str(i)) )
                            else "E'{}'".format(str(i).replace("'","\\'").replace('"','\\"')) if (("'" in str(i)) or ('"' in str(i)))
                            else "'{}'".format(str(i))
                            for i in x
                        ]
                    )
                )
                for x in 
                list(zip(*[good_dataframe[c] for c in good_dataframe.columns]))
            ),
            mod_tbl_pkey_constraint_name,
            ',\n'.join([f"{colname} = EXCLUDED.{colname}" for colname in good_dataframe.columns if colname not in [*mod_tbl_pkey_cols, 'objectid']])
        ) \
        .replace("%","%%")

    if not good_dataframe.empty:
        eng.execute(goodrecords_sql)


    # distinguish an accepted change from a rejected change based on errors
    # its a rejected change if we find that change in the errors
    rejected_changes = [
        {
            'rownumber': r['row_number'], 
            'colname': e['columns'], 
            'objectid': r['objectid']
        } 
        for e in errors for r in e['rows']
    ]

    # If there were errors, stop them here.
    # We put their good records to their tmp table already, here we will return to them their problematic records for them to examine and possibly edit
    if not errors_dataframe.empty:
        # order the columns
        errors_dataframe = errors_dataframe[ordered_columns(errors_dataframe, session.get('column_order'))]
        
        return jsonify(
            tbl = htmltable(errors_dataframe, _id = "changes-display-table"),
            # make added and deleted records show up in the browser as empty tables - we dont concern ourselves with any of that until they fix their errors
            addtbl = htmltable(errors_dataframe.drop(errors_dataframe.index), editable = False),
            deltbl = htmltable(errors_dataframe.drop(errors_dataframe.index), editable = False), 
            changed_indices = rejected_changes, 
            accepted_changes = [], 
            rejected_changes = rejected_changes, 
            errors = errors
        )
    # ------------------------------------------------ END CORE CHECKS ---------------------------------------------------------#

    # Get their original submission data from the tmp table that was created and populated from the time they logged in
    # (The time they selected the login fields associated with their submission that they are editing, and a submissionid was selected)
    df_origin = pd.read_sql(f"SELECT {','.join(session['submission_colnames'])} FROM tmp.{session['origin_tablename']} ORDER BY objectid", eng) \
        .replace('',np.NaN) \
        .replace('NA',np.NaN) \
        .replace("'=","=") # For resqualcode

    
    # Get the current modified submission
    # After this, we run custom checks on the entirety of their submission
    # entirity? entirety? however its spelled...
    df_modified = pd.read_sql(f"SELECT {','.join(session['submission_colnames'])} FROM tmp.{session['modified_tablename']} ORDER BY objectid", eng) \
        .replace('',np.NaN) \
        .replace('NA',np.NaN) \
        .replace("'=","=") # For resqualcode



    # ---------------------------------------------- CUSTOM CHECKS ROUTINE ------------------------------------------------- #
    # Core checks only needs to be run on the data given, to see if it may go into the database. 
    # Custom checks, however, needs to run on their entire submission. 
    # For this reason, we first wait for all the data to be loaded to the table (modified records table) and then run custom checks on that entire dataframe

    if errors == []:
        # custom checks
        try:
            # Print the custom checks function name
            print(current_app.dtypes.get(session.get('dtype')).get('custom_checks_functions').get(session.get('tablename')))
            
            # eval on the string of the function name should return the actual function, and it will be stored in the variable "custom_check_func" and get called later
            custom_check_func = eval(current_app.dtypes.get(session.get('dtype')).get('custom_checks_functions').get(session.get('tablename')))
        
        except Exception as e:
            # To be honest this error should only occur if the app is misconfigured, so i should probably just go with assert statements to enforce this
            raise Exception(f"In main.py - unable to get the custom checks function: {e}")

        # run custom checks
        custom_output = custom_check_func(df_modified, session.get('tablename'))
        errors = [*errors, *custom_output.get('errors')]
        warnings = [*warnings, *custom_output.get('warnings')]

        # distinguish an accepted change from a rejected change based on errors
        # its a rejected change if we find that change in the errors
        rejected_changes = [
            {
                'rownumber': r['row_number'], 
                'colname': e['columns'], 
                'objectid': r['objectid']
            } 
            for e in errors for r in e['rows']
        ]
        print(errors)
    
        # Same routine as was applied for core checks
        # display problem records in the browser for them to examine and edit
        # It may also be beneficial in the future to send them to the checker app and let them know they can check data without submitting, 
        #   if they want a more detailed and intuitive error report.
        badrows = set([r['row_number'] for e in errors for r in e['rows']])
        errors_dataframe = df_modified[df_modified.index.isin([n - 1 for n in badrows])]
        good_dataframe = df_modified[~df_modified.index.isin([n - 1 for n in badrows])]

        # order the columns
        errors_dataframe = errors_dataframe[ordered_columns(errors_dataframe, session.get('column_order'))]
        good_dataframe = good_dataframe[ordered_columns(good_dataframe, session.get('column_order'))]

        if not errors_dataframe.empty:
            return jsonify(
                tbl = htmltable(errors_dataframe, _id = "changes-display-table"),
                # make added and deleted records show up in the browser as empty tables - we dont concern ourselves with any of that until they fix their errors
                addtbl = htmltable(errors_dataframe.drop(errors_dataframe.index), editable = False),
                deltbl = htmltable(errors_dataframe.drop(errors_dataframe.index), editable = False), 
                changed_indices = rejected_changes, 
                accepted_changes = [], 
                rejected_changes = rejected_changes, 
                errors = errors
            )
    # ------------------------------------------- END CUSTOM CHECKS ROUTINE ----------------------------------------------- #



    # Here we run the comparison function - the heart and soul of the change app
    # There are some tables where numeric values are stored as text - not sure why. But the app does not like that.
    # The workaround is to specify such columns in the application's configuration
    # Then here, we go and access it from the config and pass to the comparison function so it knows which columns to treat as numeric
    #    (because it will think it is text by default)
    special_numeric_cols = current_app.dtypes.get(session.get("dtype")).get("special_numeric_columns", [])
    
    added_records, deleted_records, modified_records, changed_indices, original_data = \
        compare(df_origin, df_modified, pkey_columns, current_app.immutable_fields, special_numeric_cols)
    
    print("Done with Comparison routine")

    # Need to make sure the objectid's are integers, but not the added records, since those have next_rowid
    modified_records.objectid = modified_records.objectid.astype(int)
    deleted_records.objectid  = deleted_records.objectid.astype(int)

    # order the records based on the objectid
    # cant do it for the additional records since those may not have objectid's associated with them
    # even if they do, they get trashed
    modified_records = modified_records.sort_values('objectid')
    deleted_records = deleted_records.sort_values('objectid')
    
    
    
    # distinguish an accepted change from a rejected change based on errors
    # its a rejected change if we find that change in the errors
    print("# distinguish an accepted change from a rejected change based on errors")
    rejected_changes = [
        x for x in changed_indices if 
        (x['rownumber'], x['colname']) in [(r['row_number'], e['columns']) for e in errors for r in e['rows']]
    ]
    accepted_changes = [x for x in changed_indices if x not in rejected_changes]

    # chnaged_indices is a list of dictionaries containing:
    # The objectid, column name and row index (on the dataframe) of the change


    ##################################
    # --  Generate SQL statements -- #
    ##################################

    print("# Make a dataframe so we can groupby objectid and tablename")
    # Make a dataframe so we can groupby objectid and tablename
    # hislog = History Log
    
    assert \
        all([item['objectid'] in modified_records.objectid.values for item in accepted_changes]), \
        "ObjectID of an accepted change was not found among the objectID's of the modified records"
    
    # History log for accepted changes
    hislog_accepted_changes = pd.DataFrame({
        'objectid'     :   [int(item['objectid']) for item in accepted_changes],
        'tablename'    :   tablename,
        'changed_cols' :   [item['colname'] for item in accepted_changes],
        'newvalue'     :   [
            modified_records[modified_records['objectid'] == item['objectid']][f"{item['colname']}"].values[0]
            for item in accepted_changes
        ]   
    })
    
    # History log of rejected changes - not to be used until we highlight the excel files
    hislog_rejected_changes = pd.DataFrame({
        'objectid'     :   [int(item['objectid']) for item in rejected_changes],
        'tablename'    :   tablename,
        'changed_cols' :   [item['colname'] for item in rejected_changes],
        'newvalue'     :   [
            modified_records[modified_records['objectid'] == item['objectid']][f"{item['colname']}"].values[0]
            for item in rejected_changes
        ]   
    })
    
    if not hislog_accepted_changes.empty:

        print("# 4 iterations of the for loop. Probably doesn't make a difference doing it this way or with map")
        # 4 iterations of the for loop. Probably doesn't make a difference doing it this way or with map
        for col in hislog_accepted_changes.columns:

            # The items are converted to strings to make it easier to put everything into the sql statements, files, etc
            # Often they complain about different datatypes numpy.float64's numpy.int64's etc.

            # Apply the conversion function to the column
            # history_log_converter imported from utils.generic
            hislog_accepted_changes[col] = hislog_accepted_changes[col].apply(history_log_converter)
        

        # Creating the SQL statement to update records
        print("history log")
        hislog = hislog_accepted_changes \
            .groupby(["objectid","tablename"]) \
            .apply(
                # Set to NULL if they deleted the value
                lambda subdf: " , ".join(
                    f"{x[0]} = '{x[1]}'" if ( (x[1] != '') and (not pd.isnull(x[1])) ) else f"{x[0]} = NULL" for x in zip(subdf.changed_cols, subdf.newvalue)
                )
            ) \
            .reset_index() \
            .rename(columns = {0: 'changes'}) \
            .apply(
                lambda x: 
                f"update {x['tablename']} \
    set {x['changes']}, \
    last_edited_date = '{pd.Timestamp(session['sessionid'], unit = 's').strftime('%Y-%m-%d %H:%M:%S')}', \
    last_edited_user = '{session['session_user_email']}' \
    WHERE objectid = {x['objectid']}"
                , axis=1
            )
        
        print("hislog")
        print(hislog)

        hislog = hislog.tolist() if isinstance(hislog, pd.Series) else []

        # view_changed_records_sql is in response to Zaib's request to view the data before committing the transaction
        view_changed_records_sql = """
                SELECT * FROM {} 
                WHERE objectid IN (
                    {}
                );
            """ \
            .format(
                session.get('tablename'),
                
                # joining objectids by newlines because there seemed to be strange behavior in writing them all on one line
                # when a large number of records were modified, it seemed to add a newline randomly without our permission about 1000 characters in
                # so the workaround is to just join each objectif by a comma and newline
                # also, we have to convert them to integers in order to sort correctly, and then put them back to strings,
                #  so that the join function gets what it expects
                ",\n".join(hislog_accepted_changes.objectid.astype(int).sort_values().astype(str).unique())
            )
        
    else:
        hislog = []
        view_changed_records_sql = f" -- No Changed Records -- "

    print("hislog")
    print(hislog)
    

    print("After generating the update statements, generate the SQL for adding records")
    # After generating the update statements, generate the SQL for adding records
    # We are tacking on the system fields because those will need to be included in the SQL statement 
    # However, we will remove them after the SQL is generated, so that they are not displayed to the user

    added_records['created_user'] = "change request app"
    added_records['created_date'] = pd.Timestamp(session['sessionid'], unit = 's').strftime("%Y-%m-%d %H:%M:%S")
    for k in session.get('login_fields').keys():
        added_records[f'login_{k}'] = session.get('login_fields').get(k)
    added_records['last_edited_user'] = session["session_user_email"]
    added_records['last_edited_date'] = pd.Timestamp(session['sessionid'], unit = 's').strftime("%Y-%m-%d %H:%M:%S")
    added_records['objectid'] = f"""sde.next_rowid('sde','{tablename}')"""

    # If for some reason, the email wasnt part of the login form, then the login email wont be in the added records dataframe
    # Here we make sure the record has the original login_email for the submission
    if 'login_email' not in added_records:
        # added_records['login_email'] = session["session_user_email"]
        login_email = pd.read_sql(f"SELECT DISTINCT login_email FROM submission_tracking_table WHERE submissionid = {session.get('submissionid')}", current_app.eng).values
        assert len(login_email) > 0 , f"login_email not found for submissionid {session.get('submissionid')}"
        added_records['login_email'] = login_email[0]
        
    added_records['submissionid'] = session.get('submissionid')

    dbcols = pd.read_sql(f"SELECT column_name FROM information_schema.columns WHERE table_name = '{tablename}';", eng).column_name.tolist()
    added_records = added_records[list(set(added_records.columns).intersection(set(dbcols)))]

    add_records_sql = """INSERT INTO {} \n({}) \nVALUES {}""" \
        .format(
            tablename, 
            ', '.join(added_records.columns),
            ',\n'.join(
                "({})" \
                .format(
                    ', '.join(
                        [
                            'NULL'
                            if ( (str(i).strip() == '') or (pd.isnull(i)) )
                            else str(i).strip()
                            if ( (isinstance(i, (float, int))) or ("sde.next_" in str(i)) )
                            else "'{}'".format(str(i).replace("'","").replace('"',""))  
                            for i in x
                        ]
                    )
                )
                for x in 
                list(zip(*[added_records[c] for c in added_records.columns]))
            )
        ) \
        .replace("%","%%") \
        if not added_records.empty \
        else ' -- (No Added Records) -- ' 

    # Now get the SQL for deleting records, which is a lot less complicated (Just need objectids of those records being deleted)
    # if no deleted records, just make the delete records SQL an empty string so that nothing goes in the SQL file
    print("Now get the SQL for deleting records, which is a lot less complicated")
    delete_records_sql = "DELETE FROM {} WHERE objectid IN (\n{}\n)" \
        .format(
            tablename,
            ',\n\t'.join([str(int(x)) for x in deleted_records.objectid.tolist()])
        ) \
        if not deleted_records.empty \
        else ' -- (No Deleted Records) -- '


    #######################################
    # --  Write to Excel and SQL files -- #
    #######################################

    # Later should be done with os.path.join
    sql_filepath = f"{os.getcwd()}/files/{session['sessionid']}.sql"
    # Write hislog to a SQL file
    with open(sql_filepath, 'w') as f:
        f.write('BEGIN;\n')
        f.write("-- CHANGED RECORDS --\n")
        f.write(';\n'.join(hislog))
        f.write("\n;\n\n")
        f.write("-- ADDED RECORDS --\n")
        f.write(add_records_sql)
        f.write("\n;\n\n")
        f.write("-- DELETED RECORDS --\n")
        f.write(delete_records_sql)
        f.write("\n;\n\n")
        f.write("-- View changed data before transaction commit:\n")
        f.write(view_changed_records_sql)
        f.write("\n\n")
        f.write(f"-- Change History Table Update - run when the change has been processed and finalized -- \n")
        f.write(f"UPDATE {os.environ.get('CHANGE_HISTORY_TABLE')} SET change_processed = 'Yes' WHERE change_id = {session['sessionid']} RETURNING *; --\n")
        f.write('COMMIT;\n')
        f.close()
    
    session['sql_filepath'] = sql_filepath
    
    # make sure the highlighted excel file directory actually exists
    highlight_dir = os.path.join(os.getcwd(), 'export', 'highlightExcelFiles')
    if not os.path.exists(highlight_dir):
        os.makedirs(highlight_dir)
    
    # Later should be done with os.path.join
    path_to_highlighted_excel =  f"{os.getcwd()}/export/highlightExcelFiles/comparison_{session['sessionid']}.xlsx"
    session['comparison_path'] = path_to_highlighted_excel


    print("writing report to excel")
    # This needed to be put in a "with" block so that it automatically saves
    # writer.save() is deprecated now (June 29, 2023)
    with pd.ExcelWriter(path_to_highlighted_excel, engine = 'xlsxwriter',  engine_kwargs={'options': {'strings_to_formulas': False}}) as writer:

        original_data =  original_data[ ['objectid'] + [c for c in original_data.columns if c not in ['objectid', *current_app.system_fields]  ] ]
        modified_records =  modified_records[ ['objectid'] + [c for c in modified_records.columns if c not in ['objectid', *current_app.system_fields]  ] ]
        deleted_records =  deleted_records[ ['objectid'] + [c for c in deleted_records.columns if c not in ['objectid', *current_app.system_fields]  ] ]
        added_records = added_records[ ['objectid'] + [c for c in added_records.columns if c not in ['objectid', *current_app.system_fields]  ] ]
        
        # after removing the system fields, order tables according to the column_order
        original_data =  original_data[ ordered_columns(original_data, session.get('column_order')) ]
        modified_records =  modified_records[ ordered_columns(modified_records, session.get('column_order')) ]
        deleted_records =  deleted_records[ ordered_columns(deleted_records, session.get('column_order')) ]
        added_records = added_records[ ordered_columns(added_records, session.get('column_order')) ]

        # added records objectid is a function call to the next_rowid function
        # This shouldnt be displayed to the user
        added_records = added_records.assign(objectid = -220)
        
        # Write them to the "comparison" excel file (the change summary)
        original_data.to_excel(writer, sheet_name = "Original", index = False)
        modified_records.to_excel(writer, sheet_name = "Modified", index = False)
        added_records.to_excel(writer, sheet_name = "Added", index = False)
        deleted_records.to_excel(writer, sheet_name = "Deleted", index = False)

        # Coloring the changed cells
        print('# Coloring the changed cells')
        workbook = writer.book
        rejected_color = workbook.add_format({'bg_color':'#FF0000'})
        accepted_color = workbook.add_format({'bg_color':'#42f590'})
        worksheet = writer.sheets["Modified"]

        # the variables below which are used for marking the excel file 
        #   (hislog_accepted_changes and hislog_rejected_changes)
        #   were defined above - before the part that generates the SQL statements for updating the data

        # make objectid an int just in case it turned into a float somehow
        print('# make objectid an int just in case it turned into a float somehow')
        modified_records.objectid = modified_records.objectid.astype(int)
        hislog_accepted_changes.objectid = hislog_accepted_changes.objectid.astype(int)
        hislog_rejected_changes.objectid = hislog_rejected_changes.objectid.astype(int)

        # get the accepted change cells, according to the location in the excel file
        print('# get the accepted change cells, according to the location in the excel file')
        # Basically we are translating the objectid and column name to the excel row/column index
        print('# Basically we are translating the objectid and column name to the excel row/column index')
        accepted_highlight_cells = modified_records \
            .assign(excel_row_index = modified_records.index + 1) \
            .merge(
                hislog_accepted_changes,
                on = ['objectid'],
                how = 'inner'
            )

        if not accepted_highlight_cells.empty:
            # now the dataframe has excel row, objectid, and changed column name
            print('# now the dataframe has excel row, objectid, and changed column name')
            accepted_highlight_cells['excel_col_index'] = accepted_highlight_cells.changed_cols.apply(
                lambda c: modified_records.columns.get_loc(c)
            )
            accepted_highlight_cells = accepted_highlight_cells.apply(
                lambda row: (row.excel_row_index, row.excel_col_index), axis = 1
            ).tolist()
        else:
            accepted_highlight_cells = []

        # Now get the rejected cells
        print('# Now get the rejected cells')
        rejected_highlight_cells = modified_records \
            .assign(excel_row_index = modified_records.index + 1) \
            .merge(
                hislog_rejected_changes, 
                on = ['objectid'], 
                how = 'inner'
            )
        
        if not rejected_highlight_cells.empty:
            # now the dataframe has excel row, objectid, and changed column name
            print('# now the dataframe has excel row, objectid, and changed column name')
            rejected_highlight_cells['excel_col_index'] = rejected_highlight_cells.changed_cols.apply(
                lambda c: modified_records.columns.get_loc(c)
            )
            rejected_highlight_cells = rejected_highlight_cells.apply(
                lambda row: (row.excel_row_index, row.excel_col_index), axis = 1
            ).tolist()
        else:
            rejected_highlight_cells = []


        # highlight changes is defined in utils
        # Made it a function since later we likely will distinguish between highlighting an accepted change vs a rejected change, which will have different formatting
        # cells arg here should be a tuple of numbers. xlsxwriter can highlight based on coordinates of the cell, not column names
        # NOTE Soon there will be two of these - one for accepted changes (green) and another for rejected changes (red)
        # (Above note may have been resolved - June 29, 2023)
        
        # NOTE I think i also want to somehow include the warnings - that would be something that would take a lot longer to implement.
        # For sure something to add after we get a basic functioning app that is ready for outside people to use
        highlight_changes(
            worksheet = worksheet, color = accepted_color, cells = accepted_highlight_cells
        )
        highlight_changes(
            worksheet = worksheet, color = rejected_color, cells = rejected_highlight_cells
        )
    
    print("Successfully wrote to Excel")

    print("modified_records")
    print(modified_records)
    print("added_records")
    print(added_records)
    print("deleted_records")
    print(deleted_records)
    return jsonify(
        tbl = htmltable(modified_records, _id = "changes-display-table"), 
        addtbl = htmltable(added_records, editable = False),
        deltbl = htmltable(deleted_records, editable = False), 
        changed_indices = changed_indices, 
        accepted_changes = accepted_changes, 
        rejected_changes = rejected_changes, 
        errors = errors
    )


@comparison.errorhandler(Exception)
def default_error_handler(error):
    print("Checker application came across an error...")
    try:
        print(str(error).encode('utf-8'))
    except Exception:
        print("Couldnt print the error to the console")
    
    print("current_app.config.get('MAIL_SERVER')")
    print(current_app.config.get('MAIL_SERVER'))

    response = jsonify({'code': 500,'message': str(error)})
    response.status_code = 500
    # need to add code here to email SCCWRP staff about error
    send_mail(
            current_app.send_from,
            [
                *current_app.maintainers
            ],
            'Data Change Request Error',
            "{} (sessionid {}) came accross an error:\n\t{}\n\n\nSession Info:\n\t{}".format(
                str(session.get('session_user_email')),
                session.get('sessionid'),
                str(error)[:500],
                '\n\n\t'.join([f"{k}: {session.get(k)}" for k in session.keys()])
            ),
            files = [str(session.get('comparison_path'))],
            server = current_app.config.get('MAIL_SERVER')
        )
    return response