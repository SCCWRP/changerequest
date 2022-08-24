import json, os
from . import db
from sqlalchemy import text
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash


CUSTOM_CONFIG_PATH = os.path.join(os.getcwd(), 'proj', 'config')
assert os.path.exists(os.path.join(CUSTOM_CONFIG_PATH, 'config.json')), \
    f"{os.path.join(CUSTOM_CONFIG_PATH, 'config.json')} configuration file not found"

CUSTOM_CONFIG = json.loads( open( os.path.join(CUSTOM_CONFIG_PATH, 'config.json'), 'r' ).read() )


class User(UserMixin, db.Model):
    """Data model for user accounts."""

    __tablename__ = CUSTOM_CONFIG.get('user_management').get('users_table')

    __table_args__ = {
        "schema": "sde",
        'extend_existing': True
    }
    id = db.Column(
        db.Integer,
        primary_key = True
    )
    email = db.Column(
        db.String(50),
        primary_key=False,
        unique=True,
        nullable=False
    )
    password = db.Column(
        db.String(255),
        primary_key=False
    )
    firstname = db.Column(
        db.String(50),
        primary_key=False
    )
    lastname = db.Column(
        db.String(50),
        primary_key=False
    )
    organization = db.Column(
        db.String(255),
        primary_key=False
    )
    is_admin = db.Column(
        db.String(3),
        primary_key=False,
        server_default = "no"
    )
    is_authorized = db.Column(
        db.String(3),
        primary_key=False,
        server_default = "no"
    )
    email_confirmed = db.Column(
        db.String(3),
        primary_key=False,
        server_default = "no"
    )
    signup_date = db.Column(
        db.DateTime(),
        primary_key=False,
        server_default = text('NOW()')
    )

    def set_password(self, password):
        """Create hashed password."""
        self.password = generate_password_hash(
            password,
            method='sha256'
        )

    def check_password(self, password):
        """Check hashed password."""
        return check_password_hash(self.password, password)

    def __repr__(self):
        return '<User {}>'.format(self.username)