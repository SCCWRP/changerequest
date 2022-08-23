from flask import Blueprint, render_template, request, jsonify, session, current_app, g
from flask_bcrypt import Bcrypt
import os
import psycopg2
import pandas as pd
from psycopg2 import sql
from psycopg2.errors import UniqueViolation
from .utils.mail import send_mail

bcrypt = Bcrypt()

auth = Blueprint('auth', __name__)

@auth.route('/signup-form')
def signupform():
    agencies = None
    if current_app.user_management.get('agency_table'):
        agency_table = current_app.user_management.get('agency_table')
        agency_val_col = current_app.user_management.get('agency_value_column')
        agency_label_col = current_app.user_management.get('agency_label_column')
        agencies = pd.read_sql(f'''SELECT {agency_val_col} AS agencycode, {agency_label_col} as agencyname FROM {agency_table}''', g.eng).values
        print(agencies)
        agencies = {a[0]:a[1] for a in agencies}
        print(agencies)
    return render_template('signup.html', agencies = agencies)

@auth.route('/auth-form')
def authform():
    return render_template('auth.jinja')

@auth.route('/signup', methods = ['GET','POST'])
def signup():

    # create and remove connection every time
    conn = psycopg2.connect(
        dbname = os.environ.get("DB_NAME"),
        host = os.environ.get("DB_HOST"),
        password = os.environ.get("DB_PASSWORD"),
        user = os.environ.get("DB_USERNAME")
    )

    firstname = request.form.get('firstname')
    lastname = request.form.get('lastname')
    email = request.form.get('email')
    password = request.form.get('password')

    # agency may not be part of all the login forms
    agency = request.form.get('agency') if request.form.get('agency') else ''
    
    # horrible idea to do this in a real application for obvious reasons
    print(password)
    hashed_password = bcrypt.generate_password_hash(password)
    hashed_password = hashed_password.decode('utf-8')
    print(hashed_password)

    try:
        cur = conn.cursor()
        cur.execute(
            """
                INSERT INTO db_editors ("firstname","lastname","email", "password", "agency", "is_admin", "is_authorized") VALUES (%s,%s,%s,%s,%s, 'no', 'no');
            """,
            (   
                firstname,
                lastname,
                email, 
                hashed_password,
                agency
            )    
        )
        conn.commit()
        cur.close()
        conn.close()
        email_msg = f"""{firstname} {lastname} ({email}) { ' from {}'.format(agency) if agency else ''} has signed up to use the change request app.\n\nUPDATE db_editors SET is_authorized = 'yes' WHERE email = '{email}'"""
        send_mail(
            'admin@checker.sccwrp.org',
            current_app.maintainers,
            "Data Change Request App User Sign up", 
            email_msg, 
            server = current_app.config.get('MAIL_SERVER')
        )
        return jsonify(msg = f'{firstname} {lastname} signed up')
    except UniqueViolation as e:
        print(e)
        print(type(e).__name__)
        conn.rollback()
        conn.close()
        return jsonify(msg = 'error')


@auth.route('/signin', methods = ['GET','POST'])
def signin():
    conn = psycopg2.connect(
        dbname = os.environ.get("DB_NAME"),
        host = os.environ.get("DB_HOST"),
        password = os.environ.get("DB_PASSWORD"),
        user = os.environ.get("DB_USERNAME")
    )

    email = request.form.get('email')
    password = request.form.get('password')

    cur = conn.cursor()
    cur.execute("SELECT password, is_authorized FROM db_editors WHERE email = %s;", (email,))
    result = cur.fetchall() # returns a list of tuples
    if len(result) == 0:
        return jsonify(msg = f'email {email} not found')
    
    assert len(result) == 1, f"More than one result for {email} - primary key not set correctly"
    
    # grab first and only item in the list and grab the first item in that tuple which will be the password
    # result[0] should be a two item tuple, since we specifically queried two fields
    true_password = result[0][0]
    authorized = result[0][1] == 'yes'
        
    if not bcrypt.check_password_hash(true_password.encode('utf-8'), password):
        return jsonify(msg = "wrong password")
    
    if not authorized:
        return jsonify(msg = 'not authorized by SCCWRP to change data')
    
    session['AUTH_INFO'] = {
        'AUTHENTICATED': True,
        'AUTH_EMAIL' : email
    }
    #session.is_admin = ? # still need to add logic to check if they are an admin

    
    
    return jsonify(msg = "success")



