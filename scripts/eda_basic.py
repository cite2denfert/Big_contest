"""기본 EDA: 카드(신한) · 유동인구(SK) · 기상(기상청) 데이터 구조와 분포 확인.

실행: uv run --no-project --with pandas --with matplotlib python -X utf8 scripts/eda_basic.py
결과: outputs/eda/ 아래 그림(PNG)과 요약표(CSV), summary.md
"""
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
CARD_DIR = ROOT / "2026빅콘테스트_신한카드_데이터_레이아웃"
FLOW_DIR = ROOT / "2026빅콘테스트_sk통신인구_데이터_레이아웃"
WEATHER_DIR = ROOT / "data" / "weather"
OUT = ROOT / "outputs" / "eda"
OUT.mkdir(parents=True, exist_ok=True)

REGIONS = ["서울 강남구", "강원 춘천시"]
COLOR = {"서울 강남구": "#2a78d6", "강원 춘천시": "#eb6834"}
INK, INK2, MUTED, GRID = "#0b0b0b", "#52514e", "#898781", "#e1e0d9"
# 2025-07~12 공휴일(대체공휴일 포함)
HOLIDAYS = pd.to_datetime(["2025-08-15", "2025-10-03", "2025-10-05", "2025-10-06",
                           "2025-10-07", "2025-10-08", "2025-10-09", "2025-12-25"])
# SK 소지역코드 앞 5자리(통계청 시군구 코드)
FLOW_SGG = {"11230": "서울 강남구", "32010": "강원 춘천시"}

plt.rcParams.update({
    "font.family": "Malgun Gothic", "axes.unicode_minus": False,
    "figure.dpi": 110, "savefig.dpi": 150, "savefig.bbox": "tight",
    "axes.facecolor": "#fcfcfb", "figure.facecolor": "#fcfcfb",
    "axes.edgecolor": "#c3c2b7", "axes.labelcolor": INK2, "text.color": INK,
    "xtick.color": MUTED, "ytick.color": MUTED, "axes.grid": True,
    "grid.color": GRID, "grid.linewidth": 0.6, "axes.spines.top": False,
    "axes.spines.right": False, "axes.titlesize": 12, "axes.titleweight": "bold",
    "lines.linewidth": 2, "legend.frameon": False,
})

log = []  # summary.md 본문


def md(text=""):
    print(text)
    log.append(text)


def save(fig, name):
    fig.savefig(OUT / name)
    plt.close(fig)
    md(f"![{name}]({name})")


def eok(x):  # 원 → 억원
    return x / 1e8


# ---------------------------------------------------------------- 로드
card1 = pd.read_csv(CARD_DIR / "신한카드_빅콘테스트2026_데이터1.txt", sep="\t", encoding="cp949",
                    dtype={"TA_YMD": str})
card2 = pd.read_csv(CARD_DIR / "신한카드_빅콘테스트2026_데이터2.txt", sep="\t", encoding="cp949",
                    dtype={"TA_YMD": str})
for d in (card1, card2):
    d["date"] = pd.to_datetime(d["TA_YMD"], format="%Y%m%d")
wd = pd.read_csv(WEATHER_DIR / "weather_daily.csv", encoding="utf-8-sig", dtype={"TA_YMD": str})
wd["date"] = pd.to_datetime(wd["TA_YMD"], format="%Y%m%d")
wd = wd[wd["date"].between("2025-07-01", "2025-12-31")]

md("# 기본 EDA 요약\n")
md("재생성: `uv run --no-project --with pandas --with matplotlib python -X utf8 scripts/eda_basic.py`\n")

# ---------------------------------------------------------------- 1. 카드 데이터 구조·품질
md("## 1. 카드 데이터 구조와 품질\n")
for name, d in [("데이터1 (일×6시간대)", card1), ("데이터2 (일×고객거주지)", card2)]:
    keys = [c for c in d.columns if c not in ("TS_AT", "USE_CNT", "date")]
    md(f"### {name}")
    md(f"- 행 수 {len(d):,} / 기간 {d.date.min():%Y-%m-%d} ~ {d.date.max():%Y-%m-%d} ({d.date.nunique()}일)")
    md(f"- 결측: {d.isna().sum()[d.isna().sum() > 0].to_dict() or '없음'}")
    md(f"- 키 중복 행: {d.duplicated(keys).sum():,}")
    md(f"- 결제건수 최솟값 {d.USE_CNT.min()} → 5건 미만 셀은 비식별 처리로 빠진 것으로 보임")
    md(f"- 업종 수 {d.MCT_RY_CD.nunique()}, 성별 {sorted(d.SEX_CCD.unique())}")
    md(f"- 총 결제액 {eok(d.TS_AT.sum()):,.0f}억원, 총 건수 {d.USE_CNT.sum():,}")
    md()

corp = card1.SEX_CCD.eq("법인")
md(f"- 데이터1의 '법인' 행 비중: 행 {corp.mean():.1%}, 결제액 {card1.TS_AT[corp].sum() / card1.TS_AT.sum():.1%}")
top = card1.nlargest(8, "TS_AT")[["TA_YMD", "TIME_GB", "MCT_SGG_CD", "MCT_RY_CD", "SEX_CCD", "TS_AT", "USE_CNT"]]
top["건당금액(만원)"] = (top.TS_AT / top.USE_CNT / 1e4).round(0)
md("- 결제액 상위 셀(이상치 후보):\n")
md(top.to_markdown(index=False))
md()

# 데이터1(개인) vs 데이터2 총액 비교: 같은 원천인지 확인
c1 = card1[~corp].groupby(["MCT_SGG_CD"]).TS_AT.sum()
c2 = card2.groupby("MCT_SGG_CD").TS_AT.sum()
cmp_ = pd.DataFrame({"데이터1_개인(억)": eok(c1), "데이터2(억)": eok(c2)}).round(0)
cmp_["비율"] = (cmp_["데이터2(억)"] / cmp_["데이터1_개인(억)"]).round(3)
md("- 지역별 총액 비교 (데이터1은 법인 제외):\n")
md(cmp_.to_markdown())
md()

# 개인 결제 + 지역 상권과 무관한 업종(세금·금융·통신·온라인 결제 등) 제외를 분석 기본값으로 사용
from common import NON_COMMERCE  # noqa: E402

nc = card1[~corp].groupby(["MCT_SGG_CD", card1.MCT_RY_CD.isin(NON_COMMERCE)]).TS_AT.sum().unstack()
md(f"- 상권 무관 업종 {len(NON_COMMERCE)}개 제외: {', '.join(NON_COMMERCE)}")
md("- 개인 결제액 중 제외 업종 비중: "
   + ", ".join(f"{r} {nc.loc[r, True] / nc.loc[r].sum():.1%}" for r in REGIONS))
md()
p1 = card1[~corp & ~card1.MCT_RY_CD.isin(NON_COMMERCE)].copy()

# ---------------------------------------------------------------- 2. 일별 추이
md("## 2. 일별 매출 추이\n")
daily = p1.groupby(["MCT_SGG_CD", "date"]).agg(TS_AT=("TS_AT", "sum"), USE_CNT=("USE_CNT", "sum")).reset_index()
daily["dow"] = daily.date.dt.dayofweek
daily["holiday"] = daily.date.isin(HOLIDAYS)

fig, axes = plt.subplots(2, 1, figsize=(11, 6.5), sharex=True)
for ax, r in zip(axes, REGIONS):
    s = daily[daily.MCT_SGG_CD == r]
    ax.plot(s.date, eok(s.TS_AT), color=COLOR[r], lw=1.2, label="일별")
    ax.plot(s.date, eok(s.TS_AT).rolling(7, center=True).mean(), color=INK2, lw=2, label="7일 이동평균")
    h = s[s.holiday]
    ax.scatter(h.date, eok(h.TS_AT), s=36, color="#e34948", zorder=3, label="공휴일",
               edgecolor="#fcfcfb", linewidth=1.5)
    ax.set_title(f"{r} 일별 개인 카드 결제액 (억원)", loc="left")
    ax.set_ylim(bottom=0)
axes[0].legend(loc="lower left", ncol=3)
save(fig, "01_daily_sales.png")

dow = daily[~daily.holiday].groupby(["MCT_SGG_CD", "dow"]).TS_AT.mean().unstack(0)
dow = dow / dow.mean()
dow.index = list("월화수목금토일")
md("\n요일별 평균 결제액 지수 (지역 평균 = 1, 공휴일 제외):\n")
md(dow.round(3).to_markdown())
md()

# ---------------------------------------------------------------- 3. 업종 구성
md("## 3. 업종 구성\n")
ind = p1.groupby(["MCT_SGG_CD", "MCT_RY_CD"]).TS_AT.sum().unstack(0).fillna(0)
share = ind / ind.sum()
share.sort_values("서울 강남구", ascending=False).to_csv(OUT / "industry_share.csv", encoding="utf-8-sig")
fig, axes = plt.subplots(1, 2, figsize=(12, 7))
for ax, r in zip(axes, REGIONS):
    s = share[r].nlargest(20)[::-1]
    ax.barh(s.index, s.values * 100, color=COLOR[r], height=0.7)
    for y, v in enumerate(s.values):
        ax.text(v * 100 + 0.2, y, f"{v:.1%}", va="center", fontsize=8, color=INK2)
    ax.set_title(f"{r} 결제액 상위 20개 업종 (%)", loc="left")
    ax.grid(axis="y", visible=False)
fig.tight_layout()
save(fig, "02_industry_top20.png")
md("\n전체 업종별 비중: `industry_share.csv`\n")

# ---------------------------------------------------------------- 4. 시간대·성별·연령
md("## 4. 시간대 · 성별 · 연령\n")
tb = p1.groupby(["MCT_SGG_CD", "TIME_GB"]).TS_AT.sum().unstack(0)
tb = tb / tb.sum()
age = p1.groupby(["MCT_SGG_CD", "AGE_CCD"]).TS_AT.sum().unstack(0)
age = age / age.sum()
fig, axes = plt.subplots(1, 2, figsize=(12, 4))
x = np.arange(len(tb))
for i, r in enumerate(REGIONS):
    axes[0].bar(x + (i - 0.5) * 0.38, tb[r] * 100, width=0.36, color=COLOR[r], label=r)
    axes[1].bar(np.arange(len(age)) + (i - 0.5) * 0.38, age[r] * 100, width=0.36, color=COLOR[r], label=r)
axes[0].set_xticks(x, [t.replace("_", "~") + "시" for t in tb.index])
axes[0].set_title("시간대별 결제액 비중 (%)", loc="left")
axes[1].set_xticks(np.arange(len(age)), age.index)
axes[1].set_title("연령대별 결제액 비중 (%)", loc="left")
for ax in axes:
    ax.grid(axis="x", visible=False)
axes[0].legend()
fig.tight_layout()
save(fig, "03_time_age.png")
sex = p1.groupby(["MCT_SGG_CD", "SEX_CCD"]).TS_AT.sum().unstack(0)
md("\n성별 결제액 비중:\n")
md((sex / sex.sum()).round(3).to_markdown())
md()

# ---------------------------------------------------------------- 5. 고객 거주지 (데이터2)
md("## 5. 고객 거주지 (데이터2)\n")
res = card2.groupby(["MCT_SGG_CD", card2.CLN_SGG_CD.fillna("미상")]).TS_AT.sum().unstack(0)
res = (res / res.sum()).round(3)
md("가맹점 지역별 고객 거주 시도 상위 6개:\n")
for r in REGIONS:
    md(f"- {r}: " + ", ".join(f"{k} {v:.1%}" for k, v in res[r].nlargest(6).items()))
md()

# ---------------------------------------------------------------- 6. 기상
md("## 6. 기상 현황\n")
wd["heat"] = wd.temperature_max_c >= 33  # 폭염주의보 기준(일최고 33℃)
wd["rain"] = wd.precipitation_reported_mm.fillna(0) >= 10
wd["heavy"] = wd.precipitation_reported_mm.fillna(0) >= 80
fig, axes = plt.subplots(2, 1, figsize=(11, 6.5), sharex=True)
for r in REGIONS:
    s = wd[wd.MCT_SGG_CD == r]
    axes[0].plot(s.date, s.temperature_max_c, color=COLOR[r], lw=1.4, label=r)
    axes[1].plot(s.date, s.precipitation_reported_mm.fillna(0), color=COLOR[r], lw=1.4, label=r)
axes[0].axhline(33, color="#e34948", lw=1, ls="--")
axes[0].text(wd.date.max(), 33.4, "폭염 기준 33℃", ha="right", color=INK2, fontsize=9)
axes[0].set_title("일최고기온 (℃)", loc="left")
axes[1].set_title("일강수량 (mm)", loc="left")
axes[0].legend()
save(fig, "04_weather.png")
wsum = wd.groupby("MCT_SGG_CD").agg(
    폭염일_33=("heat", "sum"), 강수10mm일=("rain", "sum"), 강수80mm일=("heavy", "sum"),
    최고기온=("temperature_max_c", "max"), 최대일강수=("precipitation_reported_mm", "max"),
    결측_최고기온=("temperature_max_c", lambda s: s.isna().sum()))
md(wsum.to_markdown())
md()

# ---------------------------------------------------------------- 7. 매출 × 기상 첫 결합
md("## 7. 매출 × 기상 첫 결합\n")
md("요일·공휴일 효과를 빼기 위해 결제액을 **같은 지역·같은 요일 평균 대비 비율**로 바꾼 뒤 기상과 비교했다.\n")
m = daily.merge(wd[["MCT_SGG_CD", "date", "temperature_max_c", "precipitation_reported_mm", "heat", "rain"]],
                on=["MCT_SGG_CD", "date"], how="left")
miss = m[m.temperature_max_c.isna()]
md(f"- 기상 일자료가 없는 날: {[(r, f'{d:%Y-%m-%d}') for r, d in zip(miss.MCT_SGG_CD, miss.date)]}\n")
m[["heat", "rain"]] = m[["heat", "rain"]].fillna(False).astype(bool)
m["dtype"] = np.where(m.holiday, 7, m.dow)
m["month"] = m.date.dt.month
# 월 추세도 함께 제거 (계절·연말 효과)
base = m.groupby(["MCT_SGG_CD", "dtype"]).TS_AT.transform("mean")
m["idx"] = m.TS_AT / base
m["idx"] = m.idx / m.groupby(["MCT_SGG_CD", "month"]).idx.transform("mean")
m.to_csv(OUT / "daily_sales_weather.csv", index=False, encoding="utf-8-sig")

fig, axes = plt.subplots(1, 2, figsize=(12, 4.3))
for r in REGIONS:
    s = m[m.MCT_SGG_CD == r]
    axes[0].scatter(s.temperature_max_c, s.idx, s=18, color=COLOR[r], alpha=0.75, label=r,
                    edgecolor="#fcfcfb", linewidth=0.6)
    axes[1].scatter(np.log1p(s.precipitation_reported_mm.fillna(0)), s.idx, s=18, color=COLOR[r],
                    alpha=0.75, label=r, edgecolor="#fcfcfb", linewidth=0.6)
axes[0].set_xlabel("일최고기온 (℃)")
axes[1].set_xlabel("log(1 + 일강수량 mm)")
for ax in axes:
    ax.axhline(1, color=MUTED, lw=1)
    ax.set_ylabel("결제액 지수 (요일·월 보정)")
axes[0].set_title("최고기온 vs 결제액 지수", loc="left")
axes[1].set_title("강수량 vs 결제액 지수", loc="left")
axes[0].legend()
fig.tight_layout()
save(fig, "05_sales_vs_weather.png")

rows = []
for r in REGIONS:
    s = m[m.MCT_SGG_CD == r]
    for lab, mask in [("강수 10mm 이상", s.rain), ("폭염(최고 33℃ 이상)", s.heat)]:
        rows.append({"지역": r, "조건": lab, "일수": int(mask.sum()),
                     "해당일 지수": round(s.idx[mask].mean(), 3), "그 외 지수": round(s.idx[~mask].mean(), 3)})
md(pd.DataFrame(rows).to_markdown(index=False))
md()

# 업종별 강수 민감도 맛보기: 업종 일매출 지수(요일·월 보정)의 강수일/비강수일 차이
ind_d = p1.groupby(["MCT_SGG_CD", "MCT_RY_CD", "date"]).TS_AT.sum().reset_index()
ind_d = ind_d.merge(m[["MCT_SGG_CD", "date", "dtype", "month", "rain", "heat"]], on=["MCT_SGG_CD", "date"])
g = ["MCT_SGG_CD", "MCT_RY_CD"]
ind_d["idx"] = ind_d.TS_AT / ind_d.groupby(g + ["dtype"]).TS_AT.transform("mean")
ind_d["idx"] = ind_d.idx / ind_d.groupby(g + ["month"]).idx.transform("mean")
ndays = ind_d.groupby(g).date.transform("nunique")
big = ind_d.groupby(g).TS_AT.transform("sum") / ind_d.groupby("MCT_SGG_CD").TS_AT.transform("sum")
ind_d = ind_d[(ndays >= 170) & (big >= 0.003)]  # 거의 매일 거래가 있고 비중 0.3% 이상인 업종
sens = ind_d.groupby(g).apply(lambda s: pd.Series({
    "강수일 변화율": s.idx[s.rain].mean() / s.idx[~s.rain].mean() - 1,
    "폭염일 변화율": s.idx[s.heat].mean() / s.idx[~s.heat].mean() - 1,
}), include_groups=False).reset_index()
sens.to_csv(OUT / "industry_weather_sensitivity_preview.csv", index=False, encoding="utf-8-sig")

fig, axes = plt.subplots(1, 2, figsize=(12, 7.5))
for ax, r in zip(axes, REGIONS):
    s = sens[sens.MCT_SGG_CD == r].sort_values("강수일 변화율")
    s = pd.concat([s.head(8), s.tail(8)])
    colors = np.where(s["강수일 변화율"] < 0, "#e34948", "#2a78d6")
    ax.barh(s.MCT_RY_CD, s["강수일 변화율"] * 100, color=colors, height=0.7)
    ax.axvline(0, color=INK2, lw=1)
    ax.set_title(f"{r} 강수일(10mm+) 결제액 변화율 (%)\n하위 8 · 상위 8 업종", loc="left")
    ax.grid(axis="y", visible=False)
fig.tight_layout()
save(fig, "06_industry_rain_sensitivity.png")
md("\n업종별 강수·폭염 변화율 전체: `industry_weather_sensitivity_preview.csv` "
   "(단순 평균 비교라 통제 변수 없는 탐색용 수치)\n")

# ---------------------------------------------------------------- 8. 유동인구
md("## 8. 유동인구 (SK)\n")
flow = {}
for kind in ("age", "time", "wkdy"):
    parts = []
    for f in sorted(FLOW_DIR.glob(f"flow_{kind}_pop_*.csv")):
        d = pd.read_csv(f, sep="|", dtype={"BLOCK_CD": str, "STD_YM": str})
        dup = d.duplicated().sum()
        md(f"- {f.name}: {len(d):,}행, 완전 중복 {dup:,}행, 격자 {d.groupby(['X_COORD', 'Y_COORD']).ngroups:,}개")
        parts.append(d.drop_duplicates())
    d = pd.concat(parts)
    d["region"] = d.BLOCK_CD.str[:5].map(FLOW_SGG)
    flow[kind] = d
md(f"\n- 소지역코드 앞 5자리 분포: {flow['age'].BLOCK_CD.str[:5].value_counts().to_dict()}")
md()

ft = flow["time"]
tcols = [f"TMST_{h:02d}" for h in range(24)]
prof = ft.groupby(["region", "STD_YM"])[tcols].sum()
fig, axes = plt.subplots(1, 2, figsize=(12, 4))
for r in REGIONS:
    p = prof.loc[r].mean()
    axes[0].plot(range(24), p / p.sum() * 100, color=COLOR[r], label=r, marker="o", ms=4)
    tot = prof.loc[r].sum(axis=1)  # 월별 '시간대 합' = 일평균 연인원(격자 합)
    axes[1].plot(pd.to_datetime(tot.index, format="%Y%m"), tot / tot.iloc[0], color=COLOR[r],
                 label=r, marker="o", ms=6)
axes[0].set_xticks(range(0, 24, 3))
axes[0].set_xlabel("시")
axes[0].set_title("시간대별 유동인구 비중 (%)", loc="left")
axes[1].set_title("월별 유동인구 지수 (7월 = 1)", loc="left")
axes[1].axhline(1, color=MUTED, lw=1)
axes[0].legend()
fig.tight_layout()
save(fig, "07_flow_time.png")

fa = flow["age"]
acols = [c for c in fa.columns if "FLOW_POP" in c]
ag = fa.groupby("region")[acols].sum()
ag = ag.div(ag.sum(axis=1), axis=0)
md("\n성·연령별 유동인구 비중:\n")
md(ag.T.round(3).to_markdown())
md()

fw = flow["wkdy"]
wcols = [c for c in fw.columns if c.startswith("FLOW_POP_CNT_")]
wk = fw.groupby("region")[wcols].sum()
wk = wk.div(wk.mean(axis=1), axis=0)
wk.columns = list("월화수목금토일")
md("요일별 유동인구 지수 (평균 = 1):\n")
md(wk.round(3).to_markdown())
md()

(OUT / "summary.md").write_text("\n".join(log), encoding="utf-8")
print(f"\n저장: {OUT}")
