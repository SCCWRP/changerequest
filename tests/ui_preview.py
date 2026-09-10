"""Offline UI fixtures only: never imports proj, connects to a database, or sends mail."""

import argparse
from html import escape
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import mimetypes
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import parse_qs, urlsplit

from jinja2 import Environment, FileSystemLoader, select_autoescape
from markupsafe import Markup


ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / 'proj' / 'static'
TABLES = ['tbl_precipitation', 'tbl_waterquality', 'tbl_flow']
CONFIG = json.loads((ROOT / 'proj' / 'config' / 'config.json').read_text())
ENVIRONMENT = Environment(loader=FileSystemLoader(ROOT / 'proj' / 'templates'), autoescape=select_autoescape(default=True))
ROUTES = {
    'login.index': '/', 'auth.signin': '/signin', 'auth.signup': '/signup',
    'auth.logout': '/signin', 'auth.reset_request': '/reset-request',
    'export.download_submission': '/submission-download',
    'export.download_change_history': '/download_change_history',
    'finalize.savechanges': '/final_submit',
}


class Field:
    def __init__(self, name, label, kind='text'):
        self.name = name
        self.label = Markup(f'<label for="{name}">{label}</label>')
        self.kind = kind
        self.errors = []

    def __html__(self):
        if self.kind == 'submit':
            return Markup(f'<input type="submit" value="{self.name}">')
        return Markup(f'<input type="{self.kind}" id="{self.name}" name="{self.name}" required>')


def url_for(endpoint, **values):
    return '/static/' + values['filename'] if endpoint == 'static' else ROUTES[endpoint]


def render(template, request_type='edit'):
    anonymous = template in ('signin', 'signup', 'reset_request', 'reset_password')
    form = SimpleNamespace(
        csrf_token=Markup('<input type="hidden" name="csrf_token" value="offline-fixture">'),
        email=Field('email', 'Email address', 'email'), password=Field('password', 'Password', 'password'),
        firstname=Field('firstname', 'First name'), lastname=Field('lastname', 'Last name'),
        organization=Field('organization', 'Organization'), confirm=Field('confirm', 'Confirm password', 'password'),
        confirm_password=Field('confirm_password', 'Confirm password', 'password'),
        submit=Field('Sign in' if template == 'signin' else 'Submit', '', 'submit'),
    )
    return ENVIRONMENT.get_template(template + '.jinja2').render(
        current_user=SimpleNamespace(is_authenticated=not anonymous, organization='SCCWRP', email='reviewer@example.org', is_admin='yes'),
        request=SimpleNamespace(script_root=''), config=CONFIG, dtypes=CONFIG['dtypes'],
        session={'submissionid': 1780430796, 'sessionid': 1789071600, 'submissiondate': '2026-06-02 20:06', 'dtype': 'monitoring'},
        login_fields={'agency': 'City of San Diego', 'email': 'agency.editor@example.org'},
        pkeys={table: ['sitename', 'eventid', 'monitoringstation'] for table in TABLES},
        pending_deletion=False, url_for=url_for, get_flashed_messages=lambda: [], form=form,
        success=True, request_type=request_type, session_user_email='reviewer@example.org',
        change_id=1789071600, submissionid=1780430796, datatype='monitoring', submissiondate='2026-06-02 20:06',
    )


def table_html(records, editable=False):
    columns = ['objectid', 'sitename', 'eventid', 'monitoringstation', 'datestart', 'timestart', 'dateend', 'timeend', 'volumetotal', 'volumeunits', 'comment']
    headings = ''.join(f'<th scope="col">{column}</th>' for column in columns)
    body = ''
    for position in range(records):
        values = [398 + position, 'Miramar Road BMP', 172526 + position, 'MM-EFF', '2026-02-19', '16:05:00', '2026-02-19', '18:25:00', 2644.70 + position, 'gal', 'Revised field measurement']
        cells = ''.join(
            f'<td class="colname-{column}"' + (' contenteditable="true"' if editable and column != 'objectid' else '') + f'>{escape(str(value))}</td>'
            for column, value in zip(columns, values)
        )
        body += f'<tr id="objectid-{398 + position}">{cells}</tr>'
    identifier = ' id="changes-display-table"' if editable else ''
    return f'<table{identifier}><thead><tr>{headings}</tr></thead><tbody>{body}</tbody></table>'


def report(kind='edit', errors=False):
    reports = {}
    for position, table in enumerate(TABLES):
        modified = 3 + position if kind == 'edit' else 0
        added = position if kind == 'edit' else 0
        deleted = 12 + position if kind == 'delete' else position
        checks = [{'columns': 'volumetotal', 'error_message': 'Total volume must be a number.', 'error_type': 'Invalid datatype',
                   'rows': [{'objectid': 398, 'row_number': 1}]}] if errors and position == 0 else []
        changes = [{'objectid': 398 + index, 'colname': 'volumetotal', 'rownumber': index + 1} for index in range(modified)]
        reports[table] = {
            'tbl': table_html(modified, True), 'addtbl': table_html(added), 'deltbl': table_html(deleted),
            'counts': {'modified': modified, 'added': added, 'deleted': deleted},
            'errors': checks, 'warnings': [], 'edit_rows': list(range(modified)),
            'accepted_changes': [] if checks else changes,
            'rejected_changes': [{'objectid': 398, 'colname': 'volumetotal'}] if checks else [],
        }
    return {'tables': reports, 'ready': not errors, 'revision': 1, 'request_type': kind, 'warnings': [], 'message': ''}


class PreviewHandler(BaseHTTPRequestHandler):
    def reply(self, content, content_type='text/html; charset=utf-8', status=200):
        body = content if isinstance(content, bytes) else content.encode()
        self.send_response(status)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        self.wfile.write(body)

    def json_reply(self, data):
        self.reply(json.dumps(data), 'application/json')

    def do_GET(self):
        parsed = urlsplit(self.path)
        path = parsed.path
        query = parse_qs(parsed.query)
        if path.startswith('/static/'):
            asset = (STATIC / path[len('/static/'):]).resolve()
            if STATIC not in asset.parents or not asset.is_file():
                self.reply('Not found', status=404)
                return
            self.reply(asset.read_bytes(), mimetypes.guess_type(str(asset))[0] or 'application/octet-stream')
        elif path == '/login_values':
            self.json_reply({'data': ['agency.editor@example.org'] if query.get('field') == ['email'] else ['City of San Diego', 'City of Los Angeles Watershed Protection']})
        elif path == '/submissions':
            self.json_reply({'submissions': [{'submissionid': 1780430796, 'submissiondate': '2026-06-02 20:06:36'}], 'message': ''})
        elif path == '/fixtures/report':
            self.json_reply(report(query.get('kind', ['edit'])[0], query.get('errors') == ['yes']))
        elif path in ('/', '/edit-submission', '/signin', '/signup', '/reset-request', '/reset-password', '/thankyou'):
            template = 'index' if path == '/' else path[1:].replace('-', '_') if path.startswith('/reset-') else path[1:]
            self.reply(render(template))
        else:
            self.reply('Offline preview: no real downloads or account operations.', status=404)

    def do_POST(self):
        self.rfile.read(int(self.headers.get('Content-Length', 0)))
        path = urlsplit(self.path).path
        if path == '/post-session-data':
            self.json_reply({'message': 'Success'})
        elif path in ('/compare', '/request-deletion'):
            self.json_reply(report('delete' if path == '/request-deletion' else 'edit'))
        elif path == '/final_submit':
            self.reply(render('thankyou'))
        else:
            self.reply('Offline preview: account operations disabled.', status=405)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=8765)
    parser.add_argument('--check', action='store_true')
    arguments = parser.parse_args()
    if arguments.check:
        for page in ('index', 'edit-submission', 'signin', 'signup', 'reset_request', 'reset_password', 'thankyou'):
            html = render(page)
            assert 'name="viewport"' in html
            assert 'id="main-content"' in html
        print('Seven UI fixtures rendered successfully. No app imports or database access.')
    else:
        print(f'Offline UI preview only: http://127.0.0.1:{arguments.port}', flush=True)
        ThreadingHTTPServer(('127.0.0.1', arguments.port), PreviewHandler).serve_forever()