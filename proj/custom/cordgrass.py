from inspect import currentframe
from flask import current_app, session
from .functions import checkData, get_badrows
import pandas as pd

def cordgrass(df, tablename):
    current_function_name = str(currentframe().f_code.co_name)
    print(current_function_name)


    errs = []
    warnings = []

    # Alter this args dictionary as you add checks and use it for the checkData function
    # for errors that apply to multiple columns, separate them with commas
    args = {
        "dataframe": df,
        "tablename": tablename,
        "badrows": [],
        "badcolumn": "",
        "error_type": "",
        "is_core_error": False,
        "error_message": ""
    }

    # Example of appending an error (same logic applies for a warning)
    # args.update({
    #     "badrows": get_badrows(datalogger[datalogger.temperature != 5], badcol = 'temperature', message = "The temperature should be 5, not __value__"),
    #     "badcolumn": "temperature",
    #     "error_type" : "Not 5",
    #     "error_message" : "The temperature should be 5"
    # })
    # errs = [*errs, checkData(**args)]

    
    return {'errors': errs, 'warnings': warnings}