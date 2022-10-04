########################################
# This file contains the diff function #
########################################
from flask import Blueprint, request, jsonify, session, current_app, g
from flask_login import login_required
import pandas as pd
import numpy as np
from werkzeug.utils import secure_filename
from .utils.comparison import highlight_changes, compare
from .utils.html import htmltable
from .utils.mail import send_mail
from .utils.db import get_primary_key
from .core import core
from .custom import *
import os, sys



# # initialize session variable
# session['errors'] = {}
# goal is for the session['errors'] variable to look like this
# So we can store all errors in one place
"""
{
    "table": tablename,
    "dtype": dtype,
    "rows":badrows,
    "columns":badcolumn,
    "error_type":error_type,
    "core_error" : is_core_error,
    "error_message":error_message
}
"""

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
        df_modified = pd.read_excel(changed_data_path, dtype={'result': object, 'mdl': object})

        # flush the temporary table if they give us a new file
        eng.execute("DELETE FROM tmp.{};".format(session['modified_tablename']))

    else:
        print("No file given")
        df_modified = pd.DataFrame.from_records(request.get_json())
        df_modified.replace('', np.NaN, inplace = True)
        
        
    # Remember tablenames is a global variable of key value pairs (dictionary)
    # with keys being the datatype and the values being the corresponding table(s)
    # eventually this will become painful when/if the changes are done on the tbl tables
    tablename = session.get('tablename')
    
    # Get the merging columns (primarykeys of the table based on tablename)
    #session['primary_key'] = pkey_columns
    pkey_columns = get_primary_key(tablename, eng)

    # We need to have a well defined primary key, otherwise, we cant process changes for the table
    assert len(pkey_columns) > 0, f"There is no primary key for the table {tablename}"

    ########################################
    # Here we'll attempt to check the data #
    ########################################

    errors = [] # start fresh every time they attempt a change
    warnings = [] # start fresh every time they attempt a change

    # Run checks
    # soon we will want to run this on the entire submission, not just the modified records
    # Core Checks function throws the errors in the session variable, where we will access them here
    core_output = core(df = df_modified, tblname = session.get('tablename'), eng = g.eng, debug = True)

    errors = [*errors, *core_output.get('core_errors')]
    warnings = [*warnings, *core_output.get('core_warnings')]

    if errors == []:
        # custom checks
        try:
            custom_check_func = eval(current_app.dtypes.get(session.get('dtype')).get('custom_checks_functions').get(session.get('tablename')))
        except Exception as e:
            # To be honest this error should only occur if the app is misconfigured, so i should probably just go with assert statements to enforce this
            raise Exception(f"In main.py - unable to get the custom checks function: {e}")

        custom_output = custom_check_func(df_modified, session.get('tablename'))
        errors = [*errors, *custom_output.get('errors')]
        warnings = [*warnings, *custom_output.get('warnings')]


    print("df_modified")
    print(df_modified.columns)
    print(df_modified)

    # The check functions write to the session variable
    # errors = session['errors']
    print(errors)
    badrows = set([r['row_number'] for e in errors for r in e['rows']])
    errors_dataframe = df_modified[df_modified.index.isin([n - 1 for n in badrows])]
    good_dataframe = df_modified[~df_modified.index.isin([n - 1 for n in badrows])]
    print('good_dataframe')
    print(good_dataframe)
    
    goodrecords_sql = \
        """
        INSERT INTO tmp.{} 
        ({}) 
        VALUES {} 
        ON CONFLICT (objectid) DO UPDATE SET {}
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
                            else "'{}'".format(str(i).replace("'","").replace('"',""))  
                            for i in x
                        ]
                    )
                )
                for x in 
                list(zip(*[good_dataframe[c] for c in good_dataframe.columns]))
            ),
            #','.join(pkey_columns),
            #session['modified_tablename'],
            #',\n'.join([f"{colname} = EXCLUDED.{colname}" for colname in good_dataframe.columns if colname not in pkey_columns])
            ',\n'.join([f"{colname} = EXCLUDED.{colname}" for colname in good_dataframe.columns if colname != 'objectid'])
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


    print(sys.getsizeof(session))
    if not errors_dataframe.empty:
        return jsonify(
            tbl = htmltable(errors_dataframe),
            changed_indices = rejected_changes, 
            accepted_changes = [], 
            rejected_changes = rejected_changes, 
            errors = errors
        )


    # Get the submission_data from the session variable. 
    # This should be switched to being a temp table rather than an excel file path
    # df_origin = pd.read_excel(session['original_data_filepath'])    
    df_origin = pd.read_sql(f"SELECT {','.join(session['submission_colnames'])} FROM tmp.{session['origin_tablename']}", eng) \
        .replace('',np.NaN) \
        .replace('NA',np.NaN) \
        .replace("'=","=") # For resqualcode

    
    # Get the current modified submission
    df_modified = pd.read_sql(f"SELECT {','.join(session['submission_colnames'])} FROM tmp.{session['modified_tablename']}", eng) \
        .replace('',np.NaN) \
        .replace('NA',np.NaN) \
        .replace("'=","=") # For resqualcode


    added_records, deleted_records, modified_records, changed_indices, original_data = \
        compare(df_origin, df_modified, pkey_columns, current_app.immutable_fields)
    
    print("Done with Comparison routine")



    # Need to make sure the objectid's are integers, but not the added records, since those have next_rowid
    modified_records.objectid = modified_records.objectid.astype(int)
    deleted_records.objectid  = deleted_records.objectid.astype(int)
    
    
    
    # distinguish an accepted change from a rejected change based on errors
    # its a rejected change if we find that change in the errors
    print("# distinguish an accepted change from a rejected change based on errors")
    rejected_changes = [
        x for x in changed_indices if 
        (x['rownumber'], x['colname']) in [(r['row_number'], e['columns']) for e in errors for r in e['rows']]
    ]
    accepted_changes = [x for x in changed_indices if x not in rejected_changes]


    ##################################
    # --  Generate SQL statements -- #
    ##################################

    print("# Make a dataframe so we can groupby objectid and tablename")
    # Make a dataframe so we can groupby objectid and tablename
    # hislog = History Log
    hislog = pd.DataFrame({
        'objectid'     :   [int(item['objectid']) for item in accepted_changes],
        'tablename'    :   tablename,
        'changed_cols' :   [item['colname'] for item in accepted_changes],
        'newvalue'     :   [modified_records.iloc[item['rownumber'] - 1, modified_records.columns.get_loc(f"{item['colname']}")] for item in accepted_changes]   
    })
    
    if not hislog.empty:

        print("# 4 iterations of the for loop. Probably doesn't make a difference doing it this way or with map")
        # 4 iterations of the for loop. Probably doesn't make a difference doing it this way or with map
        for col in hislog.columns:
            hislog[col] = hislog[col].apply(lambda x: str(x))
        
        print("history log")
        hislog = hislog \
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
    else:
        hislog = []

    print("hislog")
    print(hislog)
    

    # After generating the update statements, generate the SQL for adding records
    print("After generating the update statements, generate the SQL for adding records")
    #added_records.objectid = f"sde.next_rowid('sde','{tablename}')"
    added_records['created_user'] = "change request app"
    added_records['created_date'] = pd.Timestamp(session['sessionid'], unit = 's').strftime("%Y-%m-%d %H:%M:%S")
    for k in session.get('login_fields').keys():
        added_records[f'login_{k}'] = session.get('login_fields').get(k)
    added_records['last_edited_user'] = session["session_user_email"]
    added_records['last_edited_date'] = pd.Timestamp(session['sessionid'], unit = 's').strftime("%Y-%m-%d %H:%M:%S")

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
        .replace("%","%%")

    # Now get the SQL for deleting records, which is a lot less complicated
    print("Now get the SQL for deleting records, which is a lot less complicated")
    delete_records_sql = f"DELETE FROM {tablename} WHERE objectid IN ({','.join([str(int(x)) for x in deleted_records.objectid.tolist()])})"

    # print(hislog)
    # print(add_records_sql)
    # print(delete_records_sql)

    #########################
    # --  Write to Excel -- #
    #########################

    print("changed_indices")
    #print(changed_indices)

    sql_filepath = f"{os.getcwd()}/files/{session['sessionid']}.sql"
    # Write hislog to a SQL file rather than excel, per Paul's request to leave it out of the excel file
    #hislog.to_excel(writer, sheet_name = "SQL statements",index = False)
    with open(sql_filepath, 'w') as f:
        f.write(';\n'.join(hislog))
        f.write(";\n\n")
        f.write(add_records_sql)
        f.write(";\n\n")
        f.write(delete_records_sql)
        f.write(";")
        f.close()
    
    session['sql_filepath'] = sql_filepath
    
    # make sure the highlighted excel file directory actually exists
    highlight_dir = os.path.join(os.getcwd(), 'export', 'highlightExcelFiles')
    if not os.path.exists(highlight_dir):
        os.makedirs(highlight_dir)
    
    path_to_highlighted_excel =  f"{os.getcwd()}/export/highlightExcelFiles/comparison_{session['sessionid']}.xlsx"
    session['comparison_path'] = path_to_highlighted_excel

    writer = pd.ExcelWriter(path_to_highlighted_excel, engine = 'xlsxwriter', options = {'strings_to_formulas': False})
    original_data.to_excel(writer, sheet_name = "Original", index = False)
    modified_records.to_excel(writer, sheet_name = "Modified", index = False)
    added_records.to_excel(writer, sheet_name = "Added", index = False)
    deleted_records.to_excel(writer, sheet_name = "Deleted", index = False)

    # Coloring the changed cells
    workbook = writer.book
    rejected_color = workbook.add_format({'bg_color':'#FF0000'})
    accepted_color = workbook.add_format({'bg_color':'#42f590'})
    worksheet = writer.sheets["Modified"]

    # highlight changes is defined in utils
    # Made it a function since later we likely will distinguish between highlighting an accepted change vs a rejected change, which will have different formatting
    # cells arg here should be a tuple of numbers. xlsxwriter can highlight based on coordinates of the cell, not column names
    # NOTE Soon there will be two of these - one for accepted changes (green) and another for rejected changes (red)
    highlight_changes(
        worksheet = worksheet, color = rejected_color, cells = [(item['rownumber'], modified_records.columns.get_loc(item['colname'])) for item in rejected_changes]
    )
    highlight_changes(
        worksheet = worksheet, color = accepted_color, cells = [(item['rownumber'], modified_records.columns.get_loc(item['colname'])) for item in accepted_changes]
    )
    
    writer.save()
    print("Successfully wrote to Excel")




    return jsonify(
        tbl = htmltable(modified_records, _id = "changes-display-table"), 
        addtbl = htmltable(added_records),
        deltbl = htmltable(deleted_records), 
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
            files = [session.get('comparison_path')],
            server = current_app.config.get('MAIL_SERVER')
        )
    return response