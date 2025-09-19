# main.py
from fastapi import FastAPI, Request, Query, Depends
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles

from db import get_db
from services.company_service import get_company_detail, resolve_stock_code

from fastapi import Form
from services.ai_report import generate_report

app = FastAPI(title="EWS Dashboard (SSR, no-JS)")
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")


@app.get("/", response_class=HTMLResponse)
def home() -> RedirectResponse:
    return RedirectResponse(url="/company/005930")
    

@app.get("/company", response_class=HTMLResponse)
def company_redirect(corp_id: str = Query(..., description="종목코드 또는 회사명"), db=Depends(get_db)):
    try:
        code = resolve_stock_code(corp_id, db)
    except Exception:
        # 못 찾으면 기본으로
        code = "005930"
    return RedirectResponse(url=f"/company/{code}")

@app.get("/company/{corp_id}", response_class=HTMLResponse)
def company_dashboard(request: Request, corp_id: str, db=Depends(get_db)):
    try:
        code = resolve_stock_code(corp_id, db)
        data = get_company_detail(code, db)
    except Exception:
        # 템플릿이 깨지지 않도록 최소 구조로 렌더
        data = {
            "company_info": {"company_name":"N/A","ticker":corp_id,"market_type":"","founded_year":0},
            "chart_data": {"bankruptcy_probabilities": {}, "title": ""},
            "news_data": {},
            "insolvency_data": {"percent":"-","status":"정보없음"},
            "risk_factor": {},
            "sector_risk": {"title":"업종별 평균 부실징후 확률","series":[]},
            "benchmark": {"categories": [], "tolerance": 0.05},
            "label": 0,  # ✅ 기본값
            
            # ✅ [추가: Beneish 기본값]
            "beneish_mscore": None,
            "beneish_year": None,
            "score_fill": 0,
            "threshold": -2.22,
        }
    ctx = {"request": request, **data}

    # ---- [추가] 게이지 점수 계산 (0~100) ----
    def to_score_0_100(v) -> float:
        """
        v가 37, '37', '37%', 0.37 어느 형태로 와도 0~100 스코어로 변환.
        범위를 벗어나면 0~100으로 클램프.
        """
        if v is None:
            return 0.0
        if isinstance(v, str):
            v = v.strip()
            v = v[:-1] if v.endswith("%") else v
        try:
            x = float(v)
        except Exception:
            return 0.0
        # 0~1 확률로 들어오면 %로 변환
        if 0.0 <= x <= 1.0:
            x *= 100.0
        # 클램프
        return max(0.0, min(100.0, x))

    # insolvency_data.percent, or 다른 필드에서 가져오기
    raw_percent = (
        data.get("insolvency_data", {}).get("percent")
        or data.get("default_prob")  # 혹시 이런 키라면
        or data.get("default_prob_score")
        or 0
    )
    risk_score = to_score_0_100(raw_percent)

    ctx = {
        "request": request,
        **data,
        "risk_score": risk_score,   # ← 게이지에 전달
    }
    return templates.TemplateResponse("index.html", ctx)

@app.get("/api/dashboard", response_class=JSONResponse)
def api_dashboard(corp_id: str = Query("005930"), db=Depends(get_db)):
    code = resolve_stock_code(corp_id, db)
    return get_company_detail(code, db)


@app.post("/company/{corp_id}/ai-report", response_class=HTMLResponse)
def create_ai_report(request: Request, corp_id: str, db=Depends(get_db)):
    # 기존 데이터 조립 재사용
    code = resolve_stock_code(corp_id, db)
    data = get_company_detail(code, db)

    # (필요 시 옵션 받기)
    # tone = Form(None), length = Form(None) 등

    md = generate_report(data)   # Markdown 문자열
    # 결과를 같은 페이지에 렌더(간단): <pre> 또는 <div>
    ctx = {"request": request, **data, "ai_report_md": md}
    return templates.TemplateResponse("index.html", ctx)

