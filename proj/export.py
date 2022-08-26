#######################################################
# This file contains code to fetch the requested data #
#######################################################
from flask import Blueprint, request, jsonify, session, send_file, g, current_app
import pandas as pd
import os
from .utils.mail import send_mail

from flask_login import login_required

export = Blueprint('export',__name__)

@export.route('/submission-download', methods = ['GET', 'POST'])
@login_required
def download_submission():

    eng = g.eng
    submissionid = request.args.get('submissionid')
    tablename = request.args.get('tablename')

    # if it was not provided in the query string, it should be already in the session data
    submissionid = submissionid if submissionid else session.get('submissionid')
    tablename = tablename if tablename else session.get('tablename')
    
    filename = f"{tablename}_{submissionid}.xlsx"

    excelpath = os.path.join(os.getcwd(),'export', filename)
    
    if not os.path.exists(excelpath):
    
        writer = pd.ExcelWriter(excelpath)
        df = pd.read_sql(f"SELECT * FROM {tablename} WHERE submissionid = {submissionid};", eng)
        df.to_excel(writer, sheet_name = tablename, index = False)
        
        writer.save()

    return send_file(excelpath, as_attachment = True, download_name = filename)



@export.route("/download_change_history", methods = ['GET','POST'])
@login_required
def download_change_history():
    return send_file(
        session['comparison_path'],
        as_attachment = True,
        download_name = f"{session.get('sessionid')}_comparison.xlsx"
    )

# # This will be for editing in browser
# lazy_loading = Blueprint('lazy_loading', __name__)
# @lazy_loading.route("/loading_lazy", methods = ['GET', 'POST'])
# def loading_lazy():
#     offset = request.form.get("offset")
#     limit = request.form.get("limit")
#     df_cols = session["submission_colnames"]
#     tablename = tablenames[session["dtype"]]
#     df = pd.read_sql(f"SELECT {','.join(df_cols)} FROM {tablename} LIMIT {limit} OFFSET {offset}", eng)
#     return jsonify(tbl = htmltable(df))



@export.errorhandler(Exception)
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