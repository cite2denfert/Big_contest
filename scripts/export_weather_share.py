"""팀 전달·제출용 기상 자료 엑셀 1개 (분석에 쓴 세 표를 시트로).

값은 data/weather의 CSV를 그대로 옮긴다(빈칸 유지). 분석에서 강수 빈칸을 0으로 바꾸는 처리는 README에 적는다.
실행: uv run --no-project --with pandas --with openpyxl python -X utf8 scripts/export_weather_share.py
"""
import pandas as pd

from common import ROOT, WEATHER_DIR

OUT = ROOT / "share" / "외부데이터_전달" / "기상청_관측자료_강남_춘천.xlsx"
OUT.parent.mkdir(parents=True, exist_ok=True)

KO = {"station_id": "지점번호", "station_name": "지점명", "station_type": "관측종류", "MCT_SGG_CD": "지역(카드 결합 키)",
      "TA_YMD": "날짜(TA_YMD)", "datetime_kst": "관측시각(KST)", "TIME_GB": "시간대(TIME_GB)",
      "temperature_mean_c": "평균기온(℃)", "temperature_min_c": "최저기온(℃)", "temperature_max_c": "최고기온(℃)",
      "temperature_c": "기온(℃)", "precipitation_reported_mm": "강수량(mm)", "wind_speed_mean_ms": "평균풍속(m/s)",
      "wind_gust_max_ms": "최대순간풍속(m/s)", "relative_humidity_mean_pct": "평균습도(%)",
      "relative_humidity_pct": "습도(%)", "wind_speed_ms": "풍속(m/s)"}

daily = pd.read_csv(WEATHER_DIR / "weather_daily.csv", encoding="utf-8-sig", dtype={"TA_YMD": str})
hourly = pd.read_csv(WEATHER_DIR / "weather_hourly.csv", encoding="utf-8-sig", dtype={"TA_YMD": str})
hourly = hourly[hourly.is_boundary_extra == 0].drop(columns="is_boundary_extra")
clim = pd.read_csv(WEATHER_DIR / "climatology_daily_2015_2024.csv", encoding="utf-8-sig", dtype={"TA_YMD": str})

guide = pd.DataFrame({"항목": [
    "출처", "관측소", "시트: 일별_2025", "시트: 시간별_2025", "시트: 일별_2015_2024", "빈칸", "수집·정제 설명"], "내용": [
    "기상청 기상자료개방포털(data.kma.go.kr) 공개 조회 화면. 무료 공개 자료",
    "춘천 ASOS 101, 강남 AWS 400",
    f"2025-07-01~12-31 기상청 공식 일별 값 ({len(daily):,}행)",
    f"2025-07-01~12-31 시간별 값 ({len(hourly):,}행)",
    f"2015~2024 일별 값, 평년 비교용 ({len(clim):,}행)",
    "원본 그대로 둠. 강수량 빈칸은 비가 오지 않은 날(분석에서 0으로 처리)",
    "README.md 참고"]})

with pd.ExcelWriter(OUT, engine="openpyxl") as xw:
    for name, df in [("안내", guide), ("일별_2025", daily), ("시간별_2025", hourly), ("일별_2015_2024", clim)]:
        df.rename(columns=KO).to_excel(xw, sheet_name=name, index=False)
        ws = xw.sheets[name]
        ws.freeze_panes = "A2"
        ws.auto_filter.ref = ws.dimensions
        for col in ws.columns:
            ws.column_dimensions[col[0].column_letter].width = 60 if name == "안내" and col[0].column_letter == "B" else 16
print("wrote", OUT)
