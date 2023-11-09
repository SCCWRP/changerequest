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
| requesting_agency| YES         | varchar| 50                       | (Null)            | (Null)        | (Null)             |
| requesting_person| YES         | varchar| 50                       | (Null)            | (Null)        | (Null)             |
| change_date      | YES         | timestamp | (Null)                | (Null)            | (Null)        | 6                  |
| change_processed | YES         | varchar| 50                       | (Null)            | (Null)        | (Null)             |
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
