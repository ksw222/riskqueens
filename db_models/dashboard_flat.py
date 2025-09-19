# db_models/dashboard_flat.py
from sqlalchemy import (
    Column, String, Text, Integer, Numeric,
    CheckConstraint, Index
)
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import declarative_mixin
from db import Base


class DashboardFlat(Base):
    __tablename__ = "dashboard_flat"

    # === PK (복합키) ===
    stock_code   = Column(String(10), primary_key=True)  # "000000" 형식 보장(ETL에서 zfill)
    year         = Column(Integer,     primary_key=True)

    # === 기본 정보 ===
    company_name     = Column(Text, nullable=False)
    industry_code    = Column(Text)   # 예: '33101'
    industry_name    = Column(Text)   # 한글 업종명
    industry_category= Column(Text)   # 대분류 (예: 제조업)
    market           = Column(Text)   # 'KOSPI' | 'KOSDAQ' | '비상장' (또는 NULL)
    founded_year     = Column(Integer)

    # 선택: 뉴스 타이틀(있을 수 있음; ETL에서는 없어도 무관)
    news_titles      = Column(ARRAY(Text), default=list)

    # === 회사 지표 ===
    default_prob          = Column(Numeric)  # 부실징후확률
    icr                   = Column(Numeric)  # 이자보상배율
    capital_impairment_ratio = Column(Numeric)  # 자본잠식률
    opm                   = Column(Numeric)  # 영업이익률
    npm                   = Column(Numeric)  # 순이익률
    roa                   = Column(Numeric)
    roe                   = Column(Numeric)
    current_ratio         = Column(Numeric)
    quick_ratio           = Column(Numeric)  # 당좌비율
    debt_ratio            = Column(Numeric)
    borrow_dependence     = Column(Numeric)  # 차입금의존도
    beneish_mscore        = Column(Numeric)
    sales_growth          = Column(Numeric)
    op_income_growth      = Column(Numeric)
    asset_turnover        = Column(Numeric)
    ar_turnover           = Column(Numeric)

    # binary label (0/1)
    label                 = Column(Integer)  # ETL에서 0/1 정규화

    # === 업종 중앙값(median_*) ===
    median_default_prob           = Column(Numeric)
    median_icr                    = Column(Numeric)
    median_capital_impairment_ratio = Column(Numeric)
    median_opm                    = Column(Numeric)
    median_npm                    = Column(Numeric)
    median_roa                    = Column(Numeric)
    median_roe                    = Column(Numeric)
    median_current_ratio          = Column(Numeric)
    median_quick_ratio            = Column(Numeric)
    median_debt_ratio             = Column(Numeric)
    median_borrow_dependence      = Column(Numeric)
    median_beneish_mscore         = Column(Numeric)
    median_sales_growth           = Column(Numeric)
    median_op_income_growth       = Column(Numeric)
    median_asset_turnover         = Column(Numeric)
    median_ar_turnover            = Column(Numeric)

    # === 제약/인덱스 ===
    __table_args__ = (
        # market 체크 제약: NULL 허용 + 세 가지 값만
        CheckConstraint(
            "(market IS NULL) OR (market IN ('KOSPI','KOSDAQ','비상장'))",
            name="dashboard_flat_market_check",
        ),
        # label 이진 제약(0/1) — DB에 동일 제약이 있으면 생략 가능
        CheckConstraint(
            "(label IS NULL) OR (label IN (0,1))",
            name="chk_dashboard_flat_label_binary",
        ),
        # 조회 최적화 인덱스
        Index("ix_dashboard_flat_code_year", "stock_code", "year"),
        Index("ix_dashboard_flat_industry_year", "industry_code", "year"),
    )

    def __repr__(self) -> str:
        return f"<DashboardFlat {self.stock_code}/{self.year} {self.company_name}>"
