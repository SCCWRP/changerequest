import pandas as pd

def htmltable(df, id = None, cssclass = None, enumeraterows = True):
    '''
        df is a pandas dataframe, 
        id is a css id you want to give to the table, 
        cssclass is a css class for the table,
        enumeraterows actually only distinguishes even/odd rows with css classes
    '''

    html = """
    <table{}{}>
        <colgroup>
            {}
        </colgroup>
        <thead>
            {}
        </thead>
        <tbody>
            {}
        </tbody>
    </table>    
    """.format(
        # add in the id
        f" id = {id}" if id else "",

        # add the class
        f" class = {cssclass}" if cssclass else "",
        
        # colgroups
        ''.join(['<col span="1" class="{}">'.format(colname) for colname in df.columns]),
        
        # column headers
        ''.join(
            [   
                # sticks on the outsides of the row after doing the join
                '<tr><th scope="col">{}</th></tr>'.format(
                    '</th><th scope="col">'.join(df.columns)
                )
            ]
        ),
        # cells of table body
        # Here we use list comprehension to create the rows, then join together by the empty string
        ''.join(
            [
                # sticks on the outsides of the row after doing the join
                # adds even and odd css classes to each row as well
                #'<tr{} id="rownumber-{}" objectid="{}">{}</tr>'.format(
                '<tr{} id="objectid-{}">{}</tr>'.format(
                    ' class="row-even"' if i % 2 == 0 else ' class="row-odd"' if enumeraterows else "",
                    #i,
                    objectid,
                    x
                ) 
                
                for i, (objectid, x) in
                
                # Zips columns together, then joins them with closing table cell tag and opening table cell tag between
                enumerate([
                    (
                        # grab the objectid for the row
                        list(filter(lambda cell: cell is not None, [cell.get('column_value') if cell.get('column_name') == 'objectid' else None for cell in row]))[0],
                        ''.join(
                            list(
                                map(
                                    lambda cell:
                                    # content should be editable for all columns except for the objectid
                                    #'<td class="colname-{}" onkeypress="enterUnfocus(event, this)">{}</td>'.format(
                                    '<td contenteditable="true" class="colname-{}" onkeypress="enterUnfocus(event, this)">{}</td>'.format(
                                        cell.get('column_name'), 
                                        cell.get('column_value') if not pd.isnull(cell.get('column_value')) else ''
                                    ) 
                                    
                                    if 
                                        cell.get('column_name') != 'objectid' 
                                    else
                                        '<td class="colname-{}" onkeypress="enterUnfocus(event, this)">{}</td>' \
                                        .format(
                                            cell.get('column_name'), 
                                            cell.get('column_value') if not pd.isnull(cell.get('column_value')) else ''
                                        )
                                    
                                    , row
                                )
                            )
                        )
                    )

                    for row in 
                    
                    zip(*
                        [
                            df[col].apply(lambda x: {'column_name':col, 'column_value': x}) for col in df.columns
                        ]
                    )

                ])
            ]    
        )
    )
    return html