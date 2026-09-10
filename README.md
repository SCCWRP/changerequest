# Data Change Request Tool
An attempt to build a fully functional change request tool on the flask framework rather than dash

The App will require two folders at the top level directory for the application to read from and write to
Those folders should be named "files" and "export"

The App will also require the database to be an ESRI enterprise geodatabase, as it uses certain functions from ESRI's geodatabases (next_rowid, next_globalid)
SCCWRP's databases are Postgres ESRI geodatabases, so it will interface with no problem for SCCWRP's databases

The app requires a users table (which we call db_editors by default) and a table called change_history. 

  
  
Schema for change_history table (can be named differently but that must be specified in the configuration)  
This table must be registered with the geodatabase
  
| column_name      | is_nullable | dtype  | character_maximum_length | numeric_precision | numeric_scale | datetime_precision |
|------------------|-------------|--------|--------------------------|-------------------|---------------|--------------------|
| objectid         | NO          | int4   | (Null)                   | 32                | 0             | (Null)             |
| original_record  | YES         | json   | (Null)                   | (Null)            | (Null)        | (Null)             |
| modified_record  | YES         | json   | (Null)                   | (Null)            | (Null)        | (Null)             |
| change_id        | YES         | int4   | (Null)                   | 32                | 0             | (Null)             |
| submissionid     | YES         | int4   | (Null)                   | 32                | 0             | (Null)             |
| tablename        | YES         | text   | (Null)                   | (Null)            | (Null)        | (Null)             |
| request_type     | YES         | varchar| 10                       | (Null)            | (Null)        | (Null)             |
| requesting_agency| YES         | varchar| 50                       | (Null)            | (Null)        | (Null)             |
| requesting_person| YES         | varchar| 50                       | (Null)            | (Null)        | (Null)             |
| change_date      | YES         | timestamp | (Null)                | (Null)            | (Null)        | 6                  |
| change_processed | YES         | varchar| 50                       | (Null)            | (Null)        | (Null)             |
| change_comment   | YES         | text   | (Null)                   | (Null)            | (Null)        | (Null)             |
| login_fields     | YES         | json   | (Null)                   | (Null)            | (Null)        | (Null)             |


  
  
Schema for db_editors (which is essentially a users table)
  
| column_name         | is_nullable | dtype    | character_maximum_length | numeric_precision | numeric_scale | datetime_precision |
|---------------------|-------------|----------|--------------------------|-------------------|---------------|--------------------|
| email               | NO          | varchar  | 255                      | (Null)            | (Null)        | (Null)             |
| password            | YES         | varchar  | 255                      | (Null)            | (Null)        | (Null)             |
| organization        | YES         | varchar  | 255                      | (Null)            | (Null)        | (Null)             |
| is_admin            | YES         | varchar  | 3                        | (Null)            | (Null)        | (Null)             |
| is_authorized       | YES         | varchar  | 3                        | (Null)            | (Null)        | (Null)             |
| id                  | NO          | int4     | (Null)                   | 32                | 0             | (Null)             |
| firstname           | YES         | varchar  | 50                       | (Null)            | (Null)        | (Null)             |
| lastname            | YES         | varchar  | 50                       | (Null)            | (Null)        | (Null)             |
| signup_date         | YES         | timestamp| (Null)                   | (Null)            | (Null)        | 6                  |
| email_confirmed     | YES         | varchar  | (Null)                   | (Null)            | (Null)        | (Null)             |
| email_confirmed_date| YES         | timestamp| (Null)                   | (Null)            | (Null)        | 6                  |

Users must be approved by a database administrator directly in the backend - at this time the app does not have the feature of an admin portal or admin login, but that is an enhancement i want to implement when i have time

## Submission Editing And Deletion

Select a datatype, login fields, and completed submission ID. The application checks
authorization and finds the configured data tables containing that submission by
querying the data tables themselves, not `submission_tracking_checksum`. Download
one workbook with a sheet named for each populated table, edit it, and upload once.
The report has a table selector above the Changed, Added, and Deleted record tabs,
with per-table primary keys, counts, errors, and warnings. Core and configured
table-level custom checks run on each supplied table. `check_submission(frames)`
is the dictionary-of-dataframes boundary for a future datatype-level check; no
cross-table custom checks have been added.

Upload matching prefers the generated sheet name, then an exact column-set match.
Ambiguous, unknown, duplicate, and structurally invalid sheets are rejected.
Missing sheets mean **no changes** to those tables and produce a warning. An empty
sheet is rejected: omission must never accidentally request deletion of a table.
Individual row deletions and primary-key replacements within nonempty sheets are
still supported. Browser corrections retain other rows and other tables; new
uploads replace the previous comparison. Finalization is refused after errors,
stale report revisions, or a no-change comparison.

Request Submission Deletion prepares a report of every original record in every
populated table. Finalization requires a nonblank comment and the exact submission
ID typed by the requester. Pending deletion requests show a warning but do not
block new edit requests. Both edit and deletion requests require a comment and
send distinct receipts to the requester and SQL plus the report to maintainers.

The application records intent only. Staff must review and manually run the SQL.
One script contains `BEGIN`/`COMMIT`, per-table sections, and a final update marking
all history for that change ID as processed. It locks affected tables and refuses
stale originals or already deleted submissions. Deletion also locks and checks
configured tables that were empty, preventing concurrent additions from escaping
the archive. Deletes run in reverse configured table order, additions in configured
order, matching the checker's parent-before-child loading convention. A guard
failure aborts the transaction: prepare a new request rather than removing guards.

## Lineage And Request Storage

Every affected record has one `change_history` row, with `tablename`, `request_type`
(`edit` or `delete`), change ID, original submission ID, login fields, requester
agency/email, request date, comment, and `change_processed = 'No'`. Existing history
has nullable table/type fields; it is not retrospectively relabeled.

Original records are streamed from the full typed snapshot using PostgreSQL
`row_to_json(...)::text`. They are never reconstructed from Excel or converted
through a Python float before being archived. Deletion writes that exact full JSON
as `original_record` and the JSON array `[]` as `modified_record`. This retains
system/login fields, object/global IDs, original dates, nulls, and numeric
precision. Edits also archive full original records; additions use `[]` for the
original. New object/global IDs are allocated by the emitted staff SQL, not by
the web application. `login_*`, configured immutable fields, and existing object
IDs remain immutable through comparison. History inserts use bound parameters in
batches of 500 inside one transaction. Finalization locks the request and guards
against duplicate history on retries; email failures retain the request for retry.

The session remains a signed client-side cookie. It stores only request identity,
login selection, submission date, and table names in addition to authentication
fields. Per-table column lists/order are re-derived from `information_schema` and
`column_order` on each request, not stored in the cookie. Comments, report revisions,
candidate frames, and finalization state are on disk under `files/requests/<change_id>/`:

- `submission.xlsx`: the multi-sheet download.
- `comparison.xlsx`: the human-readable report.
- `request.sql`: the single staff execution script.
- `history.jsonl`: exact original/modified JSON records for history insertion.
- `candidates.pkl`: server-written candidate frames for browser corrections; never an uploaded pickle.
- `state.json` and `lock`: request state and a local filesystem lock.

All workers must share this request directory, with write permission for the app
account. Request directories are created with mode 0700 and must not be served as
public static files. Preserve them during retries; do not delete pending request
artifacts. Temporary tables are `tmp.orig_<table>_<change_id>` and
`tmp.mod_<table>_<change_id>` so separate requests do not overwrite each other.
They are created as typed copies without inherited defaults, indexes, or constraints,
and are dropped after finalization or when starting over. The app does not write
production data or submission tracking rows during a request.

Report sheet names come from one shared helper: `T01_Original`, `T01_Modified`,
`T01_Added`, `T01_Deleted`, and so on. The `Index` sheet maps every report sheet to
its real table and record category. Both writer and finalizer use this helper;
the finalizer verifies report and archive counts before writing history. Names
stay below Excel's 31-character limit, including `mobile_monitoringstation`.

## Submission Tracking Additions

The tracking row is retained and `submit` is not changed. Only the generated SQL
sets the nullable deletion metadata. Login/submission selectors exclude rows
whose `deleted_at` is non-null. Checker inserts continue to work unchanged.

| column_name | is_nullable | dtype | meaning |
|-------------|-------------|-------|---------|
| deleted_at | YES | timestamp(6) | Time staff applied the deletion SQL |
| deleted_by | YES | text | Email of the deletion requester |
| deletion_change_id | YES | int4 | Change history ID recording the deletion |

`meta` remains configured. The note in `proj/config/comment about meta.txt` says
metadata came from Survey123 and was removed from configuration, but live config
includes it. Without matching completed (`submit = 'yes'`) tracking rows, the UI
will report no eligible submissions. A tracking row with no populated configured
tables also gives a clear error. No Survey123 lineage or missing tracking rows are
invented by this change.

## Startup DDL Inventory

Importing `proj` connects to the configured database and executes startup DDL.
**Do not import the package or start the app against production to test syntax.**
The complete statement inventory is:

1. `CREATE SCHEMA IF NOT EXISTS tmp;` (existing).
2. `CREATE TABLE IF NOT EXISTS "sde"."<CHANGE_HISTORY_TABLE>" (...)` (existing,
	now also includes nullable `tablename text` and `request_type varchar(10)`;
	the full schema is listed above).
3. The following five idempotent column additions, including for existing deployments:

```sql
ALTER TABLE "sde"."<CHANGE_HISTORY_TABLE>" ADD COLUMN IF NOT EXISTS "tablename" text;
ALTER TABLE "sde"."<CHANGE_HISTORY_TABLE>" ADD COLUMN IF NOT EXISTS "request_type" varchar(10);
ALTER TABLE "sde"."submission_tracking_table" ADD COLUMN IF NOT EXISTS "deleted_at" timestamp(6);
ALTER TABLE "sde"."submission_tracking_table" ADD COLUMN IF NOT EXISTS "deleted_by" text;
ALTER TABLE "sde"."submission_tracking_table" ADD COLUMN IF NOT EXISTS "deletion_change_id" int4;
```

4. If the configured users table does not exist, the existing bootstrap executes
	`CREATE TABLE "sde"."db_editors" (...)` with the schema listed above, then
	`ALTER TABLE "sde"."db_editors" ADD CONSTRAINT "db_editors_email_unique" UNIQUE ("email");`
	and `ALTER TABLE "sde"."db_editors" ADD CONSTRAINT "db_editors_pkey" PRIMARY KEY ("id");`.

No migrations were executed while implementing this feature. Deployment will need
the existing startup DDL privileges for these nullable additions.

## Offline Verification

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -v
node --check proj/static/login_form.js
node --input-type=module --check < proj/static/edit_submission.js
node --input-type=module --check < proj/static/save.js
node --check proj/static/format_table.js
```

Tests load individual helper files or extract function definitions with `ast`,
never importing `proj`. Database operations, mail, and Excel writers are replaced
by test doubles where needed. Tests cover workbook mapping, immutable lineage,
primary-key replacements, browser correction isolation, exact deletion JSON,
single-script generation and locking, bounded transactional history inserts, and
mandatory deletion confirmation. They require Python 3, pandas, psycopg2, and Flask.
Real Excel round trips, PostgreSQL execution, mail delivery, and a running-browser
workflow must still be verified in an isolated staging environment, not against
the production database. The existing Docker dependencies include the required
SQLAlchemy, xlsxwriter, and openpyxl runtime libraries.
