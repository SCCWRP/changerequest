import os, json
import psycopg2
from psycopg2 import sql

from flask_wtf import FlaskForm
from wtforms import StringField, SelectField, PasswordField, SubmitField
from wtforms.validators import (
    DataRequired,
    Email,
    EqualTo,
    Length,
    Optional
)

CUSTOM_CONFIG_PATH = os.path.join(os.getcwd(), 'proj', 'config')
assert os.path.exists(os.path.join(CUSTOM_CONFIG_PATH, 'config.json')), \
    f"{os.path.join(CUSTOM_CONFIG_PATH, 'config.json')} configuration file not found"

CUSTOM_CONFIG = json.loads( open( os.path.join(CUSTOM_CONFIG_PATH, 'config.json'), 'r' ).read() )

conn = psycopg2.connect(
    dbname = os.environ.get("DB_NAME"),
    host = os.environ.get("DB_HOST"),
    password = os.environ.get("DB_PASSWORD"),
    user = os.environ.get("DB_USERNAME")
)
cur = conn.cursor()
cur.execute(
    sql.SQL(
        """
            SELECT {}, {} FROM {};
        """
    ).format(
        sql.Identifier(CUSTOM_CONFIG.get('user_management').get("organization_value_column")),
        sql.Identifier(CUSTOM_CONFIG.get('user_management').get("organization_label_column")),
        sql.Identifier(CUSTOM_CONFIG.get('user_management').get("organization_table"))
    )
)

org_select_opts = cur.fetchall()
cur.close()
conn.close()


class SignupForm(FlaskForm):
    """User Sign-up Form."""
    firstname = StringField(
        'First Name',
        validators=[DataRequired()]
    )
    lastname = StringField(
        'Last Name',
        validators=[DataRequired()]
    )
    email = StringField(
        'Email',
        validators=[
            Length(min=6),
            Email(message='Enter a valid email.'),
            DataRequired()
        ]
    )
    organization = SelectField(
        CUSTOM_CONFIG.get('user_management').get('organization_signup_field_label'),
        choices=org_select_opts,
        validators=[DataRequired()]
    )
    password = PasswordField(
        'Password',
        validators=[
            DataRequired(),
            Length(min=6, message='Select a stronger password.')
        ]
    )
    confirm = PasswordField(
        'Confirm Your Password',
        validators=[
            DataRequired(),
            EqualTo('password', message='Passwords must match.')
        ]
    )
    
    submit = SubmitField('Register')


class LoginForm(FlaskForm):
    """User Log-in Form."""
    email = StringField(
        'Email',
        validators=[
            DataRequired(),
            Email(message='Enter a valid email.')
        ]
    )
    password = PasswordField('Password', validators=[DataRequired()])
    submit = SubmitField('Log In')