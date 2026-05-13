import os
import smtplib
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.utils import COMMASPACE, formatdate
from email import encoders

# Function to be used later in sending email
def send_mail(send_from, send_to, subject, text = '', html = None, files=None, server='localhost'):
    msg = MIMEMultipart()
    
    msg['From'] = send_from
    msg['To'] = COMMASPACE.join(send_to)
    msg['Date'] = formatdate(localtime=True)
    msg['Subject'] = subject
    
    if html:
        msg_html = MIMEText(html, 'html')
        msg.attach(msg_html)
    else:
        msg_content = MIMEText(text, 'plain')
        msg.attach(msg_content)

    if files:
        for f in files:
            if os.path.exists(f):
                ext = f.rsplit('.', 1)[-1] if '.' in f else ''
                if ext in ('txt', 'sql', 'csv', ''):
                    p = MIMEText(open(f, 'r').read())
                else:
                    attachment = open(f, 'rb')
                    p = MIMEBase('application','octet-stream')
                    p.set_payload((attachment).read())
                    encoders.encode_base64(p)
                    
                p.add_header('Content-Disposition',f"attachment; filename={f.split('/')[-1]}")
                msg.attach(p)
            else:
                print(f"filename {f} not found")

    smtp = smtplib.SMTP(server)
    smtp.sendmail(send_from, send_to, msg.as_string())
    smtp.close()

