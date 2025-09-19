# etl/load_csv.py
import argparse
import re
import numpy as np
import pandas as pd
from sqlalchemy import text
from db import engine  # 프로젝트 루트의 db.py에서 engine 재사용


def to_year(x):
    if pd.isna(x):
        return None
    s = str(x)
    m = re.search(r"(19|20)\d{2}", s)
    return int(m.group(0)) if m else None


def zfill6(x):
    if pd.isna(x):
        return None
    try:
        s = str(int(x))
    except Exception:
        s = str(x).strip()
    return s.zfill(6)


def binarize_label(x):
    try:
        v = float(x)
    except Exception:
        return 0
    if v >= 0.5:
        return 1
    if v <= 0:
        return 0
    return int(round(v))


def main(csv_path: str, encoding: str | None, truncate: bool):
    # CSV 로드 (utf-8 우선, 실패 시 cp949)
    try:
        df = pd.read_csv(csv_path, encoding=encoding or "utf-8")
    except UnicodeDecodeError:
        df = pd.read_csv(csv_path, encoding="cp949")

    # 필수 컬럼(41개) 점검
    required = [
        "회사명","거래소코드","산업코드","산업명","시장","설립일","연도",
        "부실징후확률","이자보상배율","자본잠식률","영업이익률","순이익률","ROA","ROE",
        "유동비율","당좌비율","부채비율","차입금의존도","Beneish M-Score",
        "매출액증가율","영업이익증가율","총자산회전율","매출채권회전율",
        "label","산업대분류명",
        "업종중앙값 부실징후확률","업종중앙값 이자보상배율","업종중앙값 자본잠식률",
        "업종중앙값 영업이익률","업종중앙값 순이익률","업종중앙값 ROA","업종중앙값 ROE",
        "업종중앙값 유동비율","업종중앙값 당좌비율","업종중앙값 부채비율","업종중앙값 차입금의존도",
        "업종중앙값 Beneish M-Score","업종중앙값 매출액증가율","업종중앙값 영업이익증가율",
        "업종중앙값 총자산회전율","업종중앙값 매출채권회전율",
    ]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"필수 컬럼 누락: {missing}")

    # 표준 스키마로 매핑
    out = pd.DataFrame({
        "stock_code": df["거래소코드"].apply(zfill6),
        "year": df["연도"].astype(int),
        "company_name": df["회사명"].astype(str),
        "industry_code": df["산업코드"].astype(str),
        "industry_name": df["산업명"].astype(str),
        "market": df["시장"].astype(str),
        "founded_year": df["설립일"].apply(to_year),

        "default_prob": df["부실징후확률"].astype(float),
        "icr": df["이자보상배율"].astype(float),
        "capital_impairment_ratio": df["자본잠식률"].astype(float),
        "opm": df["영업이익률"].astype(float),
        "npm": df["순이익률"].astype(float),
        "roa": df["ROA"].astype(float),
        "roe": df["ROE"].astype(float),
        "current_ratio": df["유동비율"].astype(float),
        "quick_ratio": df["당좌비율"].astype(float),
        "debt_ratio": df["부채비율"].astype(float),
        "borrow_dependence": df["차입금의존도"].astype(float),
        "beneish_mscore": df["Beneish M-Score"].astype(float),
        "sales_growth": df["매출액증가율"].astype(float),
        "op_income_growth": df["영업이익증가율"].astype(float),
        "asset_turnover": df["총자산회전율"].astype(float),
        "ar_turnover": df["매출채권회전율"].astype(float),
        "label": df["label"].apply(binarize_label).astype(int),
        "industry_category": df["산업대분류명"].astype(str),

        # 업종 중앙값 → median_*
        "median_default_prob": df["업종중앙값 부실징후확률"].astype(float),
        "median_icr": df["업종중앙값 이자보상배율"].astype(float),
        "median_capital_impairment_ratio": df["업종중앙값 자본잠식률"].astype(float),
        "median_opm": df["업종중앙값 영업이익률"].astype(float),
        "median_npm": df["업종중앙값 순이익률"].astype(float),
        "median_roa": df["업종중앙값 ROA"].astype(float),
        "median_roe": df["업종중앙값 ROE"].astype(float),
        "median_current_ratio": df["업종중앙값 유동비율"].astype(float),
        "median_quick_ratio": df["업종중앙값 당좌비율"].astype(float),
        "median_debt_ratio": df["업종중앙값 부채비율"].astype(float),
        "median_borrow_dependence": df["업종중앙값 차입금의존도"].astype(float),
        "median_beneish_mscore": df["업종중앙값 Beneish M-Score"].astype(float),
        "median_sales_growth": df["업종중앙값 매출액증가율"].astype(float),
        "median_op_income_growth": df["업종중앙값 영업이익증가율"].astype(float),
        "median_asset_turnover": df["업종중앙값 총자산회전율"].astype(float),
        "median_ar_turnover": df["업종중앙값 매출채권회전율"].astype(float),
    })

    # (stock_code, year) 중복 제거
    out = out.drop_duplicates(subset=["stock_code", "year"], keep="last")

    # 1) '_m<숫자>' 접미사 제거 + 오타 보정
    def strip_suffix(c: str) -> str:
        return re.sub(r"_m\d+$", "", c)
    out = out.rename(columns={c: strip_suffix(c) for c in out.columns})
    if "ustry_category" in out.columns:
        out = out.rename(columns={"ustry_category": "industry_category"})

    # 2) 컬럼 순서를 DB 스키마와 동일하게 고정(41개)
    cols = [
        "stock_code","year","company_name","industry_code","industry_name","market",
        "founded_year",
        "default_prob","icr","capital_impairment_ratio","opm","npm","roa","roe",
        "current_ratio","quick_ratio","debt_ratio","borrow_dependence","beneish_mscore",
        "sales_growth","op_income_growth","asset_turnover","ar_turnover","label",
        "industry_category",
        "median_default_prob","median_icr","median_capital_impairment_ratio","median_opm",
        "median_npm","median_roa","median_roe","median_current_ratio","median_quick_ratio",
        "median_debt_ratio","median_borrow_dependence","median_beneish_mscore",
        "median_sales_growth","median_op_income_growth","median_asset_turnover",
        "median_ar_turnover"
    ]
    out = out.reindex(columns=cols)

    # 3) 값 정리: NaN/±inf → NULL, 타입 고정
    out = out.replace([np.inf, -np.inf], pd.NA)
    out = out.where(pd.notnull(out), None)  # NaN -> None
    out["label"] = out["label"].astype(int)
    out["year"] = out["year"].astype(int)
    out["stock_code"] = out["stock_code"].astype(str)

    # 적재
    with engine.begin() as conn:
        # 스키마 보강
        conn.execute(text("""
            ALTER TABLE dashboard_flat
                ADD COLUMN IF NOT EXISTS stock_code              TEXT,
                ADD COLUMN IF NOT EXISTS company_name            TEXT,
                ADD COLUMN IF NOT EXISTS industry_code           TEXT,
                ADD COLUMN IF NOT EXISTS industry_name           TEXT,
                ADD COLUMN IF NOT EXISTS market                  TEXT,
                ADD COLUMN IF NOT EXISTS founded_year            INT,
                ADD COLUMN IF NOT EXISTS year                    INT,

                ADD COLUMN IF NOT EXISTS default_prob            NUMERIC,
                ADD COLUMN IF NOT EXISTS icr                     NUMERIC,
                ADD COLUMN IF NOT EXISTS capital_impairment_ratio NUMERIC,
                ADD COLUMN IF NOT EXISTS opm                     NUMERIC,
                ADD COLUMN IF NOT EXISTS npm                     NUMERIC,
                ADD COLUMN IF NOT EXISTS roa                     NUMERIC,
                ADD COLUMN IF NOT EXISTS roe                     NUMERIC,
                ADD COLUMN IF NOT EXISTS current_ratio           NUMERIC,
                ADD COLUMN IF NOT EXISTS quick_ratio             NUMERIC,
                ADD COLUMN IF NOT EXISTS debt_ratio              NUMERIC,
                ADD COLUMN IF NOT EXISTS borrow_dependence       NUMERIC,
                ADD COLUMN IF NOT EXISTS beneish_mscore          NUMERIC,
                ADD COLUMN IF NOT EXISTS sales_growth            NUMERIC,
                ADD COLUMN IF NOT EXISTS op_income_growth        NUMERIC,
                ADD COLUMN IF NOT EXISTS asset_turnover          NUMERIC,
                ADD COLUMN IF NOT EXISTS ar_turnover             NUMERIC,
                ADD COLUMN IF NOT EXISTS label                   INT,
                ADD COLUMN IF NOT EXISTS industry_category       TEXT,

                ADD COLUMN IF NOT EXISTS median_default_prob      NUMERIC,
                ADD COLUMN IF NOT EXISTS median_icr               NUMERIC,
                ADD COLUMN IF NOT EXISTS median_capital_impairment_ratio NUMERIC,
                ADD COLUMN IF NOT EXISTS median_opm               NUMERIC,
                ADD COLUMN IF NOT EXISTS median_npm               NUMERIC,
                ADD COLUMN IF NOT EXISTS median_roa               NUMERIC,
                ADD COLUMN IF NOT EXISTS median_roe               NUMERIC,
                ADD COLUMN IF NOT EXISTS median_current_ratio     NUMERIC,
                ADD COLUMN IF NOT EXISTS median_quick_ratio       NUMERIC,
                ADD COLUMN IF NOT EXISTS median_debt_ratio        NUMERIC,
                ADD COLUMN IF NOT EXISTS median_borrow_dependence NUMERIC,
                ADD COLUMN IF NOT EXISTS median_beneish_mscore    NUMERIC,
                ADD COLUMN IF NOT EXISTS median_sales_growth      NUMERIC,
                ADD COLUMN IF NOT EXISTS median_op_income_growth  NUMERIC,
                ADD COLUMN IF NOT EXISTS median_asset_turnover    NUMERIC,
                ADD COLUMN IF NOT EXISTS median_ar_turnover       NUMERIC;
        """))
        # 과거 JSONB 컬럼 제거
        conn.execute(text("ALTER TABLE dashboard_flat DROP COLUMN IF EXISTS industry_medians;"))

        # 초기화 옵션
        if truncate:
            conn.execute(text("TRUNCATE TABLE dashboard_flat;"))

    # 청크 적재(문제 청크는 단일/행단위로 재시도해 원인 추적)
    CHUNK = 4000  # 넉넉히 줄임
    for i in range(0, len(out), CHUNK):
        chunk = out.iloc[i:i+CHUNK].copy()
        try:
            chunk.to_sql(
                "dashboard_flat",
                con=engine,       # 청크별 독립 트랜잭션
                if_exists="append",
                index=False,
                method="multi",
                chunksize=800,    # 내부 분할
            )
            print(f"[OK] chunk {i}..{i+len(chunk)-1}")
        except Exception as e:
            # 1) 멀티 실패 원인 요약
            print(f"[ERR] multi insert failed for chunk {i}..{i+len(chunk)-1}: {type(e).__name__}: {e}")

            # 2) 단일 모드로 재시도(여기서 대부분 진짜 에러가 더 짧게 나옵니다)
            try:
                chunk.to_sql(
                    "dashboard_flat",
                    con=engine,
                    if_exists="append",
                    index=False,
                    method=None,
                )
                print(f"[OK] chunk {i}..{i+len(chunk)-1} single mode")
            except Exception as e2:
                print(f"[ERR] single insert failed for chunk {i}..{i+len(chunk)-1}: {type(e2).__name__}: {e2}")

                # 3) 그래도 실패하면 '문제 행'을 정확히 찾자: 행단위로 시도
                for j in range(len(chunk)):
                    row_df = chunk.iloc[[j]].copy()
                    try:
                        row_df.to_sql(
                            "dashboard_flat",
                            con=engine,
                            if_exists="append",
                            index=False,
                            method=None,
                        )
                    except Exception as e3:
                        print(f"[FATAL] row index {i+j} failed: {type(e3).__name__}: {e3}")
                        # 문제 행 내용 샘플 출력
                        print("Row data:", row_df.to_dict("records")[0])
                        raise



if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", default="etl/대시보드용데이터.csv")
    ap.add_argument("--encoding", default=None)
    ap.add_argument("--truncate", action="store_true", help="적재 전 TRUNCATE 실행")
    args = ap.parse_args()
    main(args.csv, args.encoding, args.truncate)
