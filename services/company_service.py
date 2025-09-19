# services/company_service.py
from typing import Dict, List
from sqlalchemy.orm import Session
from sqlalchemy import func
from sqlalchemy import or_
from db_models.dashboard_flat import DashboardFlat

# ✅ [추가] Beneish 임계값
THRESHOLD = -2.22

def _status_from_prob(prob: float) -> str:
    # 원하는 임계값으로 조정하세요
    if prob is None:
        return "정보없음"
    if prob >= 0.6: return "위험"
    if prob >= 0.4: return "경고"
    return "양호"

def get_company_detail(stock_code: str, db: Session) -> Dict:
    # 전체 연도 로우 (차트/뉴스용)
    rows: List[DashboardFlat] = (
        db.query(DashboardFlat)
          .filter(DashboardFlat.stock_code == stock_code)
          .order_by(DashboardFlat.year.asc())
          .all()
    )
    if not rows:
        raise ValueError(f"No data for {stock_code}")

    latest = rows[-1]

    # ✅ [추가] Beneish M-Score 단일값 + 도넛 채우기 계산(의심=100, 정상=0)
    score = float(latest.beneish_mscore) if latest.beneish_mscore is not None else None
    score_fill = 100 if (score is not None and score >= THRESHOLD) else 0

    # 1) 기업 기본 정보
    market_map = {"KOSPI": "KOSPI", "KOSDAQ": "KOSDAQ", "비상장": "비상장"}
    company_info = {
        "company_name": latest.company_name,
        "founded_year": int(latest.founded_year or 0),
        "ticker": latest.stock_code,
        "market_type": market_map.get((latest.market or "").upper(), latest.market or ""),
        "label": int(latest.label or 0),   # ✅ 추가: 0/1 정수로 고정
    }

    # 2) 연도별 부실확률 (0~1 -> 템플릿에서 x100 처리)
    chart_data = {
        "bankruptcy_probabilities": {int(r.year): float(r.default_prob or 0) for r in rows},
        "title": f"연도별 {latest.company_name} 부실확률",
        # 필요 시 수동 상한: "y_max_pct": 20
    }

    # 3) 뉴스 (최신 연도 5개만)
    news_list = (latest.news_titles or [])[:5]
    news_data = {
        f"news{i+1}": {"title": t, "url": "#"} for i, t in enumerate(news_list)
    }

    # 4) 부실확률 카드
    prob = float(latest.default_prob or 0.0)
    insolvency_data = {
        "percent": f"{prob*100:.1f}%",
        "status": _status_from_prob(prob),
    }

    # 5) 위험요인 슬림 바 (현재 템플릿이 % 문자열을 기대하면 퍼센트 붙여줌)
    risk_factor = {
        "이자보상배율": f"{float(latest.icr or 0):.1f}",
        "부채비율":     f"{float(latest.debt_ratio or 0):.1f}%",
        "ROA":         f"{float(latest.roa or 0):.1f}%",
    }

    # 6) 업종별 평균 부실확률 (최신연도 기준)
    latest_year = int(latest.year)
    q = (
        db.query(
            DashboardFlat.industry_name,
            func.avg(DashboardFlat.default_prob).label("avg_prob"),
        )
        .filter(DashboardFlat.year == latest_year)
        .group_by(DashboardFlat.industry_name)
        .order_by(func.avg(DashboardFlat.default_prob).desc())
    )
    sector_risk = {
        "title": "업종별 평균 부실징후 확률",
        "series": [
            {"label": ind or "기타", "value": float(avg or 0)}
            for ind, avg in q.all()
        ][:6]  # 상위 6개만
    }

    benchmark = build_benchmark(stock_code, db)
    # 부실확률 카드용 보조 데이터
    insolvency_card = {
        # 예: 값이 0.1234(=12.34%)라면
        # "cap_erosion": f"{float(latest.cap_erosion or 0)*100:.1f}%" 
        "cap_erosion": None,   # 당장 없으면 None
}

    return {
        "company_info": company_info,
        "chart_data": chart_data,
        "news_data": news_data,
        "insolvency_data": insolvency_data,
        "insolvency_card": insolvency_card,   # ← 추가
        "risk_factor": risk_factor,
        "sector_risk": sector_risk,
        "benchmark": benchmark,

        # ✅ [추가] 템플릿에서 바로 쓸 값들
        "beneish_mscore": score,
        "beneish_year": int(latest.year),
        "score_fill": score_fill,
        "threshold": THRESHOLD,
        
    }


def resolve_stock_code(corp_id: str, db: Session) -> str:
    """
    사용자가 넣은 corp_id(종목코드/회사명/다양한 포맷)를 dashboard_flat.stock_code(정확 6자리)로 해석
    """
    if not corp_id:
        raise ValueError("empty corp_id")

    s = corp_id.strip().upper()

    # 1) "005930.KS" 같은 포맷 → 숫자만 추출
    import re
    digits = "".join(re.findall(r"\d", s))

    # 2) 전부 숫자면 6자리로 zero-pad
    if digits.isdigit() and digits:
        code = digits.zfill(6)
        # DB에 존재 확인
        exists = (
            db.query(DashboardFlat.stock_code)
              .filter(DashboardFlat.stock_code == code)
              .limit(1).first()
        )
        if exists:
            return code  # 예: 005930, 005380, 051910

    # 3) 숫자가 아니거나 해당 코드가 없으면, 회사명으로 검색 (부분 일치)
    row = (
        db.query(DashboardFlat.stock_code)
          .filter(DashboardFlat.company_name.ilike(f"%{s}%"))
          .order_by(DashboardFlat.company_name.asc(), DashboardFlat.year.desc())
          .limit(1).first()
    )
    if row:
        return row[0]  # stock_code

    # 4) 마지막 시도: 입력 그대로 6자리라면 사용
    if len(s) == 6 and s.isdigit():
        return s

    raise ValueError(f"cannot resolve corp_id: {corp_id}")

def _f(v):
    """None 안전 변환."""
    try:
        return float(v) if v is not None else 0.0
    except Exception:
        return 0.0

def _metric(name, company, industry, direction="higher_better"):
    return {
        "name": name,
        "company": _f(company),
        "industry": _f(industry),
        "direction": direction,  # 'higher_better' | 'lower_better'
    }

def build_benchmark(stock_code: str, db) -> dict:
    """최신연도 기준 회사 vs 동일 업종 평균 비교 묶음 생성"""
    # 최신 로우(회사)
    latest = (
        db.query(DashboardFlat)
          .filter(DashboardFlat.stock_code == stock_code)
          .order_by(DashboardFlat.year.desc())
          .first()
    )
    if not latest:
        return {"categories": [], "tolerance": 0.05}

    latest_year = int(latest.year)
    industry = latest.industry_name

    # 동일 업종, 동일 연도 평균
    avg = (
        db.query(
            func.avg(DashboardFlat.opm),               # 영업이익률
            func.avg(DashboardFlat.npm),               # 순이익률
            func.avg(DashboardFlat.roe),
            func.avg(DashboardFlat.roa),
            func.avg(DashboardFlat.debt_ratio),
            func.avg(DashboardFlat.current_ratio),
            func.avg(DashboardFlat.icr),
            func.avg(DashboardFlat.sales_growth),
            func.avg(DashboardFlat.op_income_growth),
            func.avg(DashboardFlat.asset_turnover),
            func.avg(DashboardFlat.ar_turnover),
        )
        .filter(DashboardFlat.year == latest_year,
                DashboardFlat.industry_name == industry)
        .one()
    )

    (
        avg_opm, avg_npm, avg_roe, avg_roa,
        avg_debt, avg_current, avg_icr,
        avg_sales_g, avg_opinc_g,
        avg_asset_t, avg_ar_t
    ) = [ _f(x) for x in avg ]

    # 카테고리 구성
    categories = [
        {
            "name": "수익성",
            "rule": "업종 평균보다 낮으면 경쟁력 약화",
            "signal_if_worse": "경쟁력 약화",
            "metrics": [
                _metric("영업이익률(%)", latest.opm, avg_opm, "higher_better"),
                _metric("순이익률(%)",   latest.npm, avg_npm, "higher_better"),
                _metric("ROE(%)",      latest.roe, avg_roe, "higher_better"),
                _metric("ROA(%)",      latest.roa, avg_roa, "higher_better"),
            ],
        },
        {
            "name": "안정성",
            "rule": "업종 평균보다 낮거나 위험 구간이면 부실 위험",
            "signal_if_worse": "부실 위험",
            "metrics": [
                _metric("부채비율(%)",     latest.debt_ratio,   avg_debt,   "lower_better"),
                _metric("유동비율(%)",     latest.current_ratio, avg_current,"higher_better"),
                _metric("이자보상배율",     latest.icr,           avg_icr,    "higher_better"),
            ],
        },
        {
            "name": "성장성",
            "rule": "업종 평균보다 못 미치면 경쟁력 하락",
            "signal_if_worse": "경쟁력 하락",
            "metrics": [
                _metric("매출액증가율(%)",   latest.sales_growth,     avg_sales_g, "higher_better"),
                _metric("영업이익증가율(%)", latest.op_income_growth, avg_opinc_g, "higher_better"),
            ],
        },
        {
            "name": "효율성",
            "rule": "업종 대비 과도하게 낮으면 운영 비효율",
            "signal_if_worse": "운영 비효율",
            "metrics": [
                _metric("총자산회전율",     latest.asset_turnover, avg_asset_t, "higher_better"),
                _metric("매출채권회전율",   latest.ar_turnover,    avg_ar_t,    "higher_better"),
            ],
        },
    ]

    return {
        "categories": categories,
        "tolerance": 0.05,   # ±5% 이내 동률
    }


# =====================================================================
# # services/company_service.py

# # 실제 환경에선 DB/크롤러/외부 API 조회가 들어갑니다.
# # 지금은 요청 시마다 최신 값을 반환한다고 가정하고 더미 데이터를 구성합니다.

# def get_company_info(corp_id: str) -> dict:
#     # 간단 매핑(예시). 실제로는 DB에서 corp_id로 조회.
#     name_map = {
#         "005930": "삼성전자",
#         "000660": "SK하이닉스",
#         "373220": "LG에너지솔루션",
#     }
#     company_name = name_map.get(corp_id, f"기업({corp_id})")

#     return {
#         "company_name": company_name,
#         "founded_year": 1969,
#         "ticker": corp_id,
#         "market_type": "코스피",
#     }


# def get_chart_data(company_name: str) -> dict:
#     # 연도별 부실확률(0~1)
#     series = {
#         2018: 0.02,
#         2019: 0.03,
#         2020: 0.08,
#         2021: 0.05,
#         2022: 0.04,
#         2023: 0.06,
#     }
#     return {
#         "bankruptcy_probabilities": series,
#         "title": f"연도별 {company_name} 부실확률",
#     }


# def get_news_data() -> dict:
#     return {
#         "news1": {
#             "title": "삼성전자, AI 반도체 시장 진출 본격화…글로벌 경쟁 격화",
#             "url": "www.naver.com",
#         },
#         "news2": {
#             "title": "LG에너지솔루션, 미국 공장 증설 발표…배터리 수요 대응",
#             "url": "www.naver.com",
#         },
#         "news3": {
#             "title": "카카오, 자회사 구조조정 단행…수익성 개선 나선다",
#             "url": "www.naver.com",
#         },
#         "news4": {
#             "title": "네이버, 일본 시장에서 쇼핑 플랫폼 확대…현지화 전략 주목",
#             "url": "www.naver.com",
#         },
#         "news5": {
#             "title": "현대자동차, 전기차 판매 급증…2030년까지 50% 확대 목표",
#             "url": "www.naver.com",
#         },
#     }


# def get_insolvency_data() -> dict:
#     return {
#         "percent": "56.5%",   # 표시는 퍼센트 문자열
#         "status": "위험",
#     }


# def get_risk_factors() -> dict:
#     # 게이지(막대) 렌더용 — 퍼센트 문자열
#     return {
#         "이자보상배율": "82.0%",
#         "부채비율": "67.0%",
#         "ROA": "54.0%",
#     }


# def get_company_detail(corp_id: str) -> dict:
#     company = get_company_info(corp_id)
#     chart = get_chart_data(company["company_name"])
#     news = get_news_data()
#     insolv = get_insolvency_data()
#     factors = get_risk_factors()
#     bench = get_benchmark_data()
#     sector = get_sector_default_probabilities()     # ✅ 추가

#     return {
#         "company_info": company,
#         "chart_data": chart,
#         "news_data": news,
#         "insolvency_data": insolv,
#         "risk_factor": factors,
#         "benchmark": bench,
#         "sector_risk": sector,                       # ✅ 추가
#     }



# def get_chart_data(company_name: str) -> dict:
#     series = {
#         2018: 0.02,
#         2019: 0.03,
#         2020: 0.08,
#         2021: 0.05,
#         2022: 0.04,
#         2023: 0.06,
#     }
#     # y축 최대 60% (이미지와 동일). 필요시 max에 맞춰 올림 처리해도 됨.
#     return {
#         "bankruptcy_probabilities": series,
#         "title": f"연도별 {company_name} 부실확률",
#         "y_max_pct": 60,                     # y축 상한(퍼센트)
#         "y_ticks": [0, 10, 20, 30, 40, 50, 60],  # 눈금표시
#     }

# def get_benchmark_data() -> dict:
#     """
#     업종 평균 대비 벤치마크(수익성/안정성/성장성/효율성).
#     - value 단위: % 혹은 배 등 임의. 템플릿에서 상대비교만 합니다.
#     - direction: 'higher_better' or 'lower_better'
#     """
#     return {
#         "categories": [
#             {
#                 "name": "수익성",
#                 "rule": "업종 평균보다 낮으면 ‘경쟁력 약화’",
#                 "metrics": [
#                     {"name": "영업이익률", "company": 7.0, "industry": 9.0, "direction": "higher_better"},
#                     {"name": "순이익률", "company": 5.3, "industry": 6.8, "direction": "higher_better"},
#                     {"name": "ROE",     "company": 8.2, "industry": 10.1, "direction": "higher_better"},
#                     {"name": "ROA",     "company": 4.1, "industry": 4.8, "direction": "higher_better"},
#                 ],
#                 "signal_if_worse": "경쟁력 약화",
#             },
#             {
#                 "name": "안정성",
#                 "rule": "업종 평균보다 낮거나 위험 구간이면 ‘부실 위험’",
#                 "metrics": [
#                     # 부채비율은 낮을수록 유리 → lower_better
#                     {"name": "부채비율",   "company": 180, "industry": 160, "direction": "lower_better"},
#                     # 유동비율/이자보상배율은 높을수록 유리 → higher_better
#                     {"name": "유동비율",   "company": 110, "industry": 130, "direction": "higher_better"},
#                     {"name": "이자보상배율","company": 1.8, "industry": 2.4,  "direction": "higher_better"},
#                 ],
#                 "signal_if_worse": "부실 위험",
#             },
#             {
#                 "name": "성장성",
#                 "rule": "업종 평균보다 못 미치면 ‘경쟁력 하락’",
#                 "metrics": [
#                     {"name": "매출액증가율",   "company": 6.0, "industry": 8.5, "direction": "higher_better"},
#                     {"name": "영업이익증가율", "company": 5.0, "industry": 7.2, "direction": "higher_better"},
#                 ],
#                 "signal_if_worse": "경쟁력 하락",
#             },
#             {
#                 "name": "효율성",
#                 "rule": "업종 대비 과도하게 낮으면 ‘운영 비효율’",
#                 "metrics": [
#                     {"name": "총자산회전율",   "company": 0.62, "industry": 0.85, "direction": "higher_better"},
#                     {"name": "매출채권회전율", "company": 6.1,  "industry": 7.4,  "direction": "higher_better"},
#                 ],
#                 "signal_if_worse": "운영 비효율",
#             },
#         ],
#         # 비교 허용 오차(±5%) — 미세 차이는 시그널로 보지 않음
#         "tolerance": 0.05,
#     }

# def get_sector_default_probabilities() -> dict:
#     """
#     업종별 평균 부실징후(부도) 확률 데이터 (0~1 사이)
#     실제 환경에선 DB/분석테이블에서 집계해 반환하세요.
#     """
#     data = [
#         {"sector": "건설",   "prob": 0.112},
#         {"sector": "조선",   "prob": 0.097},
#         {"sector": "철강",   "prob": 0.084},
#         {"sector": "유통",   "prob": 0.071},
#         {"sector": "반도체", "prob": 0.058},
#         {"sector": "자동차", "prob": 0.051},
#     ]
#     return {
#         "title": "업종별 평균 부실징후 확률",
#         "items": data,
#         "x_max_pct": 20,   # x축 상한(%). 예: 20%까지 눈금 표시
#         "x_ticks": [0, 5, 10, 15, 20],
#     }



