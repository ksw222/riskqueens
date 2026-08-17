"""Database-backed dashboard data.

`default_prob` is always stored and compared as a probability in the 0–1 range.
Only values returned to templates/charts use percentages.
"""
import os
from typing import Any

from sqlalchemy import and_, func
from sqlalchemy.orm import Session

from db_models.dashboard_flat import DashboardFlat

THRESHOLD = -2.22


def _number(value: Any, default: float = 0.0) -> float:
    try:
        return float(value) if value is not None else default
    except (TypeError, ValueError):
        return default


def _status_from_prob(probability: float) -> str:
    if probability >= 0.6:
        return "위험"
    if probability >= 0.4:
        return "경고"
    return "양호"


def get_latest_alert_companies(db: Session, alert_threshold_pct: float | None = None) -> list[dict[str, Any]]:
    threshold = (alert_threshold_pct if alert_threshold_pct is not None
                 else float(os.getenv("ALERT_THRESHOLD_PCT", "60"))) / 100
    newest = (db.query(DashboardFlat.stock_code.label("stock_code"), func.max(DashboardFlat.year).label("year"))
              .group_by(DashboardFlat.stock_code).subquery())
    rows = (db.query(DashboardFlat).join(newest, and_(DashboardFlat.stock_code == newest.c.stock_code,
                                                       DashboardFlat.year == newest.c.year)).all())
    alerts = []
    for row in rows:
        probability = _number(row.default_prob)
        if (row.label is not None and int(row.label) == 1) or (row.label is None and probability >= threshold):
            alerts.append({"stock_code": row.stock_code, "year": row.year, "company_name": row.company_name,
                           "default_prob_pct": round(probability * 100, 1), "icr": row.icr,
                           "capital_impairment_ratio": row.capital_impairment_ratio, "debt_ratio": row.debt_ratio,
                           "roa": row.roa, "roe": row.roe})
    return sorted(alerts, key=lambda item: item["default_prob_pct"], reverse=True)


def resolve_stock_code(corp_id: str, db: Session) -> str:
    if not corp_id:
        raise ValueError("empty company identifier")
    value = corp_id.strip().upper()
    digits = "".join(c for c in value if c.isdigit())
    if digits:
        code = digits.zfill(6)
        if db.query(DashboardFlat.stock_code).filter(DashboardFlat.stock_code == code).first():
            return code
    found = (db.query(DashboardFlat.stock_code).filter(DashboardFlat.company_name.ilike(f"%{value}%"))
             .order_by(DashboardFlat.year.desc()).first())
    if found:
        return found[0]
    if len(value) == 6 and value.isdigit():
        return value
    raise ValueError("company not found")


def _metric(name: str, company: Any, industry: Any, direction: str = "higher_better") -> dict:
    return {"name": name, "company": _number(company), "industry": _number(industry), "direction": direction}


def build_benchmark(stock_code: str, db: Session) -> dict:
    latest = (db.query(DashboardFlat).filter(DashboardFlat.stock_code == stock_code)
              .order_by(DashboardFlat.year.desc()).first())
    if not latest:
        return {"categories": [], "tolerance": 0.05}
    # These values are median_* columns, so templates must call them medians, not averages.
    categories = [
        {"name": "수익성", "rule": "업종 중앙값 대비", "signal_if_worse": "수익성 약화",
         "metrics": [_metric("영업이익률(%)", latest.opm, latest.median_opm), _metric("순이익률(%)", latest.npm, latest.median_npm),
                     _metric("ROE(%)", latest.roe, latest.median_roe), _metric("ROA(%)", latest.roa, latest.median_roa)]},
        {"name": "안정성", "rule": "업종 중앙값 대비", "signal_if_worse": "재무 위험",
         "metrics": [_metric("부채비율(%)", latest.debt_ratio, latest.median_debt_ratio, "lower_better"),
                     _metric("유동비율(%)", latest.current_ratio, latest.median_current_ratio), _metric("이자보상배율", latest.icr, latest.median_icr)]},
        {"name": "성장성", "rule": "업종 중앙값 대비", "signal_if_worse": "성장성 하락",
         "metrics": [_metric("매출액증가율(%)", latest.sales_growth, latest.median_sales_growth),
                     _metric("영업이익증가율(%)", latest.op_income_growth, latest.median_op_income_growth)]},
        {"name": "효율성", "rule": "업종 중앙값 대비", "signal_if_worse": "운영 비효율",
         "metrics": [_metric("총자산회전율", latest.asset_turnover, latest.median_asset_turnover),
                     _metric("매출채권회전율", latest.ar_turnover, latest.median_ar_turnover)]},
    ]
    return {"categories": categories, "tolerance": 0.05}


def get_company_detail(stock_code: str, db: Session) -> dict:
    rows = (db.query(DashboardFlat).filter(DashboardFlat.stock_code == stock_code)
            .order_by(DashboardFlat.year.asc()).all())
    if not rows:
        raise ValueError("company data not found")
    latest = rows[-1]
    probability = _number(latest.default_prob)
    score = _number(latest.beneish_mscore, None)
    industry_rows = (db.query(DashboardFlat.industry_category.label("label"), func.max(DashboardFlat.median_default_prob).label("value"))
                     .filter(DashboardFlat.year == latest.year).group_by(DashboardFlat.industry_category).all())
    all_series = [{"label": label or "기타", "value": round(_number(value) * 100, 1)} for label, value in industry_rows]
    all_series.sort(key=lambda item: item["value"], reverse=True)
    target = latest.industry_category or "기타"
    series = all_series[:5]
    if target not in [item["label"] for item in series]:
        matching = next((item for item in all_series if item["label"] == target), None)
        if matching:
            series.append(matching)
    for item in series:
        item["highlight"] = item["label"] == target
    return {
        "default_prob": probability,
        "company_info": {"company_name": latest.company_name, "founded_year": int(latest.founded_year or 0),
                         "ticker": latest.stock_code, "market_type": latest.market or "", "industry_category": target,
                         "median_default_prob_pct": round(_number(latest.median_default_prob) * 100, 1)},
        "chart_data": {"bankruptcy_probabilities": {int(row.year): round(_number(row.default_prob) * 100, 1) for row in rows},
                       "title": f"{latest.company_name} 연도별 부실확률"},
        "news_data": {f"news{i + 1}": {"title": title, "url": "#"} for i, title in enumerate((latest.news_titles or [])[:5])},
        "insolvency_data": {"percent": f"{probability * 100:.1f}%", "status": _status_from_prob(probability)},
        "risk_factor": {"ROA": f"{_number(latest.roa):.1f}%", "ROE": f"{_number(latest.roe):.1f}%", "부채비율": f"{_number(latest.debt_ratio):.1f}%", "이자보상배율": f"{_number(latest.icr):.1f}"},
        "sector_risk": {"title": "업종별 부실확률 중앙값", "series": series, "all_series": all_series,
                        "highlight_label": target, "y_max_pct": 100, "y_ticks": list(range(0, 101, 10))},
        "benchmark": build_benchmark(stock_code, db), "beneish_mscore": score, "beneish_year": int(latest.year),
        "score_fill": 100 if score is not None and score >= THRESHOLD else 0, "threshold": THRESHOLD,
    }
