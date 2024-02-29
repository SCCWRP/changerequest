import pandas as pd
import re
from math import log10
from .functions import checkData, convert_dtype, fetch_meta, check_precision, check_length, check_scale, coalesce
from flask import current_app
from inspect import currentframe

def checkDataTypes(dataframe, tablename, eng, meta, *args, output = None, **kwargs):
    print("BEGIN checkDataTypes")
    ret = []
    for col in dataframe.columns: 
        if col not in current_app.system_fields:
            print("meta")
            print(meta)
            
            # col must be in the list of column names in the metadata dataframe
            assert \
                col in meta.column_name.values, \
                f"in function {str(currentframe().f_code.co_name)} - {col} not found in the list of column names that we are checking"
            
            # using the meta dataframe we can get the python datatype
            dtype = meta.iloc[
                meta[
                    meta.column_name == col
                ].index, 
                meta.columns.get_loc("dtype")
            ] \
            .values[0]


            ret.append(
                checkData(
                    dataframe = dataframe,
                    tablename = tablename,
                    badrows = [
                        {
                            'row_number': rownum,
                            'objectid': coalesce(objid, -220),
                            'value': coalesce(val),
                            'message': msg
                        } 
                        for rownum, objid, val, msg in
                            dataframe[
                                dataframe[col].apply(
                                    # the reason we negate is because bad rows would be considered to be ones that could not convert
                                    lambda x: not convert_dtype(dtype, x)
                                )
                            ] \
                            .apply(
                                lambda row:
                                (
                                    row.name + 1,
                                    row['objectid'],
                                    row[col], 
                                    f"The value entered here ({row[col]}) cannot be interpreted as the datatype {dtype}"
                                ),
                                axis = 1
                            ) \
                            .values
                    ],
                    badcolumn = col,
                    error_type = "Invalid Datatype",
                    is_core_error = True,
                    error_message = f"The value here is not valid for the datatype {dtype}"
                )
            )
            print("ret:")
            print(ret)
        

    print("-----before if output-----")
    print("dataframe.columns")
    print(dataframe.columns)
    if output:
        print("---enter if output---")
        output.put(ret)
    print("END checkDataTypes")
    return ret
    

def checkPrecision(dataframe, tablename, eng, meta, *args, output = None, **kwargs):
    print("BEGIN checkPrecision")
    ret = []
    for col in dataframe.columns:
        
        if (
            (col in meta[meta.udt_name == 'numeric'].column_name.values)
            and (col not in current_app.system_fields)
        ):
            assert \
                col in meta.column_name.values, \
                f"in function {str(currentframe().f_code.co_name)} - {col} not found in the list of column names that we are checking"

            prec = int(
                meta.iloc[
                    meta[
                        meta.column_name == col
                    ].index, 
                    meta.columns.get_loc("numeric_precision")
                ] \
                .values[0]
            )

            ret.append(
                checkData(
                    dataframe = dataframe,
                    tablename = tablename,
                    badrows = [
                        {
                            'row_number': rownum,
                            'objectid': coalesce(objid, -220),
                            'value': coalesce(val),
                            'message': msg
                        } 
                        for rownum, objid, val, msg in
                        
                        dataframe[
                            dataframe[col].apply(
                                lambda x:
                                not check_precision(x,prec)
                            )
                        ].apply(
                            lambda row:
                            (
                                row.name + 1,
                                row['objectid'],
                                row[col],
                                f"too many significant digits for a column of precision {prec}"
                            ),
                            axis = 1
                        ).values
                    ],
                    badcolumn = col,
                    error_type = "Value too long",
                    is_core_error = True,
                    error_message = f"the value here is too long for the column {col} which allows {prec} significant digits"
                )
            )

    if output:
        output.put(ret)
    print("END checkPrecision")
    return ret

def checkScale(dataframe, tablename, eng, meta, *args, output = None, **kwargs):
    print("BEGIN checkScale")
    ret = []
    for col in dataframe.columns:
        if (
            (col in meta[meta.udt_name == 'numeric'].column_name.values)
            and (col not in current_app.system_fields)
        ):
            assert \
                col in meta.column_name.values, \
                f"in function {str(currentframe().f_code.co_name)} - {col} not found in the list of column names that we are checking"
            scale = int(
                meta.iloc[
                    meta[
                        meta.column_name == col
                    ].index, 
                    meta.columns.get_loc("numeric_scale")
                ] \
                .values[0]
            )

            ret.append(
                checkData(
                    dataframe = dataframe,
                    tablename = tablename,
                    badrows = [
                        {
                            'row_number': rownum,
                            'objectid': coalesce(objid, -220),
                            'value': coalesce(val),
                            'message': msg
                        } 
                        
                        for rownum, objid, val, msg in
                        
                        dataframe[
                            dataframe[col].apply(
                                lambda x:
                                not check_scale(x,scale)
                            )
                        ].apply(
                            lambda row:
                            (
                                row.name + 1,
                                row['objectid'],
                                row[col],
                                f"The value here {row[col]} will be rounded to {scale} decimal places when it is loaded to the database"
                            ), 
                            axis = 1
                        ).values
                    ],
                    badcolumn = col,
                    error_type = "Value too long",
                    is_core_error = True,
                    error_message = f"The value here will be rounded to {scale} decimal places when it is loaded to the database"
                )
            )
        

    if output:
        output.put(ret) 
    print("END checkScale")
    return ret


def checkLength(dataframe, tablename, eng, meta, *args, output = None, **kwargs):
    print("BEGIN checkLength")

    # ret for return, or the item that will be returned
    ret = []
    for col in dataframe.columns:
        if (
            (col in meta[~pd.isnull(meta.character_maximum_length)].column_name.values)
            and (col not in current_app.system_fields)
        ):
            assert \
                col in meta.column_name.values, \
                f"in function {str(currentframe().f_code.co_name)} - {col} not found in the list of column names that we are checking"
            maxlen = int(
                meta.iloc[
                    meta[
                        meta.column_name == col
                    ].index, 
                    meta.columns.get_loc("character_maximum_length")
                ] \
                .values[0]
            )

            ret.append(
                checkData(
                    dataframe = dataframe,
                    tablename = tablename,
                    #badrows = dataframe[(~pd.isnull(dataframe[col])) & (dataframe[col].astype(str).str.len() > maxlen)].index.tolist(),
                    badrows = [
                        {
                            'row_number': rownum,
                            'objectid': coalesce(objid, -220),
                            'value': coalesce(val),
                            'message': msg
                        }
                        for rownum, objid, val, msg in
                        dataframe[(~pd.isnull(dataframe[col])) & (dataframe[col].astype(str).str.len() > maxlen)].apply(
                            lambda row:
                            (
                                row.name + 1,
                                row['objectid'],
                                row[col],
                                f"The value here has {len(row[col])} characters, while the character limit is {maxlen}"
                            ),
                            axis = 1
                        ).values
                    ],
                    badcolumn = col,
                    error_type = "Value too long",
                    is_core_error = True,
                    error_message = f"The value here has too many characters, while the character limit is {maxlen}"
                )
        
            )

    if output:
        output.put(ret) 
    print("END checkLength")
    return ret



def checkNotNull(dataframe, tablename, eng, meta, *args, output = None, **kwargs):
    print("BEGIN checkNotNULL")

    ret = \
    [
        checkData(
            dataframe = dataframe,
            tablename = tablename,
            badrows = [
                {
                    'row_number': rownum,
                    'objectid': coalesce(objid, -220),
                    'value': coalesce(val),
                    'message': msg
                }
                for rownum, objid, val, msg in
                dataframe[
                    dataframe[col].apply(
                        lambda x:
                        True if ((pd.isnull(x)) or (x == '')) else False
                    )
                ].apply(
                    lambda row:
                    (
                        row.name + 1,
                        row['objectid'],
                        row[col],
                        f"There is an empty value here, but the column {col} requires a value in all rows"
                    ),
                    axis = 1
                ).values
            ],
            badcolumn = col,
            error_type = "Missing Required Data",
            is_core_error = True,
            error_message = f"There is an empty value here, but the column {col} requires a value in all rows"
        )
        for col in dataframe.columns 
        if (
            (col in meta[meta.is_nullable == 'NO'].column_name.values)
            and (col not in current_app.system_fields)
        )
    ]

    if output:
        output.put(ret) 

    print("END checkNotNULL")
    return ret



def checkIntegers(dataframe, tablename, eng, meta, *args, output = None, **kwargs):
    print("BEGIN checkIntegers")
    ret = []
    for col in dataframe.columns:
        if (
                (col in meta[meta.udt_name.isin(['int2','int4','int8'])].column_name.values)
                and (col not in current_app.system_fields)
        ):
            assert \
                col in meta.column_name.values, \
                f"in function {str(currentframe().f_code.co_name)} - {col} not found in the list of column names that we are checking"
            
            udt_name = meta.iloc[meta[meta.column_name == col].index, meta.columns.get_loc("udt_name")].values[0]
            try:
                ret.append(
                    checkData(
                        dataframe = dataframe,
                        tablename = tablename,
                        badrows = [
                            {
                                'row_number': rownum,
                                'objectid': coalesce(objid, -220),
                                'value': coalesce(val),
                                'message': msg
                            }
                            for rownum, objid, val, msg in
                            dataframe[
                                dataframe[col].apply(
                                    lambda x:
                                    False if pd.isnull(x)
                                    # coerce the values to integers since they show up as strings coming in from the browser
                                    # if the datatype is bad, the datatypes check should catch it
                                    else not ( (int(x) >= -32768) & (int(x) <= 32767) )
                                    if udt_name == 'int2'
                                    else not ( (int(x) >= -2147483648) & (int(x) <= 2147483647) )
                                    if udt_name == 'int4'
                                    else not ( (int(x) >= -9223372036854775808) & (int(x) <= 9223372036854775807) )
                                    if udt_name == 'int8'
                                    
                                    # if something else slips through the cracks, this will not allow it through by default
                                    else True 
                                )
                            ].apply(
                                lambda row:
                                (
                                    row.name + 1,
                                    row['objectid'],
                                    row[col],
                                    "The column {} allows integer values from {}" \
                                    .format(
                                        col,
                                        "-32768 to 32767"
                                        if udt_name == 'int2'
                                        else  "-2147483648 to 2147483647"
                                        if udt_name == 'int4'
                                        else  "-9223372036854775808 to 9223372036854775807"
                                        if udt_name == 'int8'

                                        # It should never be anything other than the above cases, since below we are filtering for int2, 4, and 8 columns.
                                        else "(unexpected error occurred. If you see this, contact it@sccwrp.org)"
                                    )
                                ),
                                axis = 1
                            ).values
                        ],
                        badcolumn = col,
                        error_type = "Value out of range",
                        is_core_error = True,
                        error_message = "The column {} allows integer values from {}" \
                            .format(
                                col,
                                "-32768 to 32767"
                                if udt_name == 'int2'
                                else  "-2147483648 to 2147483647"
                                if udt_name == 'int4'
                                else  "-9223372036854775808 to 9223372036854775807"
                                if udt_name == 'int8'

                                # It should never be anything other than the above cases, since below we are filtering for int2, 4, and 8 columns.
                                else "(unexpected error occurred. If you see this, contact it@sccwrp.org)"
                            )
                    )
                )
            except Exception as e:
                print("Exception occurred in checkIntegers")
                print(e)
                continue

         
       

    if output:
        output.put(ret)
    print("END checkIntegers")
    return ret