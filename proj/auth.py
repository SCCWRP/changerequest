from flask import Blueprint, render_template, request, jsonify, session, current_app
from flask_bcrypt import Bcrypt
import os
import psycopg2
from psycopg2 import sql
from psycopg2.errors import UniqueViolation
from .utils.mail import send_mail

bcrypt = Bcrypt()

auth = Blueprint('auth', __name__)

@auth.route('/signup')
def signup():

    # create and remove connection every time
    conn = psycopg2.connect(
        dbname = os.environ.get("DB_NAME"),
        host = os.environ.get("DB_HOST"),
        password = os.environ.get("DB_PASSWORD"),
        user = os.environ.get("DB_USER")
    )

    username = request.form.get('username')
    email = request.form.get('email')
    pw = request.form.get('pw')
    agency = request.form.get('agency')
    
    # horrible idea to do this in a real application for obvious reasons
    print(pw)
    hashed_password = bcrypt.generate_password_hash(pw)
    hashed_password = hashed_password.decode('utf-8')
    print(hashed_password)

    try:
        cur = conn.cursor()
        cur.execute(
            """
                INSERT INTO db_editors ("username", "email", "password", "agency", "is_admin", "is_authorized") VALUES (%s,%s,%s,%s, 'no', 'no');
            """,
            (
                username,
                email, 
                hashed_password,
                agency
            )    
        )
        conn.commit()
        cur.close()
        conn.close()
        email_msg = f"{username} ({email}) from {agency} has signed up to use the change request app.\n\nUPDATE db_editors SET is_authorized = 'yes' WHERE username = '{username}'"
        send_mail(
            'admin@checker.sccwrp.org',
            current_app.maintainers,
            "Data Change Request App User Sign up", 
            email_msg, 
            server = current_app.config.get('MAIL_SERVER')
        )
        return jsonify(msg = f'{username} signed up')
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
        user = os.environ.get("DB_USER")
    )

    username = request.form.get('username')
    email = request.form.get('email')
    pw = request.form.get('pw')

    cur = conn.cursor()
    cur.execute("SELECT password, is_authorized FROM db_editors WHERE username = %s;", (username,))
    result = cur.fetchall() # returns a list of tuples
    if len(result) == 0:
        return jsonify(msg = f'username {username} not found')
    
    assert len(result) == 1, f"More than one result for {username} - primary key not set correctly"
    
    # grab first and only item in the list and grab the first item in that tuple which will be the password
    true_password = result[0][0]
    is_authorized = result[0][1]
    is_authorized = is_authorized == 'yes'
    if not is_authorized:
        return jsonify(msg = 'not authorized by SCCWRP to change data')
        
    if bcrypt.check_password_hash(true_password.encode('utf-8'), pw):
        session.AUTHENTICATED = True
        session.auth_email = email
        #session.is_admin = ?
        return jsonify(msg = "success")
    else: 
        return jsonify(msg = "wrong password")




