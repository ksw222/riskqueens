import logging
import os
import time
from collections import defaultdict, deque
from pathlib import Path

from dotenv import find_dotenv, load_dotenv
from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from db import get_db
from services.ai_report import generate_report
from services.company_service import get_company_detail, get_latest_alert_companies, resolve_stock_code
from services.mailer import send_alert_email

load_dotenv(find_dotenv(), override=False)
logger = logging.getLogger(__name__)
BASE_DIR = Path(__file__).resolve().parent

app = FastAPI(title="EWS Dashboard (SSR, no-JS)")
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
templates = Jinja2Templates(directory=BASE_DIR / "templates")

_requests: dict[str, deque[float]] = defaultdict(deque)


def _to_percent(value: object) -> float:
    """Convert canonical DB probability (0–1) to a display percentage (0–100)."""
    try:
        probability = float(value or 0)
    except (TypeError, ValueError):
        return 0.0
    return round(max(0.0, min(1.0, probability)) * 100, 1)


def _ctx(request: Request, data: dict) -> dict:
    data = dict(data)
    data["risk_score"] = _to_percent(data.get("default_prob"))
    return {"request": request, **data}


def _fallback_data(corp_id: str) -> dict:
    return {
        "company_info": {"company_name": "데이터를 불러올 수 없습니다", "ticker": corp_id,
                         "market_type": "", "founded_year": 0, "median_default_prob_pct": 0},
        "chart_data": {"bankruptcy_probabilities": {}, "title": "부실확률 추이"},
        "news_data": {}, "default_prob": 0, "insolvency_data": {"percent": "-", "status": "정보 없음"},
        "risk_factor": {}, "sector_risk": {"title": "업종별 부실확률 중앙값", "series": [], "all_series": []},
        "benchmark": {"categories": [], "tolerance": 0.05}, "beneish_mscore": None,
        "beneish_year": None, "score_fill": 0, "threshold": -2.22,
    }


def _protect_post(request: Request) -> None:
    """Allow an administrator token, otherwise apply a small per-IP abuse limit."""
    expected = os.getenv("ADMIN_TOKEN", "").strip()
    supplied = request.headers.get("X-Admin-Token", "")
    if expected and supplied != expected:
        raise HTTPException(status_code=403, detail="Administrator authorization is required.")
    key = request.client.host if request.client else "unknown"
    now = time.monotonic()
    window = int(os.getenv("RATE_LIMIT_WINDOW_SECONDS", "60"))
    limit = int(os.getenv("RATE_LIMIT_MAX_REQUESTS", "5"))
    calls = _requests[key]
    while calls and calls[0] <= now - window:
        calls.popleft()
    if len(calls) >= limit:
        raise HTTPException(status_code=429, detail="Too many requests. Please try again shortly.")
    calls.append(now)


@app.post("/alerts/send", response_class=HTMLResponse)
def send_alerts(request: Request, db: Session = Depends(get_db)):
    _protect_post(request)
    ref = request.headers.get("referer", "/")
    try:
        required = ["SMTP_HOST", "SMTP_PORT", "SMTP_USER", "SMTP_PASS", "MAIL_TO"]
        if any(not os.getenv(key, "").strip() for key in required):
            return RedirectResponse(url=f"{ref}?error=mail_not_configured", status_code=303)
        rows = get_latest_alert_companies(db=db)
        sent = send_alert_email(rows)
        return RedirectResponse(url=f"{ref}?sent={sent}&found={len(rows)}", status_code=303)
    except Exception:
        logger.exception("Unable to send alert email")
        return RedirectResponse(url=f"{ref}?error=alert_send_failed", status_code=303)


@app.get("/", response_class=HTMLResponse)
def home() -> RedirectResponse:
    return RedirectResponse(url="/company/003230")


@app.get("/company", response_class=HTMLResponse)
def company_redirect(corp_id: str = Query(...), db: Session = Depends(get_db)):
    try:
        code = resolve_stock_code(corp_id, db)
    except Exception:
        logger.exception("Company lookup failed")
        code = "003230"
    return RedirectResponse(url=f"/company/{code}")


@app.get("/company/{corp_id}", response_class=HTMLResponse)
def company_dashboard(request: Request, corp_id: str, db: Session = Depends(get_db)):
    try:
        code = resolve_stock_code(corp_id, db)
        data = get_company_detail(code, db)
    except Exception:
        logger.exception("Dashboard data retrieval failed for company %s", corp_id)
        data = _fallback_data(corp_id)
    return templates.TemplateResponse(request=request, name="index.html", context=_ctx(request, data))


@app.get("/api/dashboard", response_class=JSONResponse)
def api_dashboard(corp_id: str = Query("005930"), db: Session = Depends(get_db)):
    try:
        return get_company_detail(resolve_stock_code(corp_id, db), db)
    except Exception:
        logger.exception("Dashboard API retrieval failed for company %s", corp_id)
        return JSONResponse(_fallback_data(corp_id), status_code=503)


@app.post("/company/{corp_id}/ai-report", response_class=HTMLResponse)
def create_ai_report(request: Request, corp_id: str, db: Session = Depends(get_db)):
    _protect_post(request)
    try:
        data = get_company_detail(resolve_stock_code(corp_id, db), db)
    except Exception:
        logger.exception("AI report source retrieval failed for company %s", corp_id)
        data = _fallback_data(corp_id)
    ctx = _ctx(request, data)
    ctx["ai_report_md"] = generate_report(data)
    return templates.TemplateResponse(request=request, name="index.html", context=ctx)
