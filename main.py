# main.py
from fastapi import FastAPI, Request, Query, Depends
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles

from db import get_db
from services.company_service import get_company_detail, resolve_stock_code

app = FastAPI(title="EWS Dashboard (SSR, no-JS)")
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

@app.get("/html", response_class=HTMLResponse)
def html(request: Request, db=Depends(get_db)):
    # 기본 기업으로 렌더
    try:
        code = resolve_stock_code("005930", db)
        data = get_company_detail(code, db)
    except Exception:
        data = {
            "company_info": {"company_name":"N/A","ticker":"005930","market_type":"","founded_year":0},
            "chart_data": {"bankruptcy_probabilities": {}, "title": ""},
            "news_data": {},
            "insolvency_data": {"percent":"-","status":"정보없음"},
            "risk_factor": {},
            "sector_risk": {"title":"업종별 평균 부실징후 확률","series":[]},
            "benchmark": {"categories": [], "tolerance": 0.05},
        }
    return templates.TemplateResponse("index.html", {"request": request, **data})



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
        }
    ctx = {"request": request, **data}
    return templates.TemplateResponse("index.html", ctx)

@app.get("/api/dashboard", response_class=JSONResponse)
def api_dashboard(corp_id: str = Query("005930"), db=Depends(get_db)):
    code = resolve_stock_code(corp_id, db)
    return get_company_detail(code, db)

# ============================================================================

# # main.py
# from fastapi import FastAPI, Request, Query, Depends
# from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
# from fastapi.staticfiles import StaticFiles
# from fastapi.templating import Jinja2Templates

# # ✅ DB 세션 의존성
# from db import get_db

# # ✅ 서비스: get_company_detail 만 쓰면 나머지(회사정보/차트/뉴스/위험요인/업종차트)는 내부에서 조합
# from services.company_service import get_company_detail

# app = FastAPI(title="EWS Dashboard (SSR, no-JS)")

# # 정적 파일
# app.mount("/static", StaticFiles(directory="static"), name="static")

# # 템플릿
# templates = Jinja2Templates(directory="templates")


# # 홈 → 기본 기업(삼성전자)로 이동
# @app.get("/", response_class=HTMLResponse)
# def home() -> RedirectResponse:
#     return RedirectResponse(url="/company/005930")


# # 검색 폼이 ?corp_id= 로 전송할 때 받는 엔드포인트 (리다이렉트)
# @app.get("/company", response_class=HTMLResponse)
# def company_redirect(corp_id: str = Query(..., description="종목코드 또는 식별자")) -> RedirectResponse:
#     return RedirectResponse(url=f"/company/{corp_id}")


# # 기업 대시보드: 새로고침 시마다 서비스에서 최신 데이터 조회 후 SSR
# @app.get("/company/{corp_id}", response_class=HTMLResponse)
# def company_dashboard(
#     request: Request,
#     corp_id: str,
#     db=Depends(get_db),                      # ✅ DB 세션 주입
# ):
#     """
#     - corp_id(예: 005930)를 받아 서비스 레이어에서 dict(JSON) 수령
#     - 템플릿으로 값 전달 → JS 없이 서버 렌더
#     """
#     data = get_company_detail(corp_id, db)   # ✅ DB 세션 전달

#     ctx = {
#         "request": request,
#         "company_info": data["company_info"],
#         "chart_data": data["chart_data"],
#         "news_data": data["news_data"],
#         "insolvency_data": data["insolvency_data"],
#         "risk_factor": data["risk_factor"],
#         "benchmark": data.get("benchmark", {"categories": [], "tolerance": 0.05}),
#         "sector_risk": data["sector_risk"],
#     }
#     return templates.TemplateResponse("index.html", ctx)


# # (선택) JSON으로 확인용 API
# @app.get("/api/dashboard", response_class=JSONResponse)
# def api_dashboard(
#     corp_id: str = Query("005930"),
#     db=Depends(get_db),                      # ✅ 동일하게 DB 세션 주입
# ):
#     data = get_company_detail(corp_id, db)
#     return JSONResponse(content=data)
