# db_models/dashboard_flat.py
from sqlalchemy import Column, String, Text, Integer, Numeric
from sqlalchemy.dialects.postgresql import ARRAY
from db import Base

class DashboardFlat(Base):
    __tablename__ = "dashboard_flat"

    stock_code   = Column(String(10), primary_key=True)
    year         = Column(Integer, primary_key=True)

    company_name = Column(Text, nullable=False)
    industry_code= Column(Text)
    industry_name= Column(Text)
    market       = Column(Text)         # 'KOSPI','KOSDAQ',...
    founded_year = Column(Integer)

    news_titles  = Column(ARRAY(Text), default=[])

    default_prob = Column(Numeric(6, 4))  # 0~1
    icr          = Column(Numeric)        # 이자보상배율
    debt_ratio   = Column(Numeric)        # %
    roa          = Column(Numeric)        # %
    roe          = Column(Numeric)        # %
    opm          = Column(Numeric)        # %
    npm          = Column(Numeric)        # %
    current_ratio= Column(Numeric)        # %
    sales_growth = Column(Numeric)        # %
    op_income_growth = Column(Numeric)    # %
    asset_turnover   = Column(Numeric)
    ar_turnover      = Column(Numeric)
