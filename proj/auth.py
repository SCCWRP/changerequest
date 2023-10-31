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
from .forms import SignupForm, LoginForm, EmailForm, ResetPasswordForm
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
            url = os.path.join(request.url_root, 'auth', 'confirm', f"?token={token}")
            html = render_template('confirmation_email.jinja2', confirm_url = url, projectname = current_app.config.get("projectname"))
            flash(f"Confirmation email sent to {user.email}")
            send_mail(
                current_app.send_from, 
                [user.email], 
                f'{current_app.config.get("projectname")} Change Request App Email Confirmation', 
                html = html, 
                server = current_app.config.get('MAIL_SERVER')
            )
            send_mail(
                current_app.send_from, 
                current_app.maintainers, 
                'Change Request App Reqistration Request', 
                text = f'{user.email} has signed up to change data for the project {current_app.config.get("projectname")}. You will need to go to the database to approve them.',
                server = current_app.config.get('MAIL_SERVER')
            )
            return redirect(url_for('auth.signin'))
            
        flash('A user already exists with that email address.')
    
    return render_template(
        'signup.jinja2',
        form=form
    )

@auth_bp.route('/signin', methods = ['GET','POST'])
def signin():
    
    if current_user.is_authenticated:
        return redirect(url_for('login.index'))

    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        
        if user: 
            if user.check_password(password=form.password.data):
                login_user(user)
                next_page = request.args.get('next')
                # its weird because the term "login" is used for the form that searches for the submission, but "sign in" is used for the user authentication part
                # I know that anyone taking over this application will be confused by that
                # For anyone taking over this - We added user authentication later on
                # Feel free to change the naming convention to make it more intuitive if you would like
                if user.email_confirmed != 'yes':
                    flash("You have not yet confirmed your email address")
                    return redirect(url_for('auth.confirm_email'))
                session['session_user_email'] = user.email
                session['session_user_agency'] = user.organization
                return redirect(next_page or url_for('login.index'))
            flash('Invalid username/password combination')
            return redirect(url_for('auth.signin'))
        else:
            flash(f'Email address {form.email.data} not found')
            return redirect(url_for('auth.signin'))        


    return render_template('signin.jinja2', form=form)



@auth_bp.route('/logout', methods = ['GET','POST'])
def logout():
    
    # Clear tmp tables if they had them
    origintbl = session.get('origin_tablename')
    modtbl = session.get('modified_tablename')
    if ((origintbl is not None) and (modtbl is not None)):
        g.eng.execute(
            f"""
            DROP TABLE IF EXISTS tmp.{origintbl};
            DROP TABLE IF EXISTS tmp.{modtbl};
            """
        )

    flash(f"{current_user.email} successfully signed out")
    logout_user()
    session.clear()
    return redirect(url_for('auth.signin'))


@auth_bp.route('/confirm/', methods = ['GET','POST'])
def confirm_email():
    # in case they are asking for another email to be sent
    form = EmailForm()
    token = request.args.get('token')

    if form.validate_on_submit():
        email_address = form.email.data
        print("email_address")
        print(email_address)
        token = generate_confirmation_token(email_address)
        url = os.path.join(request.url_root, 'auth', 'confirm', f"?token={token}")
        html = render_template('confirmation_email.jinja2', confirm_url = url)
        send_mail(current_app.send_from, [email_address], 'Change Request App Email Confirmation', html = html, server = current_app.config.get('MAIL_SERVER'))
        flash(f"Confirmation email sent to {email_address}")
        return redirect(url_for('login.index'))
    
    if token is None:
        return render_template('confirm_email.jinja2', form = form)
    try:
        email = confirm_token(token)
        if email == False:
            raise Exception("Token expired")
    except Exception as e:
        flash(str(e))
        return render_template('confirm_email.jinja2', form = form)

    user = User.query.filter_by(email=email).first_or_404()
    if user.email_confirmed == 'yes':
        flash('Account already confirmed. Please login.', 'success')
        return redirect(url_for('auth.signin'))
    

    if user.email_confirmed == 'yes':
        flash('You have already confirmed your account. Thanks!', 'success')
        return redirect(url_for('auth.signin'))
    user.email_confirmed = 'yes'
    user.email_confirmed_date = datetime.now()
    db.session.add(user)
    db.session.commit()
    flash('You have confirmed your account. Thanks!', 'success')
    return redirect(url_for('auth.signin'))


@auth_bp.route("/forgot_password", methods=['GET', 'POST'])
def reset_request():
    if current_user.is_authenticated:
        return redirect(url_for('login.index'))

    form = EmailForm(submit_label='Send Password Reset Email')
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()

        if user:
            token = generate_confirmation_token(user.email)
            url = os.path.join(request.url_root, 'auth', 'reset_password', f"{token}")

            # TODO create password_reset_email.jinja2
            html = render_template('password_reset_email.jinja2', confirm_url = url)
            send_mail(current_app.send_from, [user.email], 'Change Request App Email Confirmation', html = html, server = current_app.config.get('MAIL_SERVER'))
            flash('An email has been sent with instructions to reset your password.', 'info')
            return redirect(url_for('login.index'))
        else:    
            flash(f"Email address {form.email.data} not found", 'info')

    return render_template('reset_request.jinja2', title='Reset Password', form=form)


@auth_bp.route("/reset_password/<token>", methods=['GET', 'POST'], strict_slashes=False)
def reset_password(token):
    
    # No token provided? Take them to the password reset request page
    if token is None:
        return redirect(url_for('auth.reset_request'))

    # Are they already signed in? Then they shouldn't come to this page
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))  # Redirect to main page instead of login

    # Confirm the token
    try:
        email = confirm_token(token)
        if not email:
            raise Exception("Token expired or invalid")
    except Exception as e:
        flash(str(e))
        return redirect(url_for('login.index'))  # Redirect to main page instead of login
    
    user = User.query.filter_by(email=email).first()  # Retrieve user

    # If there is no user with this email, redirect them
    if user is None:
        flash('There is no account with this email. You must register first.')
        return redirect(url_for('auth.signup'))

    form = ResetPasswordForm()
    
    if form.validate_on_submit():
        user.set_password(form.password.data)
        db.session.commit()
        flash('Your password has been updated! You are now able to log in', 'success')
        return redirect(url_for('auth.signin'))

    return render_template('reset_password.jinja2', title='Reset Password', form=form)
