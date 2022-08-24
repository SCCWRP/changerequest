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

auth_bp = Blueprint('auth', __name__, url_prefix = "/auth")



@login_manager.unauthorized_handler
def unauthorized():
    """Redirect unauthorized users to Login page."""
    flash('You must be logged in to view that page.')
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
            return redirect(url_for('auth.signin'))
            
        flash('A user already exists with that email address.')
    
    return render_template(
        'signup.jinja',
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
            return redirect(next_page or url_for('login.index'))

        flash('Invalid username/password combination')
        return redirect(url_for('auth.signin'))

    return render_template('signin.jinja', form=form)



@auth_bp.route('/logout', methods = ['GET','POST'])
def logout():
    flash(f"{current_user.email} successfully signed out")
    logout_user()
    return redirect(url_for('auth.signin'))




