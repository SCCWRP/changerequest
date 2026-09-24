#################################################################
# One-time sign-in codes, used when user_management.login_method
# is "email_code" in config.json (instead of passwords)
#################################################################
import os, hmac, hashlib, secrets
from datetime import datetime, timedelta
from sqlalchemy import text

CODE_LENGTH = 6
CODE_TTL = timedelta(minutes = 10)
MAX_ATTEMPTS = 5
RESEND_INTERVAL = timedelta(seconds = 60)


def code_login_enabled(config):
    return (config.get('user_management') or {}).get('login_method') == 'email_code'


def codes_table(users_table):
    # users_table comes from config.json, not from the user
    return f'"sde"."{users_table}_login_codes"'


def create_codes_table(eng, users_table):
    with eng.begin() as conn:
        conn.execute(text(
            f"""
            CREATE TABLE IF NOT EXISTS {codes_table(users_table)} (
                "id" SERIAL PRIMARY KEY,
                "email" varchar(255) NOT NULL,
                "code_hash" varchar(64) NOT NULL,
                "created_at" timestamp(6) NOT NULL DEFAULT now(),
                "expires_at" timestamp(6) NOT NULL,
                "attempts" int4 NOT NULL DEFAULT 0,
                "used_at" timestamp(6)
            )
            """
        ))


def _hash_code(email, code):
    # Keyed hash, so a leaked table row can't be brute forced back to a 6 digit code
    key = os.environ.get('FLASK_APP_SECRET_KEY').encode()
    return hmac.new(key, f"{email}:{code}".encode(), hashlib.sha256).hexdigest()


def issue_code(eng, users_table, email):
    """Returns a new code for the email, or None if one was sent too recently"""
    tbl = codes_table(users_table)
    now = datetime.now()
    with eng.begin() as conn:
        last_sent = conn.execute(
            text(f"SELECT max(created_at) FROM {tbl} WHERE email = :email"),
            {"email": email}
        ).scalar()
        if last_sent is not None and now - last_sent < RESEND_INTERVAL:
            return None

        # Only the newest code works - retire any older ones
        conn.execute(
            text(f"UPDATE {tbl} SET used_at = :now WHERE email = :email AND used_at IS NULL"),
            {"now": now, "email": email}
        )

        code = f"{secrets.randbelow(10 ** CODE_LENGTH):0{CODE_LENGTH}d}"
        conn.execute(
            text(f"INSERT INTO {tbl} (email, code_hash, created_at, expires_at) VALUES (:email, :code_hash, :now, :expires_at)"),
            {"email": email, "code_hash": _hash_code(email, code), "now": now, "expires_at": now + CODE_TTL}
        )
    return code


def verify_code(eng, users_table, email, code):
    """Returns True and uses up the code if it matches the email's live code"""
    tbl = codes_table(users_table)
    code = (code or '').strip()
    now = datetime.now()
    with eng.begin() as conn:
        row = conn.execute(
            text(
                f"""
                SELECT id, code_hash, attempts FROM {tbl}
                WHERE email = :email AND used_at IS NULL AND expires_at > :now
                ORDER BY created_at DESC LIMIT 1
                FOR UPDATE
                """
            ),
            {"email": email, "now": now}
        ).fetchone()

        if row is None or row.attempts >= MAX_ATTEMPTS:
            return False

        if hmac.compare_digest(row.code_hash, _hash_code(email, code)):
            conn.execute(text(f"UPDATE {tbl} SET used_at = :now WHERE id = :id"), {"now": now, "id": row.id})
            return True

        conn.execute(text(f"UPDATE {tbl} SET attempts = attempts + 1 WHERE id = :id"), {"id": row.id})
        return False
