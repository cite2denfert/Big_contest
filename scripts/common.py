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


# 업종군: 소비 행태(이동·야외 노출, 필수성)가 비슷한 업종끼리 묶음
INDUSTRY_GROUPS = {
    "외식": ["한식", "일식", "중식", "양식", "기타요식", "패스트푸드", "제과점", "커피전문점"],
    "주점·유흥": ["유흥업소", "노래방", "주류판매"],
    "생활소매": ["할인점/슈퍼마켓/양판점", "편의점", "기타식품", "농수산물", "정육점", "기타유통",
              "생활잡화/수입상품점", "사무기기/문구용품", "체인점", "화원", "애완동물", "LPG가스"],
    "백화점": ["백화점"],
    "패션·뷰티소매": ["의복/의류", "패션잡화", "시계/귀금속", "화장품", "전용매장", "수제용품점"],
    "가정·내구재": ["가구", "가전", "인테리어/건축자재/주방기구", "중고품판매점"],
    "문화·취미": ["서점", "문화용품", "악기/음반", "완구/아동용자전거", "스포츠/레저용품", "영화/공연",
              "게임방/오락실"],
    "야외·레저": ["실내/실외골프장", "종합레저타운/놀이동산", "스포츠시설", "헬스장", "싸우나/목욕탕"],
    "숙박·여행": ["호텔/콘도", "모텔,여관,기타숙박", "여행사/항공사", "고속버스/철도/여객선"],
    "의료": ["일반병원", "종합병원", "치과병원", "한의원", "기타의료", "약국", "동물병원", "보건소"],
    "미용·생활서비스": ["미용실", "미용서비스", "안마/마사지", "세탁소", "예식장/결혼서비스",
                  "장례식장/묘지/장의사", "법률/사무서비스", "회계/변리서비스", "부동산중개",
                  "연구/번역서비스", "방문판매/다단계판매"],
    "교육": ["학원/학습지", "유치원", "독서실"],
    "차량·교통": ["주유소", "자동차서비스", "자동차용품", "주차장", "택시", "오토바이"],
}
GROUP_OF = {ind: g for g, inds in INDUSTRY_GROUPS.items() for ind in inds}


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


def load_climatology():
    """2015~2024 일자료 (scripts/download_weather.py --climatology). ASOS 강수 빈칸 = 무강수."""
    c = pd.read_csv(WEATHER_DIR / "climatology_daily_2015_2024.csv", encoding="utf-8-sig", dtype={"TA_YMD": str})
    c["date"] = pd.to_datetime(c.TA_YMD, format="%Y%m%d")
    c["precipitation_reported_mm"] = c.precipitation_reported_mm.fillna(0)
    return c.dropna(subset=["temperature_max_c"])


def load_weather_hourly():
    wh = pd.read_csv(WEATHER_DIR / "weather_hourly.csv", encoding="utf-8-sig", dtype={"TA_YMD": str})
    wh = wh[wh.is_boundary_extra == 0]
    wh["date"] = pd.to_datetime(wh.TA_YMD, format="%Y%m%d")
    return wh[wh.date.between("2025-07-01", "2025-12-31")]
