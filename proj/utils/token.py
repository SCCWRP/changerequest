import os
from itsdangerous import URLSafeTimedSerializer

def generate_confirmation_token(email):
    serializer = URLSafeTimedSerializer(os.environ.get('FLASK_APP_SECRET_KEY'))
    return serializer.dumps(email, salt=os.environ.get('FLASK_APP_SECURITY_PASSWORD_SALT'))


def confirm_token(token, expiration=3600):
    serializer = URLSafeTimedSerializer(os.environ.get('FLASK_APP_SECRET_KEY'))
    try:
        email = serializer.loads(
            token,
            salt=os.environ.get('FLASK_APP_SECURITY_PASSWORD_SALT'),
            max_age=expiration
        )
    except:
        return False
    return email