import pandas as pd

def compare(df_origin, df_modified, pkey_columns, immutable_cols = []):
    print("comparison function")
    # merge the changed data with the original
    print("pkey_columns")
    print(pkey_columns)

    merged_df = df_origin.merge(df_modified, how = 'outer', on = pkey_columns, suffixes = ('_old',''))
    
    print("### non_pkey_columns simply refers to the columns that we are comparing. Everything except objectid")
    # non_pkey_columns simply refers to the columns that we are comparing. Everything except objectid
    non_pkey_columns = [col for col in df_origin.columns if col not in pkey_columns]
    print("non_pkey_columns")
    print(non_pkey_columns)

    print("### iterate through the rows of the merged dataframe to compare the values")
    # iterate through the rows of the merged dataframe to compare the values
    # and identify changed records
    merged_df['change_type'] = merged_df.apply(
        lambda x:
        "addition"
        # if all of the "old" column values are null, then the user added a new record
        if all(
            [pd.isnull(x[f'{col}_old']) for col in df_origin.columns if col not in pkey_columns]
        )
        else "deletion"
        # if all of the "new" columns have null values, then the user deleted a record
        if all(
            [pd.isnull(x[f'{col}']) for col in df_origin.columns if col  not in pkey_columns ]
        )
        else "modification"
        # if any of the old column values are different from the new columns values, it is a modified record
        if not all(
            [
                ( 
                    (
                        (x[f'{col}'] == x[f'{col}_old']) if col != 'mdl' else (float(x[f'{col}']) == float(x[f'{col}_old']))
                    )
                    | 
                    (
                        all(
                            map(
                                #pd.isnull,
                                # Treats NULLs and empty strings the same, since they are mixed around in our database
                                lambda value: pd.isnull(value) or value == '', 
                                [x[f'{col}'], x[f'{col}_old']] 
                            ) 
                        ) 
                    ) 
                )
                for col in df_origin.columns if col not in [*pkey_columns, *immutable_cols, 'objectid']
            ]
        )
        # if it doesn't meet any above case, there is no change and we return a Nonetype object
        else None 

        # don't forget that axis = 1 since the args passed to the lambda function are rows of the dataframe
        , axis = 1
    )

    pd.set_option('display.max_columns', None)
    print("merged_df")
    print(merged_df)
    print(merged_df.change_type)
    pd.set_option('display.max_columns', 4)

    print("### After comparing the data, we will replace the objectid column with objectid_old")
    # After comparing the data, we will replace the objectid column with objectid_old
    # The idea is that the objectid_old reflects the one that corresponds with the true record in the database
    # but the incoming objectid could have been messed with by the user

    # Now, object id should never be part of the primary key, but let's not assume so
    # They are still figuring out the primary key for unified chemistry
    # The thing doesn't actually work with chemistry... we rely heavily on the assumption that the table has a well defined primary key
    if 'objectid_old' in merged_df.columns:
        merged_df['objectid'] = merged_df['objectid_old']
    
    # Login fields must not be altered by the user
    for col in [c for c in merged_df.columns if str(c).startswith('login_')]:
        if f'{col}_old' in merged_df.columns:
            merged_df[col] = merged_df[f'{col}_old']

    # system fields or other columns we choose must not be altered by the user either
    for col in immutable_cols:
        if f'{col}_old' in merged_df.columns:
            merged_df[col] = merged_df[f'{col}_old']

    

    print("### Added records ")
    # Added records 
    added_records = merged_df[merged_df['change_type'] == "addition"]
    
    print("### Deleted records")
    # Deleted records
    deleted_records = merged_df[merged_df['change_type'] == "deletion"]

    
    print("### Get the merged_df back containing records with the same primary keys. We want to compare if there are any changes that are made by the users. ")
    # Get the merged_df back containing records with the same primary keys. We want to compare if there are any changes that are made by the users. 
    modified_records = merged_df[merged_df['change_type'] == 'modification'] \
        .drop(columns = ['change_type']) #\
        #.reset_index(drop = True)
    

    print("### create changed indices, a list of tuples indicating which cells got modified")
    # create changed indices, a list of tuples indicating which cells got modified
    # [(rownumber, column_name), (rownumber, column_name)]
    print("modified_records")
    print(modified_records)
    print(modified_records.columns)

    changed_indices = []
    modified_records.apply(
        lambda x:
        [   
            # Here we are simply taking advantage of the speed of list comp, to append to the changed indices variable
            changed_indices.append({'rownumber': int(x.name + 1), 'colname': str(col), 'objectid': int(x['objectid'])}) 
            for col in non_pkey_columns 
            if not ((x[f'{col}'] == x[f'{col}_old']) | (all(pd.isnull([x[f'{col}'], x[f'{col}_old']])))) 
        ],
        axis = 1
    )


    print("### sort alphabetically by column")
    # sort alphabetically by column
    modified_records = modified_records.sort_index(axis = 1)
    
    print("### The merging cols should show up first in the table")
    # The merging cols should show up first in the table
    modified_records = modified_records[
        pkey_columns + [col for col in modified_records.columns if col not in pkey_columns]
    ]
    
    print("### Split the records (original and modified) in modified_records")
    # Split the records (original and modified) in modified_records
    # Get column's names for original excel tab and modified excel tab 
    original_cols =  pkey_columns + [col for col in modified_records.columns if (col not in pkey_columns) & ("_old" in col)]
    new_cols =  pkey_columns + [col for col in modified_records.columns if (col not in pkey_columns) & ("_old" not in col) ] 
    
    print("### Create the dataframes so we can write them to excel later")
    # Create the dataframes so we can write them to excel later
    original_data = modified_records[original_cols] \
        .rename(columns = {col:col.replace("_old","") for col in original_cols if col not in pkey_columns}) \
        .reset_index(drop=True)

    # Keep only the columns we need on the 3 dataframes
    modified_records = modified_records[new_cols].reset_index(drop=True)
    added_records = added_records[new_cols].reset_index(drop=True)
    deleted_records = deleted_records[original_cols].reset_index(drop=True)
    deleted_records.columns = [x.replace("_old","") for x in deleted_records.columns]

    print("end comparison function")
    return added_records, deleted_records, modified_records, changed_indices, original_data
    


def highlight_changes(worksheet, color, cells):
    """
        worksheet: the excel worksheet being formatted,
        color: the format that will be added,
        cells: list of tuples, indicating the coordinates of the cells to be highlighted

        This function aims to utilie the speed of the list comprehension for loop, without returning anything
    """
    [
        worksheet.conditional_format(
            # coord is a tuple of the coordinates of cells that were changed, and need to be highlighted
            coord[0], coord[1], coord[0], coord[1],
            {
                'type': 'no_errors',
                'format': color
            }
        )
        for coord in cells
    ]
    return None
