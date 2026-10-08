"""분석 스크립트 공통 상수·로더."""
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
CARD_DIR = ROOT / "2026빅콘테스트_신한카드_데이터_레이아웃"
FLOW_DIR = ROOT / "2026빅콘테스트_sk통신인구_데이터_레이아웃"
WEATHER_DIR = ROOT / "data" / "weather"

REGIONS = ["서울 강남구", "강원 춘천시"]

# 2025-07~12 공휴일(대체공휴일 포함)
HOLIDAYS = pd.to_datetime(["2025-08-15", "2025-10-03", "2025-10-05", "2025-10-06",
                           "2025-10-07", "2025-10-08", "2025-10-09", "2025-12-25"])

# 지역 상권 매출로 보기 어려운 업종
# - 세금·금융·통신·온라인결제·고가 자동차 등: 결제 성격상 상권과 무관 (EDA)
# - 컴퓨터/소프트웨어, 쇼핑몰: 정기결제·통신판매 패턴 (scripts/check_online_industries.py)
NON_COMMERCE = ["세금공과금", "ZZ_나머지", "결제대행(PG)", "학교등록금", "보험",
                "통신요금(PC통신,무선호출)", "통신요금(이동,시내전화)", "상품권/복권",
                "수입자동차", "중고차판매", "면세점", "컴퓨터/소프트웨어", "쇼핑몰"]


def load_card(n):
    """신한카드 데이터 n(1 또는 2)."""
    d = pd.read_csv(CARD_DIR / f"신한카드_빅콘테스트2026_데이터{n}.txt", sep="\t", encoding="cp949",
                    dtype={"TA_YMD": str})
    d["date"] = pd.to_datetime(d.TA_YMD, format="%Y%m%d")
    return d


def commerce(card):
    """개인 결제 + 상권 업종만."""
    return card[(card.SEX_CCD != "법인") & ~card.MCT_RY_CD.isin(NON_COMMERCE)]


def load_weather_daily():
    wd = pd.read_csv(WEATHER_DIR / "weather_daily.csv", encoding="utf-8-sig", dtype={"TA_YMD": str})
    wd["date"] = pd.to_datetime(wd.TA_YMD, format="%Y%m%d")
    return wd[wd.date.between("2025-07-01", "2025-12-31")]


def load_weather_hourly():
    wh = pd.read_csv(WEATHER_DIR / "weather_hourly.csv", encoding="utf-8-sig", dtype={"TA_YMD": str})
    wh = wh[wh.is_boundary_extra == 0]
    wh["date"] = pd.to_datetime(wh.TA_YMD, format="%Y%m%d")
    return wh[wh.date.between("2025-07-01", "2025-12-31")]
