# services/company_service.py
from typing import Dict, List, Any
from sqlalchemy.orm import Session
from sqlalchemy import func, or_, and_
import os

from db_models.dashboard_flat import DashboardFlat


# 메일보내기
def _to_float(x):
    try:
        return float(x)
    except:
        return None

def get_latest_alert_companies(
    db: Session,
    alert_threshold_pct: float = None,  # .env에서 가져옴 (예: 60)
    prob_is_percent: bool = False       # default_prob가 0~100인지 여부
) -> List[Dict[str, Any]]:
    """
    회사별 '가장 최신 연도' 레코드만 모은 뒤,
    1) label 컬럼이 있으면 label=1만
    2) 없으면 default_prob 기준으로 경보 임계치 이상만
    반환합니다.
    """
    # 회사별 최신연도 subquery
    subq = (
        db.query(
            DashboardFlat.stock_code.label("stock_code"),
            func.max(DashboardFlat.year).label("max_year")
        ).group_by(DashboardFlat.stock_code)
         .subquery()
    )

    rows = (
        db.query(DashboardFlat)
          .join(subq, and_(
                DashboardFlat.stock_code == subq.c.stock_code,
                DashboardFlat.year == subq.c.max_year
          ))
          .all()
    )

    # 환경설정
    if alert_threshold_pct is None:
        alert_threshold_pct = float(os.getenv("ALERT_THRESHOLD_PCT", "60"))
    prob_is_percent = str(os.getenv("PROB_IS_PERCENT", "false")).lower() == "true"

    alert_list = []
    for r in rows:
        # 1) label이 있으면 그걸 우선 사용
        has_label = hasattr(r, "label")
        is_alert = False

        if has_label and getattr(r, "label") is not None:
            is_alert = int(getattr(r, "label")) == 1
        else:
            # 2) default_prob 기준: 저장 스케일(0~1 or 0~100)에 따라 환산
            p = _to_float(r.default_prob)
            if p is None:
                is_alert = False
            else:
                p_pct = p if prob_is_percent else (p * 100.0)
                is_alert = p_pct >= alert_threshold_pct

        if is_alert:
            # 표시용 값 준비
            p = _to_float(r.default_prob)
            p_pct = None if p is None else (p if prob_is_percent else p * 100.0)

            alert_list.append({
                "stock_code": r.stock_code,
                "year": r.year,
                "company_name": r.company_name,
                "default_prob_pct": None if p_pct is None else round(p_pct, 1),
                "icr": r.icr,
                "capital_impairment_ratio": r.capital_impairment_ratio,
                "debt_ratio": r.debt_ratio,
                "roa": r.roa,
                "roe": r.roe,
            })

    # 정렬(기본: 위험도 내림차순 → 종목코드)
    alert_list.sort(key=lambda x: (x["default_prob_pct"] or -1), reverse=True)
    return alert_list

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
        "industry_category" : latest.industry_category,
        "median_default_prob" : latest.median_default_prob,
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
        "percent": f"{prob:.1f}%",
        "status": _status_from_prob(prob),
    }

    # 5) 위험요인 슬림 바 (현재 템플릿이 % 문자열을 기대하면 퍼센트 붙여줌)
    risk_factor = {
        "매출액증가율": f"{float(latest.sales_growth or 0):.1f}%",
        "ROA":         f"{float(latest.roa or 0):.1f}%",
        "ROE":          f"{float(latest.roe or 0):.1f}%",
        "차입금의존도": f"{float(latest.borrow_dependence or 0):.1f}%",
        "이자보상배율": f"{float(latest.icr or 0):.1f}",
        "부채비율":     f"{float(latest.debt_ratio or 0):.1f}%",
        "매출액순이익률": f"{float(latest.npm or 0):.1f}%",
        "유동비율":     f"{float(latest.current_ratio or 0):.1f}%",
        "당좌비율":     f"{float(latest.quick_ratio or 0):.1f}%",
        "자본잠식률":     f"{float(latest.capital_impairment_ratio or 0):.1f}%",
    }

    # 6) 업종별 평균 부실확률 (최신연도 기준, 대분류 전체 + 현재업종 강조 세트)
    # === 6) 업종별 '중앙값 부실확률' 그대로 사용 (0~1 스케일 가정) ===
    latest_year = int(latest.year)
    target_cat  = (latest.industry_category or "기타")

    # ✅ 여기를 실제 컬럼명으로 바꿔주세요.
    # 예시 후보:
    #   DashboardFlat.industry_median_default_prob
    #   DashboardFlat.industry_median_prob
    #   DashboardFlat.sector_median_default_prob
    COL = DashboardFlat.median_default_prob  # <-- 실제 컬럼명으로!

    # 대분류별 중앙값(이미 계산된 값)을 그대로 가져옴
    q_all = (
        db.query(
            DashboardFlat.industry_category.label("cat"),
            # 같은 연/업종이면 값이 동일하다고 가정 → 집계는 max/avg 아무거나 무방
            func.max(COL).label("med_prob")
        )
        .filter(DashboardFlat.year == latest_year)
        .group_by(DashboardFlat.industry_category)
    )

    # (라벨, 값[0~1]) 리스트
    all_rows = [(lbl or "기타", float(v or 0)) for lbl, v in q_all.all()]
    # 보기 좋게 내림차순 정렬
    all_rows.sort(key=lambda x: x[1], reverse=True)

    # 상위 5개 + 현재 회사 업종(없으면 추가)
    top = all_rows[:5]
    if target_cat not in [l for (l, _) in top]:
        t_val = next((v for (l, v) in all_rows if l == target_cat), None)
        if t_val is not None:
            top.append((target_cat, t_val))

    # 중복 제거 + 강조 플래그
    seen = set()
    series = []
    for label, val in top:
        if label in seen:
            continue
        seen.add(label)
        series.append({
            "label": label,
            "value": val,                      # 0~1 값(프론트에서 ×100 → %)
            "highlight": (label == target_cat)
        })

    sector_risk = {
        "title": "업종별 평균 부실징후 확률",
        "series": series,                                   # 기본 6개
        "all_series": [{"label": l, "value": v} for l, v in all_rows],  # 필터용 17개 전체
        "highlight_label": target_cat,
        "y_max_pct": 100,
        "y_ticks": [0,10,20,30,40,50,60,70,80,90,100],
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
    """최신연도 기준: 회사 값 vs 같은 로우의 업종 중앙값(median_*) 비교"""
    latest = (
        db.query(DashboardFlat)
          .filter(DashboardFlat.stock_code == stock_code)
          .order_by(DashboardFlat.year.desc())
          .first()
    )
    if not latest:
        return {"categories": [], "tolerance": 0.05}

    categories = [
        {
            "name": "수익성",
            "rule": "업종 평균보다 낮으면 경쟁력 약화",
            "signal_if_worse": "경쟁력 약화",
            "metrics": [
                _metric("영업이익률(%)", latest.opm, latest.median_opm, "higher_better"),
                _metric("순이익률(%)",   latest.npm, latest.median_npm, "higher_better"),
                _metric("ROE(%)",      latest.roe, latest.median_roe, "higher_better"),
                _metric("ROA(%)",      latest.roa, latest.median_roa, "higher_better"),
            ],
        },
        {
            "name": "안정성",
            "rule": "업종 평균보다 낮거나 위험 구간이면 부실 위험",
            "signal_if_worse": "부실 위험",
            "metrics": [
                _metric("부채비율(%)", latest.debt_ratio, latest.median_debt_ratio, "lower_better"),
                _metric("유동비율(%)", latest.current_ratio, latest.median_current_ratio, "higher_better"),
                _metric("이자보상배율", latest.icr, latest.median_icr, "higher_better"),
            ],
        },
        {
            "name": "성장성",
            "rule": "업종 평균보다 못 미치면 경쟁력 하락",
            "signal_if_worse": "경쟁력 하락",
            "metrics": [
                _metric("매출액증가율(%)", latest.sales_growth, latest.median_sales_growth, "higher_better"),
                _metric("영업이익증가율(%)", latest.op_income_growth, latest.median_op_income_growth, "higher_better"),
            ],
        },
        {
            "name": "효율성",
            "rule": "업종 대비 과도하게 낮으면 운영 비효율",
            "signal_if_worse": "운영 비효율",
            "metrics": [
                _metric("총자산회전율", latest.asset_turnover, latest.median_asset_turnover, "higher_better"),
                _metric("매출채권회전율", latest.ar_turnover, latest.median_ar_turnover, "higher_better"),
            ],
        },
    ]
    return {"categories": categories, "tolerance": 0.05}



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



