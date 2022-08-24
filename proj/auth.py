from flask import Blueprint, render_template, request, jsonify, session, current_app, g, redirect, url_for, flash
from flask_bcrypt import Bcrypt
from flask_login import login_required, logout_user, current_user, login_user

import os
import psycopg2
import pandas as pd
from psycopg2 import sql
from psycopg2.errors import UniqueViolation

from .utils.mail import send_mail
from .models import User
from .forms import SignupForm, LoginForm
from . import login_manager, db


bcrypt = Bcrypt()

auth = Blueprint('auth', __name__, url_prefix = "/auth")

@auth.route('/signup')
def signupform():
    
    form = SignupForm()
    if form.validate_on_submit():
        existing_user = User.query.filter_by(email=form.email.data).first()
        if existing_user is None:
            user = User(
                name=form.name.data,
                email=form.email.data,
                website=form.website.data
            )
            user.set_password(form.password.data)
            db.session.add(user)
            db.session.commit()  # Create new user
            login_user(user)  # Log in as newly created user
            #return redirect(url_for('main_bp.dashboard'))
            return 'i hope this worked'
            
        flash('A user already exists with that email address.')
    
    return render_template(
        'signup.jinja',
        form=form
    )

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



