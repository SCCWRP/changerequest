import pandas as pd
import multiprocessing as mp
import time, json, os


# For the sake of checking the data in multiple ways at the same time
def multitask(functions: list, *args):
    '''funcs is a list of functions that will be turned into processes'''
    output = mp.Queue()
    processes = [mp.Process(target = function, args = (*args, output)) for function in functions]

    starttime = time.time()
    for p in processes:
        print("starting a process")
        p.start()
        
    for p in processes:
        print("joining processes")
        p.join()

    finaloutput = []
    while output.qsize() > 0:
        finaloutput.append(output.get())
    print("output from the multitask/mutliprocessing function")
    print(finaloutput)
    return finaloutput



def unixtime(dt):
    ''' dt being a datetime, or something that can be converted to pandas timestamp '''
    try:
        return (pd.Timestamp(dt, tz = 'UTC') - pd.Timestamp('1970-01-01', tz = 'UTC')) // pd.Timedelta('1s')
    except ValueError:
        return (pd.Timestamp(dt.tz_convert(None)) - pd.Timestamp('1970-01-01')) // pd.Timedelta('1s')


def change_history_update(row, original_df, sessionid, submissionid, login_info, organization, email_address):
    original_record = original_df[original_df.objectid == row.objectid]
    changed_record = json.dumps(row.to_dict()).replace("'","")
    original_record = json.dumps(pd.DataFrame(original_record).to_dict('records')).replace("'","")
    sql = f"""
        (
            '{original_record}',
            '{changed_record}',
            {sessionid},
            {submissionid},
            '{login_info}',
            '{organization}',
            '{email_address}',
            '{pd.Timestamp(sessionid, unit = 's').strftime("%Y-%m-%d %H:%M:%S")}',
            'No'
        )
        """
    
    return sql