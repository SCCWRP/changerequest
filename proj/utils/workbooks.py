REPORT_INDEX = 'Index'
REPORT_KINDS = ('Original', 'Modified', 'Added', 'Deleted')


def report_sheets(tables):
    return {
        table: {kind: f'T{position:02d}_{kind}' for kind in REPORT_KINDS}
        for position, table in enumerate(tables, start=1)
    }


def report_index(tables):
    return [
        {'tablename': table, 'kind': kind, 'sheet_name': sheet}
        for table, sheets in report_sheets(tables).items()
        for kind, sheet in sheets.items()
    ]


def resolve_sheets(sheets, columns):
    resolved = {}
    for sheet, frame in sheets.items():
        if sheet in columns:
            candidates = [sheet]
        else:
            candidates = [table for table, names in columns.items() if set(frame.columns) == set(names)]
        if len(candidates) != 1:
            raise ValueError(f'Sheet "{sheet}" cannot be uniquely matched to a submission table. Restore its original sheet name and columns.')
        table = candidates[0]
        if table in resolved:
            raise ValueError(f'More than one sheet matches {table}.')
        if set(frame.columns) != set(columns[table]):
            missing = sorted(set(columns[table]) - set(frame.columns))
            extra = sorted(set(frame.columns) - set(columns[table]))
            raise ValueError(f'{sheet}: missing columns {missing}; unexpected columns {extra}.')
        if frame.empty:
            raise ValueError(f'{sheet} is empty. Restore its records or omit the sheet to leave it unchanged. Use Request Submission Deletion to remove the whole submission.')
        resolved[table] = frame
    if not resolved:
        raise ValueError('The workbook contains no submission data sheets.')
    return resolved, [table for table in columns if table not in resolved]