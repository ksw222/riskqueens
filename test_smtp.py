# test_smtp.py
import os, ssl, smtplib
from email.mime.text import MIMEText
from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv(), override=True)

host = os.getenv("SMTP_HOST")
port = int(os.getenv("SMTP_PORT", "465"))
user = os.getenv("SMTP_USER")
pw   = os.getenv("SMTP_PASS")
mail_from = os.getenv("MAIL_FROM", user)
mail_to   = [addr.strip() for addr in os.getenv("MAIL_TO","").split(",") if addr.strip()]

assert all([host, port, user, pw, mail_to]), "필수 SMTP 환경변수가 비었습니다."

msg = MIMEText("SMTP 단독 테스트 본문입니다.")
msg["Subject"] = "RiskQueens SMTP Test"
msg["From"] = mail_from
msg["To"] = ", ".join(mail_to)

with smtplib.SMTP_SSL(host, port, context=ssl.create_default_context()) as s:
    s.login(user, pw)
    s.sendmail(user, mail_to, msg.as_string())

print("OK: SMTP 전송 성공")
