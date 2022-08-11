import os
import smtplib
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.utils import COMMASPACE, formatdate
from email import encoders

# Function to be used later in sending email
def send_mail(send_from, send_to, subject, text, files=None, server='localhost'):
    msg = MIMEMultipart()
    
    msg['From'] = send_from
    msg['To'] = COMMASPACE.join(send_to)
    msg['Date'] = formatdate(localtime=True)
    msg['Subject'] = subject
    
    msg_content = MIMEText(text)
    msg.attach(msg_content)
    
    if files:
        for f in files:
            assert os.path.exists(f), f"filename {f} not found"
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

    smtp = smtplib.SMTP(server)
    smtp.sendmail(send_from, send_to, msg.as_string())
    smtp.close()