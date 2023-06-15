import pandas_access as mdb
import pandas as pd
import os
import re
import glob

def checkData(tablename, badrows, badcolumn, error_type, error_message = "Error", is_core_error = False, errors_list = [], q = None, **kwargs):
    
    # See comments on the get_badrows function
    # doesnt have to be used but it makes it more convenient to plug in a check
    # that function can be used to get the badrows argument that would be used in this function
    
    if len(badrows) > 0:
        if q is not None:
            # This is the case where we run with multiprocessing
            # q would be a mutliprocessing.Queue() 
            q.put({
                "table": tablename,
                "rows":badrows,
                "columns":badcolumn,
                "error_type":error_type,
                "is_core_error" : is_core_error,
                "error_message":error_message
            })

        return {
            "table": tablename,
            "rows":badrows,
            "columns":badcolumn,
            "error_type":error_type,
            "is_core_error" : is_core_error,
            "error_message":error_message
        }
    return {}
        



# checkLogic() returns indices of rows with logic errors
def checkLogic(df1, df2, cols: list, error_type = "Logic Error", df1_name = "", df2_name = ""):
    ''' each record in df1 must have a corresponding record in df2'''
    print(f"cols: {cols}")
    print(f"df1 cols: {df1.columns.tolist()}")
    print(set([x.lower() for x in cols]).issubset(set(df1.columns)))

    print(f"df2 cols: {df2.columns.tolist()}")
    assert \
    set([x.lower() for x in cols]).issubset(set(df1.columns)), \
    "({}) not in columns of {} ({})" \
    .format(
        ','.join([x.lower() for x in cols]), df1_name, ','.join(df1.columns)
    )
    print("passed 1st assertion")
    assert \
    set([x.lower() for x in cols]).issubset(set(df2.columns)), \
    "({}) not in columns of {} ({})" \
    .format(
        ','.join([x.lower() for x in cols]), df2_name, ','.join(df2.columns)
    )
    print("passed 2nd assertion")
    # 'Kristin wrote this code in ancient times.'
    # 'I still don't fully understand what it does.'
    # all() returns whether all elements are true
    print("before badrows")
    badrows = df1[~df1[[x.lower() for x in cols]].isin(df2[[x.lower() for x in cols]].to_dict(orient='list')).all(axis=1)].index.tolist()
    print(f"badrows: {badrows}")
    print("after badrows")
    #consider raising error if cols list is not str (see mp) --- ask robert though bc maybe nah

    return(badrows)

# ---- A few custom checks common to taxonomy, toxicity, and chemistry ---- #
def check_multiple_dates_within_site(submission):
    assert 'stationcode' in submission.columns, "'stationcode' is not a column in submission dataframe"
    assert 'sampledate' in submission.columns, "'sampledate' is not a column in submission dataframe"
    assert 'tmp_row' in submission.columns, "'tmp_row' is not a column in submission dataframe"
    assert not submission.empty, "submission dataframe is empty"

    # group by station code and sampledate, grab the first index of each unique date, reset to dataframe
    submission_groupby = submission.groupby(['stationcode','sampledate'])['tmp_row'].first().reset_index()

    # filter on grouped stations that have more than one unique sample date, output sorted list of indices 
    badrows = sorted(list(set(submission_groupby.groupby('stationcode').filter(lambda x: x['sampledate'].count() > 1)['tmp_row'])))

    # count number of unique dates within a stationcode
    num_unique_sample_dates = len(badrows)
    return (badrows, num_unique_sample_dates)

def check_missing_phab_data(submission, phab_data):
    assert 'stationcode' in submission.columns, "'stationcode' is not a column in submission dataframe"
    assert 'sampledate' in submission.columns, "'sampledate' is not a column in submission dataframe"
    assert 'tmp_row' in submission.columns, "'tmp_row' is not a column in submission dataframe"
    assert 'stationcode' in phab_data.columns, "'stationcode' is not a column in phab dataframe"
    assert 'sampledate' in phab_data.columns, "'sampledate' is not a column in phab dataframe"
    assert not submission.empty, "submission dataframe is empty"

    # group by stationcode and sampledate, grab first row in each group, reset back to dataframe from pandas groupby object 
    submission_groupby = submission.groupby(['stationcode','sampledate'])['tmp_row'].first().reset_index()

    # join submission df on phab_data on the stationcode in order to compare sampledates from both dfs
    # note that the 2 distinct sampledate columns get _sub and _phab added to differentiate them
    # left join in case there is no record in the phab table for a particular stationcode 
    merge_sub_with_phab = pd.merge(submission_groupby, phab_data, how = 'left', on = 'stationcode', suffixes=("_sub", "_phab"))

    merge_sub_with_phab['sampledate_sub'] = pd.to_datetime(merge_sub_with_phab['sampledate_sub'])
    merge_sub_with_phab['sampledate_phab'] = pd.to_datetime(merge_sub_with_phab['sampledate_phab'])
    # boolean mask that checks if the years in the sampledate columns are the same
    is_same_year = merge_sub_with_phab['sampledate_sub'].dt.year == merge_sub_with_phab['sampledate_phab'].dt.year
    
    # get all rows that do not have matching years
    mismatched_years = merge_sub_with_phab[~is_same_year]

    # get sorted lists of indices and stationcodes of rows with mismatched years 
    # used in the warning message later
    badrows = sorted(list(set(mismatched_years['tmp_row'])))
    badsites = list(set(mismatched_years['stationcode']))
    return (badrows, badsites)

def check_mismatched_phab_date(submission, phab_data):
    assert 'stationcode' in submission.columns, "'stationcode' is not a column in submission dataframe"
    assert 'sampledate' in submission.columns, "'sampledate' is not a column in submission dataframe"
    assert 'tmp_row' in submission.columns, "'tmp_row' is not a column in submission dataframe"
    assert 'stationcode' in phab_data.columns, "'stationcode' is not a column in phab dataframe"
    assert 'sampledate' in phab_data.columns, "'sampledate' is not a column in phab dataframe"
    assert not submission.empty, "submission dataframe is empty"

    # group by stationcode and sampledate, grab first row in each group, reset back to dataframe from pandas groupby object 
    submission_groupby = submission.groupby(['stationcode','sampledate'])['tmp_row'].first().reset_index()

    # join submission df on phab_data on the stationcode in order to compare sampledates from both dfs
    # note that the 2 distinct sampledate columns get _sub and _phab added to differentiate them
    # left join in case there is no record in the phab table for a particular stationcode 
    merge_sub_with_phab = pd.merge(submission_groupby, phab_data, how = 'left', on = 'stationcode', suffixes=("_sub", "_phab"))

    merge_sub_with_phab['sampledate_sub'] = pd.to_datetime(merge_sub_with_phab['sampledate_sub'])
    merge_sub_with_phab['sampledate_phab'] = pd.to_datetime(merge_sub_with_phab['sampledate_phab'])
    # boolean mask that checks if the years in the sampledate columns are the same
    is_same_year = merge_sub_with_phab['sampledate_sub'].dt.year == merge_sub_with_phab['sampledate_phab'].dt.year
    # boolean mask that checks if the dates in the sampledate columns are the same
    is_same_date = merge_sub_with_phab['sampledate_sub'] == merge_sub_with_phab['sampledate_phab']

    # get all rows that have same year but not same date
    matched_years = merge_sub_with_phab[is_same_year & ~is_same_date]

    # get sorted lists of indices and stationcodes of rows with same years but mismatched dates
    # used in the warning message later
    badrows = sorted(list(matched_years['tmp_row']))
    phabdates = list(set(matched_years['sampledate_phab'].dt.strftime('%m-%d-%Y')))
    return (badrows, phabdates)


# ---- Below is just for PHAB ---- #

# This file contains the python dictionary that represents what the schema SHOULD look like for all submitted PHAB Access Databases
# It also contains the code which checks to make sure that what they submitted contains all required tables and columns

# We need to have a dictionary that contains the correct schema of the access database
# the schema will be a dictionary, the keys are the required table names
# The values are the columns that they are required to have in that table
# Now, if they ever change what data they want to grab from the submitted access database, we will need to update this dictionary
correct_schema = {
            'Sample_Entry':set([
                    "SampleRowID","EventCode","ProtocolCode","StationCode","SampleDate","AgencyCode","ProjectCode","SampleComments"
                ]),
            'EventLookUp':set([
                    "EventCode","EventName"
                ]),
            'ProtocolLookUp':set([
                    "ProtocolCode","ProtocolName"
                ]),
            'StationLookUp':set([
                    "StationCode","StationName","LocalWatershed","HydrologicUnit","EcoregionLevel3Code","UpstreamArea","County"
                ]),
            'AgencyLookUp':set([
                    "AgencyCode","AgencyName"
                ]),
            'ProjectLookUp':set([
                    "ParentProjectCode","ProjectCode","ProjectName"
                ]),
            'QALookUp':set([
                    "QACode","QAName","QADescr"
                ]),
            'ResQualLookUp':set([
                    "ResQualCode","ResQualName"
                ]),
            'StationDetailLookUp':set([
                    "StationCode","TargetLatitude","TargetLongitude","Datum"
                ]),
            'Location_Entry':set([
                    "SampleRowID","LocationCode","GeometryShape","LocationRowID"
                ]),
            'LocationLookUp':set([
                    "LocationCode","LocationName"
                ]),
            'ParentProjectLookUp':set([
                    "ParentProjectCode","ParentProjectName"
                ]),
            'CollectionMethodLookUp':set([
                    "CollectionMethodCode","CollectionMethodName"
                ]),
            'ConstituentLookUp':set([
                    "ConstituentRowID","MatrixCode","AnalyteCode","FractionCode","UnitCode","MethodCode"
                ]),
            'MatrixLookUp':set([
                    "MatrixCode","MatrixName"
                ]),
            'MethodLookUp':set([
                    "MethodCode","MethodName"
                ]),
            'AnalyteLookUp':set([
                    "AnalyteCode","AnalyteName"
                ]),
            'UnitLookUp':set([
                    "UnitCode","UnitName"
                ]),
            'FractionLookUp':set([
                    "FractionCode","FractionName"
                ]),
            'CollectionDeviceLookUp':set([
                    "CollectionDeviceCode","CollectionDeviceName"
                ]),
            'ComplianceLookUp':set([
                    "ComplianceCode","ComplianceName"
                ]),
            'BatchVerificationLookUp':set([
                    "BatchVerificationCode","BatchVerificationName"
                ]),
            'FieldCollection_Entry':set([
                    "FieldCollectionRowID","LocationRowID","CollectionTime","CollectionMethodCode","Replicate","CollectionDepth",
                    "UnitCollectionDepth","FieldCollectionComments"    
                ]),
            'FieldResult_Entry':set([
                    "FieldResultRowID","FieldCollectionRowID","ConstituentRowID","FieldReplicate","Result","ResQualCode","QACode",
                    "ComplianceCode","BatchVerificationCode","CollectionDeviceCode","CalibrationDate","FieldResultComments","ExportData"
                ]),
            'HabitatCollection_Entry':set([
                    "HabitatCollectionRowID","LocationRowID","CollectionTime","CollectionMethodCode","Replicate","HabitatCollectionComments"  
                ]),
            'HabitatResult_Entry':set([
                    "HabitatResultRowID","HabitatCollectionRowID","VariableResult","Result","ResQualCode","QACode","ComplianceCode",
                    "CollectionDeviceCode","HabitatResultComments","ExportData","ConstituentRowID"
                ]),
            'Geometry_Entry':set([
                    "LocationRowID","Latitude","Longitude"
                ])
        }

required_tables = correct_schema.keys()


def check_schema(db):
    'this function is to check the schema of the submitted file to see if it matches what it is supposed to be.'    

    submitted_schema = mdb.read_schema(db)
    print("submitted schema")
    print(submitted_schema)
    
    for key in submitted_schema.keys():
        print(key)
        submitted_schema[key] = set(submitted_schema[key])
    
    print("New submitted schema:")
    print(submitted_schema)

    missing_data_msgs = []
    # Check - They have to have the required tables in their access database
    if set(required_tables).issubset(set(submitted_schema.keys())):
        # They have all the tables
        print("No missing tables")

        # Check - Each table must have the required columns and datatypes.
        for tablename in required_tables:
            print('correct_schema[tablename]')
            print(correct_schema[tablename])
            print('submitted_schema[tablename]')
            print(submitted_schema[tablename])
            print("table %s in the submitted access database was missing the following columns:" % tablename)
            missing_columns = list(correct_schema[tablename] - submitted_schema[tablename])
            print("missing columns")
            print(missing_columns)
            if len(missing_columns) > 0:
                message = "Table %s was missing the following columns: %s" % (tablename, ','.join(missing_columns))
                print(message)
                missing_data_msgs.append(message)
             
    else:
        # This means they were missing required tables from their access database
        print("Missing required tables:")
        missing_tables = list(set(required_tables) - set(submitted_schema.keys()).intersection(set(required_tables)))
        print(missing_tables)
        missing_data_msgs.append("The following tables were missing from your access database: %s" % ','.join(missing_tables))

    print("missing_data_msgs:")
    print(missing_data_msgs)
    return missing_data_msgs

# The convert_dtype function is added to functions.py for custom checks. This has specifically been added for the result (text) column in multiple datatypes for SMC to ensure
# that the values for the result column is checked as a float to prevent the submission of any text to the result field. 
# 
def convert_dtype(t, x):
    try:
        if ((pd.isnull(x)) and (t == float)):
            # modified to check that t is float instead of int
            return True
        t(x)
        return True
    except Exception as e:
        if t == pd.Timestamp:
            # checking for a valid postgres timestamp literal
            # Postgres technically also accepts the format like "January 8 00:00:00 1999" but we won't be checking for that unless it becomes a problem
            datepat = re.compile("\d{4}-\d{1,2}-\d{1,2}\s*(\d{1,2}:\d{1,2}:\d{2}(\.\d+){0,1}){0,1}$")
            return bool(re.match(datepat, str(x)))
        return False

def multivalue_lookup_check(df, field, listname, listfield, dbconnection, displayfieldname = None, sep=','):
    """
    Checks a column of a dataframe against a column in a lookup list. Specifically if the column may have multiple values.
    The default is that the user enters multiple values separated by a comma, although the function may take other characters as separators
    
    Parameters:
    df               : The user's dataframe
    field            : The field name of the user's submitted dataframe
    listname         : The Lookup list name (for example lu_resqualcode)
    listfield        : The field of the lookup list table that we are checking against
    displayfieldname : What the user will see in the error report - defaults to the field argument 
                       it should still be a column in the dataframe, but with different capitalization

    Returns a dictionary of arguments to pass to the checkData function
    """

    # default the displayfieldname to the "field" argument
    displayfieldname = displayfieldname if displayfieldname else field

    # displayfieldname should still be a column of the dataframe, but just typically camelcased
    assert displayfieldname.lower() in df.columns, f"the displayfieldname {displayfieldname} was not found in the columns of the dataframe, even when it was lowercased"

    assert field in df.columns, f"In {str(currentframe().f_code.co_name)} (value against multiple values check) - {field} not in the columns of the dataframe"
    lookupvals = set(read_sql(f'''SELECT DISTINCT "{listfield}" FROM "{listname}";''', dbconnection)[listfield].tolist())

    if not 'tmp_row' in df.columns:
        df['tmp_row'] = df.index

    # hard to explain what this is doing through a code comment
    badrows = df[df[field].apply(lambda values: not set([val.strip() for val in str(values).split(sep)]).issubset(lookupvals) )].tmp_row.tolist()
    args = {
        "badrows": badrows,
        "badcolumn": displayfieldname,
        "error_type": "Lookup Error",
        "error_message": f"""One of the values here is not in the lookup list <a target = "_blank" href=/{current_app.script_root}/scraper?action=help&layer={listname}>{listname}</a>"""
    }

    return args

def nameUpdate(df, field, conditions, oldname, newname):
    """
    DESCRIPTION:
    This function returns an error if the field in df under conditions contains an oldname.
    
    PARAMETERS:
    
    df - pandas dataframe of interest
    field - string of the field of interest
    conditions - a dictionary of conditions placed on the dataframe (i.e. {'field':['condition1',...]})
    oldname - string of the name returned to user if found in field
    newname - string of the suggested fix for oldname.
    """
    print("function - nameUpdate")
    print("creating mask dataframe")
    mask = pd.DataFrame([df[k].isin(v) for k,v in conditions.items()]).T.all(axis = 1)
    print("extract the appropriate subset of the original dataframe (df)")
    sub = df[mask]
    print("Find where the column has the outdated name")
    errs = sub[sub[field].str.contains(oldname)]
    print(errs)
    print("Call the checkData function")
    checkData(errs.tmp_row.tolist(),field,'Undefined Error','error','%s must now be written as %s.' %(oldname, newname),df)

def add_custom_checks_function(directory, func_name):
    func_name = str(func_name).lower()
    
    newfilepath = os.path.join(directory, f"{func_name}_custom.py")
    
    if os.path.exists(newfilepath):
        print(f"{newfilepath} already exists")
        return
        
    # The reason i do an if statement rather than an assert is because i dont want to prevent the app from running altogether
    templatefilepath = os.path.join(directory, f"example.py")
    assert os.path.exists(templatefilepath), f"example.py not found in {directory}"

    newfile = open(newfilepath, 'w')
    templatefile = open(templatefilepath, 'r')

    for line in templatefile:
        newfile.write(line.replace('__example__', func_name))
    
    newfile.close()
    templatefile.close()

    initpath = os.path.join(directory, '__init__.py')
    assert(os.path.exists(initpath)), f"{initpath} not found"

    with open(initpath, 'a') as f:
        f.write(f"from .{func_name}_custom import {func_name}")

    if os.path.exists(newfilepath):
        print("Success")
        print(f"Custom check file {newfilepath} added.")
        print("fix_custom_imports function must run to import it into proj/custom/__init__.py so the function can be imported into main.py")
        return True
    else:
        print("Something went wrong")
        return False
    

def fix_custom_imports(directory):
    initpath = os.path.join(directory, '__init__.py')
    assert os.path.exists(initpath), f"{initpath} not found"
    custom_files_glob = glob.glob(os.path.join(directory, '*_custom.py'))

    print("custom checks files:")
    print(custom_files_glob)

    # function names should be the same as that which is before _custom.py
    # these function names should also match the keys of the datasets dictionary defined in the datasets.json configuration file
    # custom import statements would be all the import statements that should be in theory in the __init__.py file for the app to be correctly configured
    custom_import_statements = [
        f"""from .{f.rsplit('/', 1)[-1].rsplit('_',1)[0].strip()}_custom import {f.rsplit('/', 1)[-1].rsplit('_',1)[0].strip()}"""
        for f in custom_files_glob
    ]
    print(custom_import_statements)

    # current imports would be the import statements currently in the __init__.py file
    # An app that is configured correctly would have custom_import_statments the same as current_imports
    import_pattern = re.compile('from\s+\.(\w+)_custom\s+import\s+(\w+)')
    with open(initpath,'r') as initfile:
        # store all lines of the original init file
        initfile_all_lines_orig = [l.strip() for l in initfile.readlines()]
        current_imports = [imp.strip() for imp in initfile_all_lines_orig if bool(re.search(import_pattern, imp))]
        initfile.close()

    imports_to_delete = set(current_imports) - set(custom_import_statements)
    imports_to_add = set(custom_import_statements) - set(current_imports)
    
    with open(initpath,'w') as initfile:
        for line in initfile_all_lines_orig:
            if line.strip() not in imports_to_delete:
                initfile.write(f"{line}\n")
            
        for imp in imports_to_add:
            initfile.write(f"{imp}\n")
        initfile.close()

    print("custom imports updated")
    print(f"Current contents of {initpath}:")
    with open(initpath, 'r') as f:
        print(f.read())
        f.close()
    return