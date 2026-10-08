"""업종별 폭염·호우 효과 회귀분석.

모형 A (일 단위, 지역 × 업종별 OLS)
    log(결제액_d) = 주 고정효과 + 요일 + 공휴일·연휴 + 연말 전야
                    + 최고기온 구간(30~33 / 33~35 / 35+, 기준 <30)
                    + 일강수 구간(0.1~10 / 10~30 / 30+, 기준 0)
                    + 전날 호우(30mm+)
    - 주 고정효과가 계절·월 추세를 흡수하므로 같은 주 안의 날씨 차이로 효과를 식별
    - 폭염과 호우를 한 모형에 넣어 서로 통제한 뒤 각각 보고
    - 표준오차: HAC(Newey-West, 7일), 업종 간 다중검정은 BH-FDR q값으로 보정

모형 B (시간대 단위, 지역 × 업종별 OLS)
    log(결제액_{d,b}) = 시간대×요일 + 시간대×주 + 공휴일 + 시간대별 [해당 시간대 최고기온 33+]
                        + 시간대별 [해당 시간대 강수 5mm+]
    - 6시간대(00~05/06~11/12~17/18~23)별로 그 시간의 기상을 붙여, 어느 시간대 매출이 영향을 받는지 확인

피해 규모(탐색용): 효과 계수 → 변화율 exp(b)-1, 업종 기준 일매출(평상일 평균) × 변화율 × 해당 일수.

실행: uv run --no-project --with pandas --with matplotlib --with tabulate --with statsmodels python -X utf8 scripts/weather_regression.py
"""
import warnings

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import statsmodels.api as sm
from statsmodels.stats.multitest import multipletests

from common import HOLIDAYS, REGIONS, ROOT, commerce, load_card, load_weather_daily, load_weather_hourly

warnings.filterwarnings("ignore")
OUT = ROOT / "outputs" / "regression"
OUT.mkdir(parents=True, exist_ok=True)

COLOR = {"서울 강남구": "#2a78d6", "강원 춘천시": "#eb6834"}
INK2, MUTED, GRID = "#52514e", "#898781", "#e1e0d9"
NEG, POS = "#e34948", "#2a78d6"
plt.rcParams.update({
    "font.family": "Malgun Gothic", "axes.unicode_minus": False, "savefig.dpi": 150,
    "savefig.bbox": "tight", "axes.facecolor": "#fcfcfb", "figure.facecolor": "#fcfcfb",
    "axes.edgecolor": "#c3c2b7", "xtick.color": MUTED, "ytick.color": MUTED, "axes.grid": True,
    "grid.color": GRID, "grid.linewidth": 0.6, "axes.spines.top": False, "axes.spines.right": False,
    "axes.titlesize": 12, "axes.titleweight": "bold", "legend.frameon": False,
})

# 추석 연휴는 주말(10/4)까지 하나의 연휴로 처리
HOL = HOLIDAYS.union(pd.to_datetime(["2025-10-04"]))
EVE = pd.to_datetime(["2025-12-24", "2025-12-31"])
TEMP_BINS = [-np.inf, 30, 33, 35, np.inf]
TEMP_LABELS = ["<30", "30~33", "33~35", "35+"]
RAIN_BINS = [-np.inf, 0, 10, 30, np.inf]
RAIN_LABELS = ["0", "0.1~10", "10~30", "30+"]
HEAT_TERMS = ["t_30~33", "t_33~35", "t_35+"]
RAIN_TERMS = ["r_0.1~10", "r_10~30", "r_30+", "r30_lag1"]
MIN_DAYS, MIN_SHARE = 175, 0.001  # 업종 포함 기준: 거래일 수, 지역 상권 내 결제액 비중

log = []


def md(text=""):
    print(text)
    log.append(text)


# ---------------------------------------------------------------- 데이터
card = commerce(load_card(1))
wd = load_weather_daily()
wh = load_weather_hourly()

w = wd[["MCT_SGG_CD", "date", "temperature_max_c", "precipitation_reported_mm"]].copy()
w["rain"] = w.precipitation_reported_mm.fillna(0)
w["tbin"] = pd.cut(w.temperature_max_c, TEMP_BINS, labels=TEMP_LABELS, right=False)
w["rbin"] = pd.cut(w.rain, RAIN_BINS, labels=RAIN_LABELS)
w = w.sort_values(["MCT_SGG_CD", "date"])
w["r30_lag1"] = (w.groupby("MCT_SGG_CD").rain.shift(1) >= 30).astype(float)
w = w.dropna(subset=["temperature_max_c"])  # 강남 9/10~11 관측 결측일 제외

daily = card.groupby(["MCT_SGG_CD", "MCT_RY_CD", "date"]).TS_AT.sum().reset_index()
daily = daily.merge(w, on=["MCT_SGG_CD", "date"])
share = daily.groupby(["MCT_SGG_CD", "MCT_RY_CD"]).TS_AT.sum()
share = share / share.groupby(level=0).transform("sum")
ndays = daily.groupby(["MCT_SGG_CD", "MCT_RY_CD"]).date.nunique()
keep = share[(share >= MIN_SHARE) & (ndays >= MIN_DAYS)].index
total = daily.groupby(["MCT_SGG_CD", "date"]).TS_AT.sum().reset_index().merge(w, on=["MCT_SGG_CD", "date"])
total["MCT_RY_CD"] = "전체 상권"


def design_daily(g):
    X = pd.DataFrame(index=g.index)
    X = X.join(pd.get_dummies(g.date.dt.isocalendar().week.astype(str), prefix="wk", drop_first=True))
    X = X.join(pd.get_dummies(g.date.dt.dayofweek.astype(str), prefix="dow", drop_first=True))
    X["holiday"] = g.date.isin(HOL)
    X["eve"] = g.date.isin(EVE)
    for lab in TEMP_LABELS[1:]:
        X[f"t_{lab}"] = g.tbin.eq(lab)
    for lab in RAIN_LABELS[1:]:
        X[f"r_{lab}"] = g.rbin.eq(lab)
    X["r30_lag1"] = g.r30_lag1
    return sm.add_constant(X.astype(float))


def fit(y, X, terms):
    res = sm.OLS(y, X).fit(cov_type="HAC", cov_kwds={"maxlags": 7})
    out = {}
    for t in terms:
        if t in res.params and X[t].sum() > 0:
            out[t] = (res.params[t], res.bse[t], res.pvalues[t], int(X[t].sum()))
    return out, res


# ---------------------------------------------------------------- 모형 A
rows = []
groups = [total.groupby(["MCT_SGG_CD", "MCT_RY_CD"])]
groups.append(daily.set_index(["MCT_SGG_CD", "MCT_RY_CD"]).loc[keep].reset_index().groupby(["MCT_SGG_CD", "MCT_RY_CD"]))
for gb in groups:
    for (r, ind), g in gb:
        g = g.sort_values("date").reset_index(drop=True)
        X = design_daily(g)
        y = np.log(g.TS_AT)
        est, res = fit(y, X, HEAT_TERMS + RAIN_TERMS)
        normal = g.TS_AT[g.tbin.eq("<30") & g.rbin.eq("0") & ~g.date.isin(HOL)].mean()
        for t, (b, se, p, n) in est.items():
            rows.append({"지역": r, "업종": ind, "항목": t, "계수": b, "표준오차": se, "p": p, "일수": n,
                         "변화율": np.exp(b) - 1, "기준일매출(억)": normal / 1e8,
                         "업종비중": share.get((r, ind), 1.0), "R2": res.rsquared})
A = pd.DataFrame(rows)
A["하한"] = np.exp(A.계수 - 1.96 * A.표준오차) - 1
A["상한"] = np.exp(A.계수 + 1.96 * A.표준오차) - 1
A["q"] = np.nan
mask = A.업종 != "전체 상권"
for (r, t), idx in A[mask].groupby(["지역", "항목"]).groups.items():
    A.loc[idx, "q"] = multipletests(A.loc[idx, "p"], method="fdr_bh")[1]
# 기간 누적 영향액 = 기준 일매출 × 변화율 × 해당 일수
A["기간영향(억)"] = A["기준일매출(억)"] * A.변화율 * A.일수
A.to_csv(OUT / "model_A_daily_coefficients.csv", index=False, encoding="utf-8-sig")

md("# 업종별 폭염·호우 효과 회귀분석\n")
md("모형 설명은 `scripts/weather_regression.py` 상단 주석 참고. 변화율은 같은 주·같은 요일 조건에서 "
   "기준일(최고 30℃ 미만·무강수) 대비 결제액 변화.\n")
md(f"- 분석 업종: 강남 {sum(k[0] == '서울 강남구' for k in keep)}개, 춘천 {sum(k[0] == '강원 춘천시' for k in keep)}개 "
   f"(거래일 {MIN_DAYS}일 이상, 지역 상권 결제액 비중 {MIN_SHARE:.1%} 이상)")
md("- 유의성 표기: q<0.05 (업종 간 다중검정 보정 후)\n")

LABEL = {"t_30~33": "최고 30~33℃", "t_33~35": "최고 33~35℃", "t_35+": "최고 35℃+",
         "r_0.1~10": "강수 0.1~10mm", "r_10~30": "강수 10~30mm", "r_30+": "강수 30mm+ (호우일)",
         "r30_lag1": "호우 다음날"}

md("## 1. 전체 상권 효과 (구간별 반응)\n")
tot = A[~mask].copy()
tot["효과"] = tot.apply(lambda s: f"{s.변화율:+.1%} [{s.하한:+.1%}, {s.상한:+.1%}]", axis=1)
tab = tot.pivot(index="항목", columns="지역", values="효과").reindex(HEAT_TERMS + RAIN_TERMS)
tab.index = [LABEL[i] for i in tab.index]
md(tab.to_markdown())
md("\n대괄호는 95% 신뢰구간.\n")

# 강건성: 폭염은 7~8월에만 발생하므로 7~9월 표본만으로 다시 추정
md("**강건성 점검 — 7~9월 표본만 사용** (폭염 계절 안에서만 비교)\n")
rob = []
for r, g in total.groupby("MCT_SGG_CD"):
    g = g[g.date < "2025-10-01"].sort_values("date").reset_index(drop=True)
    est, _ = fit(np.log(g.TS_AT), design_daily(g), HEAT_TERMS + ["r_30+"])
    for t, (b, se, p, n) in est.items():
        rob.append({"지역": r, "항목": LABEL[t], "효과": f"{np.exp(b) - 1:+.1%} "
                    f"[{np.exp(b - 1.96 * se) - 1:+.1%}, {np.exp(b + 1.96 * se) - 1:+.1%}]", "일수": n})
md(pd.DataFrame(rob).pivot(index="항목", columns="지역", values="효과").to_markdown())
md()

fig, axes = plt.subplots(1, 2, figsize=(12, 4.2))
for ax, terms, ref, title in [(axes[0], HEAT_TERMS, "<30℃", "최고기온 구간별 결제액 변화 (기준: 30℃ 미만)"),
                              (axes[1], RAIN_TERMS[:3], "무강수", "일강수 구간별 결제액 변화 (기준: 무강수)")]:
    x = np.arange(len(terms) + 1)
    for i, r in enumerate(REGIONS):
        s = tot[tot.지역 == r].set_index("항목").reindex(terms)
        v = np.r_[0, s.변화율 * 100]
        lo = np.r_[0, s.하한 * 100]
        hi = np.r_[0, s.상한 * 100]
        off = (i - 0.5) * 0.18
        ax.errorbar(x + off, v, yerr=[v - lo, hi - v], fmt="o-", color=COLOR[r], ms=7, lw=2,
                    capsize=0, elinewidth=1.2, label=r, mec="#fcfcfb", mew=1.5)
    ax.axhline(0, color=INK2, lw=1)
    ax.set_xticks(x, [ref] + [LABEL[t].replace("최고 ", "").replace("강수 ", "").replace(" (호우일)", "")
                              for t in terms])
    ax.set_ylabel("결제액 변화 (%)")
    ax.set_title(title, loc="left")
axes[0].legend()
fig.tight_layout()
fig.savefig(OUT / "01_dose_response_total.png")
plt.close(fig)
md("![구간별 반응](01_dose_response_total.png)\n")


def industry_section(term, title, fname, n_side=10):
    md(f"## {title}\n")
    s = A[mask & A.항목.eq(term)].copy()
    fig, axes = plt.subplots(1, 2, figsize=(13, 0.33 * 2 * n_side + 1.5))
    for ax, r in zip(axes, REGIONS):
        g = s[s.지역 == r].sort_values("변화율")
        g = pd.concat([g.head(n_side), g.tail(n_side)]).drop_duplicates("업종")
        y = np.arange(len(g))
        sig = g.q < 0.05
        col = np.where(g.변화율 < 0, NEG, POS)
        ax.hlines(y, g.하한 * 100, g.상한 * 100, color=col, lw=1.4, alpha=0.6)
        ax.scatter(g.변화율 * 100, y, s=np.where(sig, 60, 30), c=np.where(sig, col, "#fcfcfb"),
                   edgecolors=col, linewidths=1.5, zorder=3)
        ax.axvline(0, color=INK2, lw=1)
        ax.set_yticks(y, g.업종)
        ax.grid(axis="y", visible=False)
        ax.set_title(f"{r}", loc="left")
        ax.set_xlabel("결제액 변화 (%), 막대=95% 신뢰구간, 채운 점=q<0.05")
    fig.suptitle(f"{title}: 업종별 결제액 변화 (하위·상위 {n_side})", x=0.01, ha="left", fontweight="bold")
    fig.tight_layout()
    fig.savefig(OUT / fname)
    plt.close(fig)
    md(f"![{title}]({fname})\n")
    for r in REGIONS:
        g = s[s.지역 == r]
        sig = g[g.q < 0.05].sort_values("변화율")
        md(f"**{r}** — 유의한 업종 {len(sig)}개 / {len(g)}개 (해당 일수 {int(g.일수.iloc[0])}일)\n")
        if len(sig):
            t = sig[["업종", "변화율", "하한", "상한", "q", "기준일매출(억)", "기간영향(억)"]].copy()
            for c in ["변화율", "하한", "상한"]:
                t[c] = t[c].map("{:+.1%}".format)
            md(t.round(3).to_markdown(index=False))
        md()


industry_section("t_33~35", "2. 폭염(최고 33~35℃) 효과", "02_heat33_industry.png")
industry_section("t_35+", "3. 극한 폭염(최고 35℃+) 효과", "03_heat35_industry.png")
industry_section("r_30+", "4. 호우(일강수 30mm+) 효과", "04_rain30_industry.png")
industry_section("r30_lag1", "5. 호우 다음날 효과 (소비 이연·회복)", "05_rain_lag_industry.png")

# ---------------------------------------------------------------- 피해 규모 (탐색용)
md("## 6. 기간 누적 영향액 (탐색용)\n")
md("기간영향 = 기준 일매출 × 변화율 × 해당 일수. 신한카드 개인 결제 기준이며, 전체 시장 규모로 환산하지 않은 값.\n")
imp = A[mask & A.항목.isin(["t_33~35", "t_35+", "r_30+", "r30_lag1"])].copy()
imp["유형"] = np.where(imp.항목.str.startswith("t_"), "폭염", "호우")
agg = imp.groupby(["지역", "유형"]).agg(
    유의업종_합계_억=("기간영향(억)", lambda s: s[imp.loc[s.index, "q"] < 0.05].sum()),
    전업종_점추정합_억=("기간영향(억)", "sum")).round(1)
md(agg.to_markdown())
md("\n- **유의업종 합계**(q<0.05)를 1차 수치로 본다. 전업종 점추정합은 비유의 계수까지 더한 값이라 "
   "불확실성이 매우 크다 (특히 강남은 기준 매출이 큰 병원 업종의 노이즈가 지배).")
md("- 호우는 당일(30mm+)과 다음날 효과를 더한 순효과.\n")
imp["유의"] = imp.q < 0.05
net = imp.groupby(["지역", "유형", "업종"]).agg(
    기간영향=("기간영향(억)", "sum"), 유의항목수=("유의", "sum")).reset_index()
net = net.rename(columns={"기간영향": "기간영향(억)"})
net.to_csv(OUT / "impact_by_industry.csv", index=False, encoding="utf-8-sig")
fig, axes = plt.subplots(2, 2, figsize=(13, 9))
for i, hz in enumerate(["폭염", "호우"]):
    for j, r in enumerate(REGIONS):
        ax = axes[i, j]
        g = net[(net.지역 == r) & (net.유형 == hz)].sort_values("기간영향(억)").head(12)[::-1]
        col = np.where(g.유의항목수 > 0, np.where(g["기간영향(억)"] < 0, NEG, POS), "#c3c2b7")
        ax.barh(g.업종, g["기간영향(억)"], color=col, height=0.65)
        ax.axvline(0, color=INK2, lw=1)
        ax.set_title(f"{r} · {hz} 누적 영향 상위 12 (억원)", loc="left")
        ax.grid(axis="y", visible=False)
fig.suptitle("색 막대 = q<0.05 항목 포함 업종, 회색 = 통계적으로 유의하지 않은 점추정",
             x=0.01, ha="left", fontsize=10, color=INK2)
fig.tight_layout()
fig.savefig(OUT / "06_impact_top.png")
plt.close(fig)
md("![누적 영향](06_impact_top.png)\n")

# ---------------------------------------------------------------- 모형 B: 시간대
md("## 7. 시간대별 효과 (모형 B)\n")
md("각 6시간대의 결제액을 같은 시간대의 기상(시간대 내 최고기온 33℃+, 시간대 강수 합 5mm+)과 연결.\n")
wb = wh.groupby(["MCT_SGG_CD", "date", "TIME_GB"]).agg(
    tmax=("temperature_c", "max"), rain=("precipitation_reported_mm", lambda s: s.fillna(0).sum()),
    n=("temperature_c", "count")).reset_index()
wb = wb[wb.n >= 4]
band = card.groupby(["MCT_SGG_CD", "MCT_RY_CD", "date", "TIME_GB"]).TS_AT.sum().reset_index()
band_tot = band.groupby(["MCT_SGG_CD", "date", "TIME_GB"]).TS_AT.sum().reset_index()
band_tot["MCT_RY_CD"] = "전체 상권"
band = band.set_index(["MCT_SGG_CD", "MCT_RY_CD"]).loc[keep].reset_index()
BANDS = ["00_05", "06_11", "12_17", "18_23"]
rowsB = []
for src in (band_tot, band):
    src = src.merge(wb, on=["MCT_SGG_CD", "date", "TIME_GB"])
    # 시간대마다 모형 A와 같은 구조(주·요일·공휴일 통제)로 따로 추정
    for (r, ind, b), g in src.groupby(["MCT_SGG_CD", "MCT_RY_CD", "TIME_GB"]):
        if len(g) < 150:  # 업종별 새벽 시간대처럼 거래가 희박한 경우 제외
            continue
        g = g.sort_values("date").reset_index(drop=True)
        X = pd.DataFrame(index=g.index)
        X = X.join(pd.get_dummies(g.date.dt.isocalendar().week.astype(str), prefix="wk", drop_first=True))
        X = X.join(pd.get_dummies(g.date.dt.dayofweek.astype(str), prefix="dow", drop_first=True))
        X["holiday"] = g.date.isin(HOL)
        X["eve"] = g.date.isin(EVE)
        X["heat"] = g.tmax >= 33
        X["rain"] = g.rain >= 5
        X = sm.add_constant(X.astype(float))
        res = sm.OLS(np.log(g.TS_AT), X).fit(cov_type="HAC", cov_kwds={"maxlags": 7})
        for t, hz in [("heat", "폭염"), ("rain", "호우")]:
            if X[t].sum() >= 3:
                rowsB.append({"지역": r, "업종": ind, "유형": hz, "시간대": b,
                              "변화율": np.exp(res.params[t]) - 1, "p": res.pvalues[t], "관측수": int(X[t].sum()),
                              "하한": np.exp(res.params[t] - 1.96 * res.bse[t]) - 1,
                              "상한": np.exp(res.params[t] + 1.96 * res.bse[t]) - 1})
B = pd.DataFrame(rowsB)
B.to_csv(OUT / "model_B_timeband_coefficients.csv", index=False, encoding="utf-8-sig")
bt = B[B.업종 == "전체 상권"].copy()
bt["효과"] = bt.apply(lambda s: f"{s.변화율:+.1%} [{s.하한:+.1%}, {s.상한:+.1%}] (n={s.관측수})", axis=1)
md(bt.pivot(index=["유형", "시간대"], columns="지역", values="효과").to_markdown())
md()

fig, axes = plt.subplots(1, 2, figsize=(12, 4))
for ax, hz in zip(axes, ["폭염", "호우"]):
    for i, r in enumerate(REGIONS):
        s = bt[(bt.유형 == hz) & (bt.지역 == r)].set_index("시간대").reindex(BANDS)
        x = np.arange(len(BANDS)) + (i - 0.5) * 0.18
        v, lo, hi = s.변화율 * 100, s.하한 * 100, s.상한 * 100
        ax.errorbar(x, v, yerr=[v - lo, hi - v], fmt="o", color=COLOR[r], ms=8, capsize=0,
                    elinewidth=1.4, label=r, mec="#fcfcfb", mew=1.5)
    ax.axhline(0, color=INK2, lw=1)
    ax.set_xticks(range(4), [b.replace("_", "~") + "시" for b in BANDS])
    ax.set_title(f"{hz}: 시간대별 결제액 변화 (%)" + (" — 해당 시간 33℃+" if hz == "폭염" else " — 해당 시간 강수 5mm+"),
                 loc="left")
axes[0].legend()
fig.tight_layout()
fig.savefig(OUT / "07_timeband_total.png")
plt.close(fig)
md("![시간대별](07_timeband_total.png)\n")
md("업종별 시간대 계수 전체: `model_B_timeband_coefficients.csv`\n")

(OUT / "summary.md").write_text("\n".join(log), encoding="utf-8")
print(f"\n저장: {OUT}")
