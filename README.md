# 2026 빅콘테스트 AI 데이터분석 분야

주제: **기후 위기에 따른 취약 상권 영향 분석** (서울 강남구 · 강원 춘천시, 2025-07 ~ 2025-12)

## 데이터 배치

공모전 제공 데이터와 기상 원자료는 저장소에 포함하지 않는다. 아래 위치에 두고 실행한다.

| 경로 | 내용 |
|---|---|
| `2026빅콘테스트_신한카드_데이터_레이아웃/` | 신한카드 데이터1·2 (txt, cp949, 탭 구분) |
| `2026빅콘테스트_sk통신인구_데이터_레이아웃/` | SK 유동인구 월별 CSV (`\|` 구분) |
| `data/weather/` | 기상청 관측자료. `python -X utf8 scripts/download_weather.py --download`로 재수집 |

## 분석 스크립트

| 스크립트 | 결과 |
|---|---|
| `scripts/eda_basic.py` | `outputs/eda/` 기본 EDA |
| `scripts/check_online_industries.py` | `outputs/industry_check/` 강남 컴퓨터/소프트웨어·쇼핑몰 점검 |
| `scripts/weather_regression.py` | `outputs/regression/` 업종별 폭염·호우 효과 회귀분석 |
| `scripts/region_profile.py` | `outputs/region_profile/` 강남·춘천 지역 특성 |
| `scripts/group_regression.py` | `outputs/group_regression/` 업종군 효과, 강남 제외 기준 민감도 |
| `scripts/vulnerability_index.py` | `outputs/vulnerability/` 기후 취약도 지수, 예보 기반 지원 우선순위 |
| `scripts/predict_damage.py` | `outputs/prediction/` LightGBM 매출 예측·반사실 피해·경보 분류 |

공통 모듈: `scripts/common.py`(경로·제외 업종·업종군), `scripts/weather_models.py`(회귀 설계·경험적 베이즈 축소).
2차 분석 요약: `outputs/findings_round2.md`.

취약도 지수는 10년 기후 자료가 필요하다: `python -X utf8 scripts/download_weather.py --climatology`

실행 예:

```
uv run --no-project --with pandas --with matplotlib --with tabulate --with statsmodels --with scipy --with lightgbm --with scikit-learn python -X utf8 scripts/<스크립트>.py
```
