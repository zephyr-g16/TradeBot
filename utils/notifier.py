import smtplib
from email.message import EmailMessage

class Notifier:
    
    def send_email(self, subject, body, to_email):
        """Send an email notification"""
        msg = EmailMessage()
        msg.set_content(body)
        msg['Subject'] = subject
        msg['From'] = "automatic.cryptrader@gmail.com"
        msg['To'] = to_email

        try:
            with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
                smtp.login("automatic.cryptrader@gmail.com", "sfxq zvxz zwim wbot")
                smtp.send_message(msg)
                print(f"Email notification sent to {to_email}")
        except Exception as e:
            print(f"Failed to send email: {e}")