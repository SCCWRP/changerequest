import multiprocessing as mp
import pandas as pd
import time
from itertools import chain
from .dupes import checkDuplicates, checkDuplicatesInProduction
from .lookups import checkLookUpLists
from .metadata import checkNotNull, checkPrecision, checkScale, checkLength, checkDataTypes, checkIntegers
from .functions import fetch_meta, multitask


# goal here is to take in all_dfs as an argument and assemble the CoreChecker processes
def core(df, tblname, eng, debug = False):

    meta = fetch_meta(tblname, eng)

    errs = []
    warnings = []
    errs.extend(
        [
            checkDataTypes(df, tblname, eng, meta),
            checkDuplicates(df, tblname, eng, meta),
            checkDuplicatesInProduction(df, tblname, eng, meta),
            checkLookUpLists(df, tblname, eng, meta),
            checkNotNull(df, tblname, eng, meta),
            checkIntegers(df, tblname, eng, meta),
            checkPrecision(df, tblname, eng, meta),
            checkScale(df, tblname, eng, meta),
            checkLength(df, tblname, eng, meta)
        ]
        
        if debug 
        else
        
        multitask(
            [
                checkDataTypes,
                checkDuplicates,
                checkDuplicatesInProduction,
                checkLookUpLists,
                checkNotNull,
                checkIntegers,
                checkPrecision,
                checkScale,
                checkLength
            ],
            df,
            tblname,
            eng,
            meta
        )
    )


    # Paul decided that check Scale should be an error rather than a warning
    # This was implemented for the checker and we are now putting it in the change request app
    # 
    # warnings.extend(
    #     [checkScale(df, tblname, eng, meta)]
    #     if debug 
    #     else
    #     multitask([checkScale], df, tblname, eng, meta)
    # )

    print("errs")
    print(errs)
    print("warnings")
    print(warnings)
    # flatten the lists
    return {
        "core_errors": [e for sublist in errs for e in sublist if ( e != dict() and e != set() )],
        "core_warnings": [w for sublist in warnings for w in sublist if ( w != dict() and w != set() )]
    }
    
