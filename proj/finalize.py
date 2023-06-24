from flask import Blueprint, session, render_template, g, jsonify, current_app
import pandas as pd
import json
import os
from .utils.generic import change_history_update
from .utils.mail import send_mail

from flask_login import login_required

finalize = Blueprint('finalize', __name__)
@finalize.route("/final_submit", methods = ['GET', 'POST'])
@login_required
def savechanges():
    eng = g.eng

    sessionid = session.get('sessionid')
    submissionid = session.get('submissionid')
    login_info = json.dumps(session.get('login_fields')).replace("'","")

    # Both provided when the user signs in (auth.signin)
    session_user_email = str(session.get('session_user_email'))
    session_user_agency = str(session.get('session_user_agency'))

    try:
        print("getting the changed records")
        changed = pd.read_excel(
            f"{os.getcwd()}/export/highlightExcelFiles/comparison_{session['sessionid']}.xlsx", 
            sheet_name = 'Modified'
        ).fillna('')
        
        print("getting the original records")
        original = pd.read_excel(
            f"{os.getcwd()}/export/highlightExcelFiles/comparison_{session['sessionid']}.xlsx", 
            sheet_name = 'Original'
        ).fillna('')
        
        print("getting the deleted records")
        deleted = pd.read_excel(
            f"{os.getcwd()}/export/highlightExcelFiles/comparison_{session['sessionid']}.xlsx", 
            sheet_name = 'Deleted'
        ).fillna('')
        
        print("getting the added records")
        added = pd.read_excel(
            f"{os.getcwd()}/export/highlightExcelFiles/comparison_{session['sessionid']}.xlsx", 
            sheet_name = 'Added'
        ).fillna('')

        for colname,datatype in changed.dtypes.to_dict().items():
            if datatype == 'datetime64[ns]':
                changed[colname] = changed[colname].apply(lambda x: x.strftime("%Y-%m-%d %H:%M:%S") if pd.notnull(x) else '')
            if colname == 'resqualcode':
                changed[colname] = changed[colname].str.replace("'","")
        
        for colname,datatype in original.dtypes.to_dict().items():
            if datatype == 'datetime64[ns]':
                original[colname] = original[colname].apply(lambda x: x.strftime("%Y-%m-%d %H:%M:%S") if pd.notnull(x) else '')
            if colname == 'resqualcode':
                original[colname] = original[colname].str.replace("'","")
        
        for colname,datatype in added.dtypes.to_dict().items():
            if datatype == 'datetime64[ns]':
                added[colname] = added[colname].apply(lambda x: x.strftime("%Y-%m-%d %H:%M:%S") if pd.notnull(x) else '')
            if colname == 'resqualcode':
                added[colname] = added[colname].str.replace("'","")
        
        for colname,datatype in deleted.dtypes.to_dict().items():
            if datatype == 'datetime64[ns]':
                deleted[colname] = deleted[colname].apply(lambda x: x.strftime("%Y-%m-%d %H:%M:%S") if pd.notnull(x) else '')
            if colname == 'resqualcode':
                deleted[colname] = deleted[colname].str.replace("'","")


        print("update the change history table one by one")
        print("update the changed records")
  
        change_history_records = [
            *changed.apply(
                lambda row: change_history_update(row, original, sessionid, submissionid, login_info, session_user_agency, session_user_email),
                axis = 1
            ) \
            .values,
            *added.apply(
                lambda row:
                f"""
                    (
                        '[]',
                        '{json.dumps(row.to_dict()).replace("'","")}',
                        {sessionid},
                        {submissionid},
                        '{login_info}',
                        '{session_user_agency}'
                        '{session_user_email}',
                        '{pd.Timestamp(sessionid, unit = 's').strftime("%Y-%m-%d %H:%M:%S")}',
                        'No'
                    )
                """,
                axis = 1
            ).values,
            *deleted.apply(
                lambda row:
                f"""
                    (
                        '{json.dumps(row.to_dict()).replace("'","")}',
                        '[]',
                        {sessionid},
                        {submissionid},
                        '{login_info}',
                        '{session_user_agency}',
                        '{session_user_email}',
                        '{pd.Timestamp(sessionid, unit = 's').strftime("%Y-%m-%d %H:%M:%S")}',
                        'No'
                    )
                """,
                axis = 1
            ).values
        ]

        change_history_sql = f"""
            INSERT INTO {os.environ.get('CHANGE_HISTORY_TABLE')} (
                original_record,
                modified_record,
                change_id,
                submissionid,
                login_fields,
                requesting_agency,
                requesting_person,
                change_date,
                change_processed
            ) VALUES {', '.join(change_history_records)}
        """
        change_history_sql = change_history_sql.replace('%','%%')
        print("change_history_sql")
        print(change_history_sql)

        assert sessionid not in pd.read_sql(f"SELECT DISTINCT change_id FROM {os.environ.get('CHANGE_HISTORY_TABLE')}", eng).change_id.values, \
            f"Change ID {sessionid} already exists in the change history table"

        eng.execute(change_history_sql)

        with open(os.path.join(os.getcwd(), 'files', f"{session['sessionid']}.sql"), 'r') as sqlfile:
            datatype = session.get('dtype')

            sql = sqlfile.read()
            sqlfile.close()

            # email for user
            send_mail(
                current_app.send_from,
                [
                    *current_app.maintainers,
                    str(session.get('session_user_email'))
                ],
                f'Data Change Request made for {current_app.config.get("projectname")}',
                """A database change request was made from {} :\n\n\
Datatype: {}\n\
Original Submission Date: {}\n\
Original Submission ID: {}\n\
Change ID: {}\n\n\
SCCWRP Staff has been notified and they will let you know when the change has been finalized.
\n\
                """.format(
                    str(session.get('session_user_email')),
                    session.get('dtype'),
                    session.get('submissiondate'),
                    session.get('submissionid'),
                    session.get('sessionid')
                ),
                files = [session.get('comparison_path')],
                server = current_app.config.get('MAIL_SERVER')
            )

            # email for staff
            send_mail(
                current_app.send_from,
                [
                    *current_app.maintainers
                ],
                f'Data Change Request made for {current_app.config.get("projectname")}',
                """A database change request was made from {} :\n\n\
Datatype: {}\n\
Original Submission Date: {}\n\
Original Submission ID: {}\n\
Change ID: {}\n\n\n\
For SCCWRP staff:\n\
UPDATE RECORDS: (See attached SQL file)\n
\n\nUPDATE CHANGE HISTORY TABLE:\n{}
                """.format(
                    str(session.get('session_user_email')),
                    session.get('dtype'),
                    session.get('submissiondate'),
                    session.get('submissionid'),
                    session.get('sessionid'),
                    #sql,
                    f"UPDATE {os.environ.get('CHANGE_HISTORY_TABLE')} SET change_processed = 'Yes' WHERE change_id = {session['sessionid']}"
                ),
                files = [session.get('comparison_path'), session.get('sql_filepath')],
                server = current_app.config.get('MAIL_SERVER')
                # server = '192.168.1.18'
            )

        

        return render_template(
            "thankyou.jinja2",
            success = True,
            datatype = session.get('dtype'),
            session_user_email = str(session.get('session_user_email')), 
            submissiondate = session.get('submissiondate'), 
            submissionid = session.get('submissionid'), 
            login_fields = session.get('login_fields'),
            change_id = session.get('sessionid')
        )

    except Exception as e:
        print(e)
        print(str(e)[:400])
        send_mail(
            current_app.send_from,
            [
                *current_app.maintainers
            ],
            'Data Change Request Error',
            "{} (sessionid {}) came accross an error:\n\t{}\n\n\nSession Info:\n\t{}".format(
                str(session.get('session_user_email')),
                session.get('sessionid'),
                str(e)[:500],
                '\n\n\t'.join([f"{k}: {session.get(k)}" for k in session.keys()])
            ),
            files = [session.get('comparison_path')],
            server = current_app.config.get('MAIL_SERVER')
        )
        return render_template(
            "thankyou.jinja2",
            success = False,
            datatype = session.get('dtype'),
            session_user_email = str(session.get('session_user_email')), 
            submissiondate = session.get('submissiondate'), 
            submissionid = session.get('submissionid'), 
            login_fields = session.get('login_fields'),
            change_id = session.get('sessionid')
        )


@finalize.errorhandler(Exception)
def default_error_handler(error):
    print("Checker application came across an error...")
    #print(str(error).encode('utf-8'))
    response = jsonify({'code': 500,'message': str(error)})
    response.status_code = 500
    # need to add code here to email SCCWRP staff about error
    send_mail(
        current_app.send_from,
        [
            *current_app.maintainers
        ],
        'Data Change Request Error',
        f"{str(session.get('session_user_email'))} (sessionid {session.get('sessionid')}) came accross an error: {str(error)}",
        files = [session.get('comparison_path')],
        server = current_app.config.get('MAIL_SERVER')
    )
    return response