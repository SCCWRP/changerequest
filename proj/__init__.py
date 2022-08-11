import os, json
import numpy as np
import pandas as pd
from flask import Flask, g
from flask_cors import CORS
from sqlalchemy import create_engine
from .export import export
from .login import login
from .main import comparison
from .finalize import finalize
from .custom.functions import add_custom_checks_function

CUSTOM_CONFIG_PATH = os.path.join(os.getcwd(), 'proj', 'config')
assert os.path.exists(os.path.join(CUSTOM_CONFIG_PATH, 'config.json')), \
    f"{os.path.join(CUSTOM_CONFIG_PATH, 'config.json')} configuration file not found"

CUSTOM_CONFIG = json.loads( open( os.path.join(CUSTOM_CONFIG_PATH, 'config.json'), 'r' ).read() )

app = Flask(__name__, static_url_path='/static')
app.debug = True # remove for production

CORS(app)
# does your application require uploaded filenames to be modified to timestamps or left as is
app.config['CORS_HEADERS'] = 'Content-Type'

app.config['MAIL_SERVER'] = CUSTOM_CONFIG.get('mail_server')
app.config['SESSION_TYPE'] = 'filesystem'

app.config['MAX_CONTENT_LENGTH'] = 200 * 1024 * 1024  # 100MB limit
app.secret_key = os.environ.get('FLASK_APP_SECRET_KEY')
app.infile = ""

app.maintainers = CUSTOM_CONFIG.get('maintainers')

app.send_from = CUSTOM_CONFIG.get('send_from')


# list of database fields that should not be queried on - removed status could be a problem 9sep17 - added trawl calculated fields - removed projectcode for smc part of tbl_phab
app.system_fields = [
    "globalid", "submissionid", "created_user", "created_date", "last_edited_user", "last_edited_date", "warnings"
]

app.custom_unchanging_fields = CUSTOM_CONFIG.get('custom_unchanging_fields')

# All fields that begin with login must also be immutable
app.immutable_fields = [
    *app.system_fields, *app.custom_unchanging_fields
]

# set the database connection string, database, and type of database we are going to point our application at
app.eng = create_engine(os.environ.get('DB_CONNECTION_STRING'))

# set the database connection string, database, and type of database we are going to point our application at
#app.eng = create_engine(environ.get("DB_CONNECTION_STRING"))
def connect_db():
    return create_engine(os.environ.get("DB_CONNECTION_STRING"))

@app.before_request
def before_request():
    g.eng = connect_db()

@app.teardown_request
def teardown_request(exception):
    if hasattr(g, 'eng'):
        g.eng.dispose()


class NpEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, np.integer):
            return int(obj)
        if isinstance(obj, np.floating):
            return float(obj)
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        if isinstance(obj, pd.Timestamp):
            return obj.strftime("%Y-%m-%d %H:%M:%S")
        return super(NpEncoder, self).default(obj)

app.json_encoder = NpEncoder


app.dtypes = CUSTOM_CONFIG.get('dtypes')

app.register_blueprint(export)
app.register_blueprint(login)
app.register_blueprint(comparison)
app.register_blueprint(finalize)


# When the app starts up, it will check to see if all the custom checks functions exist if they were specified in the config file
# If they were not specified, it will create the file and the function
def add_custom_checks_function(directory, func_name):
    func_name = str(func_name).lower()
    
    newfilepath = os.path.join(directory, f"{func_name}_custom.py")
    
    if os.path.exists(newfilepath):
        print(f"{newfilepath} already exists")
        return
        
    # The reason i do an if statement rather than an assert is because i dont want to prevent the app from running altogether
    templatefilepath = os.path.join(directory, f"example.py")
    if not os.path.exists(templatefilepath):
        print(f"example.py not found in {directory}")

    newfile = open(newfilepath, 'w')
    templatefile = open(templatefilepath, 'r')

    for line in templatefile:
        newfile.write(line.replace('__example__', func_name))
    
    newfile.close()
    templatefile.close()

    initfile = open(os.path.join(directory, '__init__.py'), 'a')
    initfile.write(f'\nfrom .{func_name}_custom import {func_name}')

    if os.path.exists(newfilepath):
        print("Success")
        return True
    else:
        print("Something went wrong")
        return False
    
    



tmpdtypes = CUSTOM_CONFIG.get('dtypes')
custom_dir = os.path.join(os.getcwd(), 'proj','custom')
for dtyp in tmpdtypes.keys():
    for tbl, func_name in tmpdtypes.get(dtyp).get("custom_checks_functions").items():
        add_custom_checks_function(custom_dir, func_name)

# App depends on a schema called tmp existing in the database
app.eng.execute("CREATE SCHEMA IF NOT EXISTS tmp;")