# services/mailer.py
import os, smtplib, ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

def _env_bool(key: str, default: bool=False) -> bool:
    v = os.getenv(key, str(default)).lower()
    return v in ("1", "true", "yes", "y")

# ---------- 포매터들 ----------
from decimal import Decimal, ROUND_DOWN

def _fmt_prob_pct(v):
    """
    부실확률 표시용:
    - 0~1     : ×100
    - 0~100   : 그대로
    - 0~10000 : ÷100  (퍼센트가 한 번 더 곱해진 경우 교정)
    - 그 외 값: 합리적 범위 내로 보정 후, 소수 둘째자리 '버림'
    """
    if v is None or v == "":
        return ""
    try:
        x = float(v)
    except:
        return ""

    # 스케일 정규화
    if 0.0 <= x <= 1.0:
        x *= 100.0
    elif 100.0 < x <= 10000.0:
        x /= 100.0  # 잘못 곱해진 퍼센트 교정

    # 최종 0~100으로만 제한
    x = max(0.0, min(100.0, x))

    # 반올림 없이 소수 둘째자리 '버림'
    d = Decimal(str(x)).quantize(Decimal("0.00"), rounding=ROUND_DOWN)
    return f"{d}%"



def _fmt_ratio_pct_auto(v, digits=2):
    """
    일반 비율(자본잠식률/부채비율 등): 0~1이면 ×100, 아니면 그대로.
    음수도 허용. 'xx.xx%' 형식.
    """
    if v is None or v == "":
        return ""
    try:
        x = float(v)
    except:
        return ""
    if -1.5 <= x <= 1.5:  # 보수적: 0~1(혹은 -1~1) 범위면 퍼센트로 해석
        x *= 100.0
    fmt = f"{{:,.{digits}f}}%"
    return fmt.format(x)

def _fmt_num(v, digits=2):
    if v is None or v == "":
        return ""
    try:
        x = float(v)
    except:
        return ""
    fmt = f"{{:,.{digits}f}}"
    return fmt.format(x)

def send_alert_email(alert_rows) -> int:
    """
    alert_rows: get_latest_alert_companies() 반환 리스트(dict)
      기대 키:
        - stock_code, company_name, year
        - default_prob_pct 또는 default_prob (둘 중 하나만 있어도 작동)
        - icr, capital_impairment_ratio, debt_ratio
    """
    host = os.getenv("SMTP_HOST")
    port = int(os.getenv("SMTP_PORT", "465"))
    user = os.getenv("SMTP_USER")
    pw   = os.getenv("SMTP_PASS")
    use_ssl = _env_bool("SMTP_USE_SSL", True)

    mail_from = os.getenv("MAIL_FROM", "no-reply@riskqueens.com")
    mail_to = [x.strip() for x in os.getenv("MAIL_TO", "").split(",") if x.strip()]

    if not host or not port or not user or not pw or not mail_to:
        raise RuntimeError("SMTP/.env 설정이 부족합니다 (HOST/PORT/USER/PASS/MAIL_TO).")

    subject = "RiskQueens: 최신 연도 기준 위험 기업 알림"

    # 표 생성
    rows_html = []
    for r in alert_rows:
        # 부실확률: default_prob_pct 우선, 없으면 default_prob 사용
        prob_raw = r.get("default_prob_pct")
        if prob_raw is None:
            prob_raw = r.get("default_prob")
        prob_cell = _fmt_prob_pct(prob_raw)

        icr_cell  = _fmt_num(r.get("icr"), 2)
        capimp    = _fmt_ratio_pct_auto(r.get("capital_impairment_ratio"), 2)
        debt      = _fmt_ratio_pct_auto(r.get("debt_ratio"), 2)

        rows_html.append(f"""
        <tr>
          <td>{r.get('stock_code','')}</td>
          <td>{r.get('company_name','')}</td>
          <td>{r.get('year','')}</td>
          <td style="text-align:right">{prob_cell}</td>
          <td style="text-align:right">{icr_cell}</td>
          <td style="text-align:right">{capimp}</td>
          <td style="text-align:right">{debt}</td>
        </tr>
        """)

    html = f"""
    <html><body>
      <h2>최신 연도 기준 위험(라벨=1 또는 임계치 초과) 기업 목록</h2>
      <p>총 {len(alert_rows)}개 기업이 포착되었습니다.</p>
      <table border="1" cellpadding="6" cellspacing="0" style="border-collapse:collapse; font-family:system-ui,Roboto,'Malgun Gothic',sans-serif; font-size:13px;">
        <thead style="background:#f3e8ff">
          <tr>
            <th>종목코드</th><th>회사명</th><th>연도</th>
            <th>부실확률(%)</th><th>이자보상배율</th><th>자본잠식률</th><th>부채비율</th>
          </tr>
        </thead>
        <tbody>
          {''.join(rows_html)}
        </tbody>
      </table>
      <p style="color:#888">이 메일은 RQ Dashboard에서 자동 발송되었습니다.</p>
    </body></html>
    """

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = mail_from
    msg["To"] = ", ".join(mail_to)
    msg.attach(MIMEText(html, "html", _charset="utf-8"))

    if use_ssl:
        context = ssl.create_default_context()
        with smtplib.SMTP_SSL(host, port, context=context) as s:
            s.login(user, pw)
            s.sendmail(mail_from, mail_to, msg.as_string())
    else:
        with smtplib.SMTP(host, port) as s:
            s.starttls(context=ssl.create_default_context())
            s.login(user, pw)
            s.sendmail(mail_from, mail_to, msg.as_string())

    return len(mail_to)
