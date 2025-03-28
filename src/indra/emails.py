import logging
import os
import smtplib
import ssl
from datetime import datetime
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from enum import Enum

from dotenv import load_dotenv

logger = logging.getLogger(__name__)

class Status(Enum):
    SUCCESS = 1
    CRITICAL = 2
    ERROR = 3

class ReportEntry:

    def __init__(self, component_name, status, comments):
        self.component_name = component_name
        self.status = status
        self.comments = comments

    def _to_list(self):
        return [self.component_name, self.status, self.comments]

class Report:
    reports: list[ReportEntry]

    def __init__(self, job_name, email_recipients, run_date=None):

        self.job_name = job_name
        if run_date is None:
            self.run_date = datetime.now().strftime("%Y%m%d")
        else:
            self.run_date = run_date
        self.email_recipients = email_recipients


        self.reports = []

        load_dotenv()

        self.SMTP_SERVER = os.getenv('SMTP_SERVER')
        self.PORT = os.getenv('PORT')
        self.EMAIL = os.getenv('EMAIL')
        self.PASSWORD = os.getenv('PASSWORD')

        self.message = MIMEMultipart()

    def add_a_status_report(self, component_name: str, status: Status, comments: str):
        self.reports.append(ReportEntry(component_name, status, comments))

    def collate_report_entries(self):

        subject = self.job_name + ' || ' + self.run_date

        html = """
                <html><body><table style="border: 1px solid black;"><tr style="border: 1px solid black;">
                """

        for header in ["Component Name", "Status", "Comments"]:
            string = f"<th style='border: 1px solid black; font-size: 20px; padding: 10px'>{header}</th>"
            html += string

        html += "</tr>"

        # data = [report._to_list() for report in self.reports]

        for report_entry in self.reports:
            if report_entry.status == Status.SUCCESS:
                color = 'green'
            elif report_entry.status == Status.CRITICAL:
                color = 'red'
            elif report_entry.status == Status.ERROR:
                color = 'orange'

            html += f"<tr style='border: 1px solid black; font-size: 18px; color: {color}'>"
            html += f"<td style='border: 1px solid black; padding: 10px'>{report_entry.component_name}</td>"
            html += f"<td style='border: 1px solid black; padding: 10px'>{report_entry.status}</td>"
            html += f"<td style='border: 1px solid black; padding: 10px'>{report_entry.comments}</td>"
            html += "</tr>"

        html += "</table></body></html>"

        if any([report_entry.status == Status.CRITICAL for report_entry in self.reports]):
            subject = 'CRITICAL ERROR!! - ' + subject

        if any([report_entry.status == Status.ERROR for report_entry in self.reports]):
            subject = 'Errors raised - ' + subject


        self.message["From"] = 'Artpark Automated Pipelines'
        self.message["To"] = self.email_recipients
        self.message["Subject"] = subject
        self.message.attach(MIMEText(html,'html'))

        return self.message.as_string()

    def add_attachment(self, filepath):
        try:
            with open(filepath, "rb") as attachment:
                part = MIMEBase("application", "octet-stream")
                part.set_payload(attachment.read())

            encoders.encode_base64(part)

            attachment_name = filepath.split('/')[-1]
            part.add_header(
                "Content-Disposition",
                f"attachment; filename= {attachment_name}",
            )

            self.message.attach(part)
            print("added attachment")
        except Exception as e:
            logger.error(f"Failed to attach file {filepath}: {e}")
            raise

    def send_email(self):

        text = self.collate_report_entries()

        with smtplib.SMTP(self.SMTP_SERVER, self.PORT) as server:
            logger.info("Connecting to email server")
            server.starttls(context=ssl.create_default_context())
            server.login(self.EMAIL, self.PASSWORD)
            server.sendmail(self.EMAIL, self.email_recipients, text)
            logger.info("Email sent successfully")

    def any_criticals(self):
        return any([report.status == Status.CRITICAL for report in self.reports])
