from . import db
from flask import current_app
from werkzeug.security import generate_password_hash, check_password_hash

class User(db.Model):
    """Data model for user accounts."""

    __tablename__ = current_app.users_table
    __table_args__ = {
        "schema": "sde",
        'extend_existing': True
    }

    email = db.Column(
        db.String(50),
        primary_key=True
    )
    pasword = db.Column(
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
    agency = db.Column(
        db.String(255),
        primary_key=False
    )
    is_admin = db.Column(
        db.String(3),
        primary_key=False
    )
    is_authorized = db.Column(
        db.String(3),
        primary_key=False
    )
    signup_date = db.Column(
        db.String(3),
        primary_key=False
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