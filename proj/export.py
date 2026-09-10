#######################################################
# This file contains code to fetch the requested data #
#######################################################
from flask import Blueprint, jsonify, session, send_file, current_app
from .utils.submissions import request_directory, read_state

from flask_login import login_required

export = Blueprint('export',__name__)

@export.route('/submission-download', methods = ['GET', 'POST'])
@login_required
def download_submission():
    if not session.get('tables'):
        return jsonify(message='Select a submission first.'), 400
    return send_file(
        request_directory(session['sessionid']) / 'submission.xlsx', as_attachment=True,
        download_name=f"{session['dtype']}_{session['submissionid']}.xlsx",
    )



@export.route("/download_change_history", methods = ['GET','POST'])
@login_required
def download_change_history():
    if not session.get('sessionid') or not read_state(session['sessionid']).get('ready'):
        return jsonify(message='No valid comparison report is available.'), 400
    return send_file(
        request_directory(session['sessionid']) / 'comparison.xlsx',
        as_attachment = True,
        download_name = f"{session.get('sessionid')}_comparison.xlsx"
    )

@export.errorhandler(Exception)
def default_error_handler(error):
    current_app.logger.exception('Submission export failed')
    return jsonify(message='This request file is unavailable. Contact SCCWRP with your change ID.'), 500