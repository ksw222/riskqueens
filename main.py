# main.py
from fastapi import FastAPI, Request, Query, Depends
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
from dotenv import load_dotenv, find_dotenv
import os

from db import get_db
from services.company_service import get_company_detail, resolve_stock_code, get_latest_alert_companies
from services.ai_report import generate_report
from services.mailer import send_alert_email

load_dotenv(find_dotenv(), override=True)

app = FastAPI(title="EWS Dashboard (SSR, no-JS)")
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# -------- 최소 공용 유틸 --------
def _to_score_0_100(v) -> float:
    if v is None:
        return 0.0
    if isinstance(v, str):
        s = v.strip()
        if s.endswith("%"):
            s = s[:-1]
        try:
            v = float(s)
        except Exception:
            return 0.0
    try:
        x = float(v)
    except Exception:
        return 0.0
    if 0.0 <= x <= 1.0:
        x *= 100.0
    return max(0.0, min(100.0, x))

def _ctx(request: Request, data: dict) -> dict:
    raw = (
        data.get("insolvency_data", {}).get("percent")
        or data.get("default_prob")
        or data.get("default_prob_score")
        or 0
    )
    return {"request": request, **data, "risk_score": _to_score_0_100(raw)}
# --------------------------------

def _env_missing(keys: list[str]) -> list[str]:
    return [k for k in keys if not os.getenv(k, "").strip()]

@app.post("/alerts/send", response_class=HTMLResponse)
def send_alerts(request: Request, db: Session = Depends(get_db)):
    try:
        missing = _env_missing(["SMTP_HOST","SMTP_PORT","SMTP_USER","SMTP_PASS","MAIL_TO"])
        if missing:
            ref = request.headers.get("referer", "/")
            return RedirectResponse(url=f"{ref}?error=ENV%20missing:%20{','.join(missing)}", status_code=303)

        rows = get_latest_alert_companies(db=db)
        sent = send_alert_email(rows)

        ref = request.headers.get("referer", "/")
        return RedirectResponse(url=f"{ref}?sent={sent}&found={len(rows)}", status_code=303)
    except Exception as e:
        ref = request.headers.get("referer", "/")
        return RedirectResponse(url=f"{ref}?error={str(e)}", status_code=303)

@app.get("/", response_class=HTMLResponse)
def home() -> RedirectResponse:
    return RedirectResponse(url="/company/003230")

@app.get("/company", response_class=HTMLResponse)
def company_redirect(corp_id: str = Query(..., description="종목코드 또는 회사명"), db=Depends(get_db)):
    try:
        code = resolve_stock_code(corp_id, db)
    except Exception:
        code = "003230"
    return RedirectResponse(url=f"/company/{code}")

@app.get("/company/{corp_id}", response_class=HTMLResponse)
def company_dashboard(request: Request, corp_id: str, db=Depends(get_db)):
    try:
        code = resolve_stock_code(corp_id, db)
        data = get_company_detail(code, db)
    except Exception:
        data = {
            "company_info": {"company_name":"N/A","ticker":corp_id,"market_type":"","founded_year":0},
            "chart_data": {"bankruptcy_probabilities": {}, "title": ""},
            "news_data": {},
            "insolvency_data": {"percent":"-","status":"정보없음"},
            "risk_factor": {},
            "sector_risk": {"title":"업종별 평균 부실징후 확률","series":[]},
            "benchmark": {"categories": [], "tolerance": 0.05},
            "label": 0,
            "beneish_mscore": None,
            "beneish_year": None,
            "score_fill": 0,
            "threshold": -2.22,
        }
    return templates.TemplateResponse("index.html", _ctx(request, data))

@app.get("/api/dashboard", response_class=JSONResponse)
def api_dashboard(corp_id: str = Query("005930"), db=Depends(get_db)):
    code = resolve_stock_code(corp_id, db)
    return get_company_detail(code, db)

@app.post("/company/{corp_id}/ai-report", response_class=HTMLResponse)
def create_ai_report(request: Request, corp_id: str, db=Depends(get_db)):
    code = resolve_stock_code(corp_id, db)
    data = get_company_detail(code, db)

    report_html = generate_report(data)
    ctx = _ctx(request, data)
    ctx["ai_report_md"] = report_html  # 템플릿에서 |safe 사용
    return templates.TemplateResponse("index.html", ctx)
