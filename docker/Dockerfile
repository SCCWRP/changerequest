FROM python:latest
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get upgrade -y
RUN apt-get install -y apt-utils
RUN apt-get install -y python3-pip python3-dev build-essential libssl-dev libffi-dev
RUN apt-get install -y libpcre3 libpcre3-dev
RUN pip install --upgrade pip
RUN pip3 install wheel
RUN pip3 install markupsafe==2.0.1
RUN pip3 install uwsgi flask ipython
RUN pip3 install xlrd flask_session
RUN pip3 install flask_cors
#RUN pip3 install sqlalchemy
#https://github.com/dagster-io/dagster/discussions/11881 sqlalchemy >= 2.0.0 has a bug where eng.execute generates an error
RUN pip3 install sqlalchemy==1.4.47
RUN apt-get install -y libpq-dev && pip3 install psycopg2
RUN pip3 install pandas xlsxwriter numpy
RUN pip3 install folium
RUN pip3 install pandas_access
RUN pip3 install flask_mail
RUN pip3 install geoalchemy2
RUN pip3 install odo
RUN pip3 install cerberus

RUN pip3 install Werkzeug
RUN pip3 install Flask-Bcrypt
RUN pip3 install Flask-SQLAlchemy
RUN pip3 install Flask-Login
RUN pip3 install Flask-WTF
RUN pip3 install email_validator
RUN pip3 install itsdangerous
RUN pip3 install openpyxl

RUN mkdir -p /var/www/changerequest/
WORKDIR /var/www/changerequest/

# docker image build -t sccwrp/flask:changerequest .

# Example of what should go in deploy.sh
# docker container rm -f __CONTAINERNAME__ ;
# docker container run -it -d \
#     --name __CONTAINERNAME__ \
#     -v /var/www/__PROJECTNAME__/changerequest:/var/www/changerequest \
#     -v /tmp:/tmp \
#     -w /var/www/changerequest \
#     -v /etc/timezone:/etc/timezone:ro \
#     -v /etc/localtime:/etc/localtime:ro \
#     -e DB_USERNAME='__DB_USERNAME__' \
#     -e DB_PASSWORD='__DB_PASSWORD__' \
#     -e DB_HOST='__DB_HOST__' \
#     -e DB_NAME='__DB_NAME__' \
#     -e DB_CONNECTION_STRING='__DB_PLATFORM__://__DB_USERNAME__:__DB_PASSWORD__@__DB_HOST__/__DB_NAME__' \
#     -e CHANGE_HISTORY_TABLE='change_history' \
#     -e FLASK_APP_SECRET_KEY='__RANDOM_STRING__' \
#     sccwrp/flask:changerequest \
#     uwsgi -s /tmp/__CONTAINERNAME__.sock --uid www-data --gid www-data --manage-script-name --mount /changerequest=run:app --chmod-socket=666;