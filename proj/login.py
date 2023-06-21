#########################################################
# This file contains code that handles the login screen #
#########################################################
from flask import Blueprint, request, jsonify, session, render_template, current_app, g
import pandas as pd
from datetime import datetime
import os
from .utils.generic import unixtime
from .utils.login import get_login_field, get_submission_ids

from flask_login import login_required, current_user

login = Blueprint('login', __name__)


@login.route('/')
@login_required
def index():
    dtypes = current_app.dtypes
    return render_template("index.jinja2", dtypes = dtypes)

@login.route("/edit-submission", methods = ['GET', 'POST'])
@login_required
def edit_data():
    return render_template("edit-submission.jinja2", login_fields = session.get('login_fields'))

@login.route('/login_values')
@login_required
def login_values():
    eng = g.eng

    data = get_login_field(
        dtypes = current_app.dtypes,
        eng = eng,
        **request.args
    )
    return jsonify(data = data)

@login.route('/submissions')
@login_required
def submissions():
    eng = g.eng
    
    data = get_submission_ids(
        dtypes = current_app.dtypes,
        eng = eng,
        **request.args
    )

    return jsonify(submissions = data)


@login.route("/post-session-data", methods = ['GET', 'POST'])
@login_required
def sessiondata():

    eng = g.eng
    system_fields = current_app.system_fields

    print(request.form)
    session['login_fields'] = dict(request.form)

    # check the organization they logged in as against the organization they are part of
    login_organization = request.form.get(current_app.config.get('user_management').get('organization_login_field'))
    admin_user = current_user.is_admin == 'yes'
    authorized_user = current_user.is_authorized == 'yes'
    print("authorized_user")
    print(authorized_user)
    if not authorized_user:
        maintainers = current_app.config.get('maintainers')
        maintainers_str = ','.join(maintainers)
        return jsonify(user_error_msg=f"SCCWRP has not yet approved the user {current_user.email} to edit data with this application. Contact {maintainers_str}")
    if not admin_user:
        if current_user.organization != login_organization:
            return jsonify(user_error_msg=f"You ({current_user.email}) are not authorized to edit data from {login_organization}")
    if not current_user.email_confirmed == 'yes':
            return jsonify(user_error_msg=f"You have not yet confirmed your email ({current_user.email})")

    # Get the current sessionid, later used as a changeID
    session['sessionid'] = unixtime(datetime.today())

    # SubmissionID and Tablename are in every form, thats how the HTML was set up
    session['submissionid'] = request.form.get('submissionid')
    session['submissiondate'] = pd.Timestamp(int(request.form.get('submissionid')), unit = 's').strftime('%Y-%m-%d %H:%M:%S')
    session['tablename'] = request.form.get('tablename')
    # now provided in auth form
    #session['session_user_email'] = request.form.get('session_user_email')
    session['dtype'] = request.form.get('dtype')

    tablename = session.get('tablename')

    # Get the current sessionid, later used as a changeID
    session['sessionid'] = unixtime(datetime.today())

    system_cols = ",".join(f"'{colname}'" for colname in system_fields)
    df_cols = pd.read_sql(f"""
        SELECT column_name FROM INFORMATION_SCHEMA.columns 
        WHERE table_name = '{tablename}' 
        AND column_name NOT IN ({system_cols})
    """,eng
    )['column_name'].tolist()
    
    # Having the column names of the data that is being retrieved may be useful to have in the session variable
    # May be useful running basic checks on data that the user drops back in
    # We need to make sure that the data they drop has the same column names
    # Like i said, this may end up not being needed.
    # As of now, I am using this in the lazy loading route (see below)
    session["submission_colnames"] = df_cols

    # We will store the user's data in two tables in the tmp schema
    # One table is for the original submission, whereas the other is for the changed submission
    # Storing their temporary changed data will make it easier for us to run various checks on their data
    # Not all checks apply to inficidual rows of data. Some checks are by batches of rows, or groups of rows
    session['origin_tablename'] = f"orig_{session.get('tablename')}_{session.get('submissionid')}"
    session['modified_tablename'] = f"mod_{session.get('tablename')}_{session.get('submissionid')}"

    
    
    # Called tmp sql since it creates the temporary tables in the tmp schema
    # BY THE WAY, the SMC change request app needs to have things done on the basis of agency, etc because in many cases the submission ID is missing
    # We might want to consider populating that column based on the created_date, so the SMC data can work with this version of the app
    # 8/12/2022 - I think for the SMC database, it will be best for us to back populate the submission id's for the sake of tracking data and for this change application - Robert
    

    eng.execute(
        f"""
            CREATE TABLE IF NOT EXISTS tmp.{session['modified_tablename']} (LIKE sde.{tablename} INCLUDING ALL);
            CREATE TABLE IF NOT EXISTS tmp.{session['origin_tablename']} (LIKE sde.{tablename} INCLUDING ALL);
            DELETE FROM tmp.{session['origin_tablename']};
            DELETE FROM tmp.{session['modified_tablename']};
        """
    )
    print(tablename)
    # Remove Not NULL constraints from the tmp tables, at least for the immutable fields
    # It doesnt matter if those fields get populated in the tmp tables
    # we need to do this with psycopg sql injection prevention and all that

    print("Querying for columns that the temp tables actually have so we dont attempt to modify non existent columns")
    existing_cols = set(
        pd.read_sql(
            f"""
                (SELECT DISTINCT column_name FROM information_schema.columns WHERE table_name LIKE '{session['modified_tablename']}')
                UNION ALL
                (SELECT DISTINCT column_name FROM information_schema.columns WHERE table_name LIKE '{session['origin_tablename']}')
            """,
            eng
        ) \
        .column_name.unique()
    )
    print("DONE querying for columns that the temp tables actually have so we dont attempt to modify non existent columns")

    rmsql = [
        f"""
            ALTER TABLE tmp.{session['modified_tablename']} ALTER COLUMN {col} DROP NOT NULL;
            ALTER TABLE tmp.{session['origin_tablename']} ALTER COLUMN {col} DROP NOT NULL;
        """
        for col in set(current_app.immutable_fields).intersection(existing_cols)
    ]

    # objectid cant be part of the system fields - it must be preserved during the comparison
    # Its NOT NULL constraint must be dropped, because records getting added will not have objectid's
    rmsql.append(f"""ALTER TABLE tmp.{session['modified_tablename']} ALTER COLUMN objectid DROP NOT NULL;""")

    eng.execute(';'.join(rmsql))

    eng.execute(
        f"""
        INSERT INTO tmp.{session['origin_tablename']}
            (
                SELECT * FROM sde.{tablename}  
                WHERE submissionid = {session.get('submissionid')}
            );
        """
    )


    
    # We embedded the SQL which selects their submission into the same string that creates, and updates the "original data" temp table
    # Reason being, we ran it separately with pandas read sql after, got an error saying the table didnt exist
    # We hypothesized that the code that read the table was executing before the code that created the table was done, so we wanted to 
    #   essentially put the code that reads the table in the same SQL transaction as the code that creates the tables etc.
    # However, come to find out, it is most likely simply due to the fact that i did not put the "tmp." schema name in front of the table.....
    # -__-
    # HOWEVER. It works now, so im not going to mess with it.
    sqlresult = eng.execute(f"""SELECT {",".join(f"tmp.{session['origin_tablename']}.{c}" for c in df_cols)} FROM tmp.{session['origin_tablename']};""")
    df = pd.DataFrame(sqlresult.fetchall())


    print('df')
    print(df)

    if df.empty:
        return jsonify(user_error_msg = 'No data found')

    df.columns = [x.lower() for x in sqlresult.keys()]
    
    # save the path it got saved to
    # This should be a temp table rather than an excel file
    original_data_filepath = f"{os.getcwd()}/export/{tablename}_{session.get('submissionid')}.xlsx"
    session['original_data_filepath'] = original_data_filepath
    session['original_data_sql'] = f"SELECT {','.join(df_cols)} FROM tmp.{session['origin_tablename']}"


    # write to excel for user to download
    with pd.ExcelWriter(original_data_filepath, engine = 'xlsxwriter',engine_kwargs={'options': {'strings_to_formulas': False}}) as writer:
        df.to_excel(writer, index=False)



    return jsonify(message = 'Success')
