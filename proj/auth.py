from flask import Blueprint, render_template, request, jsonify, session, current_app, g, redirect, url_for, flash, render_template_string
from flask_bcrypt import Bcrypt
from flask_login import login_required, logout_user, current_user, login_user

import os
import psycopg2
import pandas as pd
from psycopg2 import sql
from psycopg2.errors import UniqueViolation
from datetime import datetime

from .utils.mail import send_mail
from .utils.token import generate_confirmation_token, confirm_token
from .models import User
from .forms import SignupForm, LoginForm
from . import login_manager, db


bcrypt = Bcrypt()

auth_bp = Blueprint('auth', __name__, url_prefix = "/auth")



@login_manager.unauthorized_handler
def unauthorized():
    """Redirect unauthorized users to Login page."""
    # flash('You must be logged in to view that page.')
    return redirect(url_for('auth.signin'))



@login_manager.user_loader
def load_user(user_id):
    """Check if user is logged-in on every page load."""
    if user_id is not None:
        return User.query.get(user_id)
    return None


@auth_bp.route('/signup', methods = ['GET','POST'])
def signup():
    form = SignupForm()
    if form.validate_on_submit():
        existing_user = User.query.filter_by(email=form.email.data).first()
        if existing_user is None:
            user = User(
                firstname=form.firstname.data,
                lastname=form.lastname.data,
                email=form.email.data,
                organization=form.organization.data
            )
            user.set_password(form.password.data)
            db.session.add(user)
            db.session.commit()  # Create new user
            #login_user(user)  # Log in as newly created user
            token = generate_confirmation_token(user.email)
            url = 'https://192.168.1.18/smcintercal-changerequest/auth/confirm/{}'.format(token)
            html = render_template('confirmation_email.jinja2', confirm_url = url)
            send_mail(current_app.send_from, [user.email], 'Change Request App Email Confirmation', html = html, server = current_app.config.get('MAIL_SERVER'))
            return redirect(url_for('auth.signin'))
            
        flash('A user already exists with that email address.')
    
    return render_template(
        'signup.jinja2',
        form=form
    )

@auth_bp.route('/signin', methods = ['GET','POST'])
def signin():
    
    if current_user.is_authenticated:
        return redirect(url_for('index'))

    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        print('user.is_admin')
        print(user.is_admin)
        if user and user.check_password(password=form.password.data):
            login_user(user)
            next_page = request.args.get('next')
            # its weird because the term "login" is used for the form that searches for the submission, but "sign in" is used for the user authentication part
            # I know that anyone taking over this application will be confused by that
            # For anyone taking over this - We added user authentication later on
            # Feel free to change the naming convention to make it more intuitive if you would like
            return redirect(next_page or url_for('login.index'))

        flash('Invalid username/password combination')
        return redirect(url_for('auth.signin'))

    return render_template('signin.jinja2', form=form)



@auth_bp.route('/logout', methods = ['GET','POST'])
def logout():
    flash(f"{current_user.email} successfully signed out")
    logout_user()
    print("current_user")
    print(current_user)
    print("current_user.is_authenticated")
    print(current_user.is_authenticated)
    return redirect(url_for('auth.signin'))


@auth_bp.route('/confirm/<token>')
def confirm_email(token):
    try:
        email = confirm_token(token)
    except:
        return 'token expired'
    user = User.query.filter_by(email=email).first_or_404()
    if user.email_confirmed == 'yes':
        flash('Account already confirmed. Please login.', 'success')
        return redirect(url_for('auth.signin'))
    
    user.email_confirmed = 'yes'
    user.email_confirmed_date = datetime.now()
    db.session.add(user)
    db.session.commit()
    flash('You have confirmed your account. Thanks!', 'success')
    return redirect(url_for('auth.signin'))


