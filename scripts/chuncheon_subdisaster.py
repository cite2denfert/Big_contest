"""춘천 '재해 기준에 못 미치는 비'의 매출 손실 비중.

1) 특보 수준 판정: 춘천 ASOS 시간 강수로 날짜별 최대 3시간·12시간 누적 강수를 구해
   기상청 호우주의보(3h 60mm+ 또는 12h 110mm+)·호우경보(3h 90mm+ 또는 12h 180mm+) 기준 도달 여부 판정.
   ※ 실제 특보는 예보 기반·권역 단위로 발효되므로 '관측값 기준 특보 수준'으로 표현한다.
2) 강수일 손실 (두 방법)
   A 회귀: 춘천 업종군별 강수 구간 효과(0.1~10/10~30/30+mm, 호우 다음날; 주 고정효과·요일·공휴일·기온 통제)를
           0 중심 경험적 베이즈로 축소 → 하루 손실 = Σ_업종군 평상일 매출 × (1 − exp(효과)). 사후분포 2,000회로 90% 구간.
   B 예측 모델: 춘천+강남 업종군 LightGBM(주 단위 블록 6겹 교차검증 예측) → 하루 손실 = 강수 변수를 0으로 바꾼 예측 − 실제 강수 예측.
3) 평년(2015~2024) 기대 손실: 일강수 구간별 연평균 일수 × 구간별 하루 손실(A).
   10년 자료는 일 단위라 특보 수준을 '일강수 80mm+'로 근사 (2025년 시간 자료에서 특보 수준은 94.7mm 하루뿐,
   55~71mm 날은 모두 미달이었던 점을 근거로 함).

실행: uv run --no-project --with pandas --with matplotlib --with tabulate --with statsmodels --with lightgbm --with scikit-learn python -X utf8 scripts/chuncheon_subdisaster.py
"""
import warnings

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from chuncheon_data import BASE_F, CC, CTRL_F, RAIN_F, build_panel, lgbm
from common import ROOT, load_climatology, load_weather_hourly
from weather_models import eb_shrink, fit_panel

warnings.filterwarnings("ignore")
OUT = ROOT / "outputs" / "chuncheon_subdisaster"
OUT.mkdir(parents=True, exist_ok=True)
RNG = np.random.default_rng(7)
CAT_ORDER = ["특보 수준", "미달 · 30mm+", "미달 · 10~30mm", "미달 · 0.1~10mm", "호우 다음날"]
SAME_DAY = ["특보 수준", "미달 · 30mm+", "미달 · 10~30mm", "미달 · 0.1~10mm"]  # 비 온 당일
CAT_COLOR = {"특보 수준": "#eb6834", "미달 · 30mm+": "#104281", "미달 · 10~30mm": "#3987e5",
             "미달 · 0.1~10mm": "#9ec5f4", "호우 다음날": "#c3c2b7"}
INK2, MUTED, GRID = "#52514e", "#898781", "#e1e0d9"
plt.rcParams.update({
    "font.family": "Malgun Gothic", "axes.unicode_minus": False, "savefig.dpi": 150,
    "savefig.bbox": "tight", "axes.facecolor": "#fcfcfb", "figure.facecolor": "#fcfcfb",
    "axes.edgecolor": "#c3c2b7", "xtick.color": MUTED, "ytick.color": MUTED, "axes.grid": True,
    "grid.color": GRID, "grid.linewidth": 0.6, "axes.spines.top": False, "axes.spines.right": False,
    "axes.titlesize": 12, "axes.titleweight": "bold", "legend.frameon": False,
})
log = []


def md(text=""):
    print(text)
    log.append(text)


# ---------------------------------------------------------------- 1. 특보 수준 판정
h = load_weather_hourly()
h = h[h.MCT_SGG_CD == CC].copy()
h["t"] = pd.to_datetime(h.datetime_kst.str[:19])
p = h.set_index("t").sort_index().precipitation_reported_mm.fillna(0)
r3, r12 = p.rolling("3h").sum(), p.rolling("12h").sum()
alert = pd.DataFrame({"최대3시간": r3.groupby(r3.index.normalize()).max(),
                      "최대12시간": r12.groupby(r12.index.normalize()).max(),
                      "최대1시간": p.groupby(p.index.normalize()).max()})
alert["주의보수준"] = (alert.최대3시간 >= 60) | (alert.최대12시간 >= 110)
alert["경보수준"] = (alert.최대3시간 >= 90) | (alert.최대12시간 >= 180)

card, w, x = build_panel()
wc = w[w.MCT_SGG_CD == CC].set_index("date")
day = wc[["rain", "r30_lag1"]].join(alert)


def category(r):
    if r.주의보수준:
        return "특보 수준"
    if r.rain >= 30:
        return "미달 · 30mm+"
    if r.rain >= 10:
        return "미달 · 10~30mm"
    if r.rain > 0:
        return "미달 · 0.1~10mm"
    return "호우 다음날" if r.r30_lag1 == 1 else "무강수"


day["구분"] = day.apply(category, axis=1)

md("# 재해 기준에 못 미치는 비의 매출 손실 — 춘천\n")
md("방법은 `scripts/chuncheon_subdisaster.py` 상단 주석 참고.\n")
md("## 1. 특보 수준 판정 (2025-07~12, 춘천 ASOS 시간 강수)\n")
md("기준: 호우주의보 = 3시간 60mm+ 또는 12시간 110mm+, 호우경보 = 3시간 90mm+ 또는 12시간 180mm+\n")
big = day[day.rain >= 10].sort_values("rain", ascending=False)
t = big[["rain", "최대1시간", "최대3시간", "최대12시간", "주의보수준", "경보수준"]].copy()
t.index = t.index.strftime("%m-%d (%a)")
t = t.rename(columns={"rain": "일강수"})
md(f"일강수 10mm+ 날 {len(big)}일 중 주의보 수준 **{int(big.주의보수준.sum())}일**, 경보 수준 {int(big.경보수준.sum())}일\n")
md(t.round(1).to_markdown())
md()
day.to_csv(OUT / "rain_day_alert_level.csv", encoding="utf-8-sig")

# ---------------------------------------------------------------- 2A. 회귀 기반 하루 손실
cg = x[x.MCT_SGG_CD == CC][["MCT_SGG_CD", "group", "date", "TS_AT"]].merge(
    w.drop(columns=["rain_lag1", "rain_lag2"], errors="ignore"), on=["MCT_SGG_CD", "date"])
nd = cg.groupby("group").date.transform("nunique")
cg = cg[nd >= 175]
est = fit_panel(cg, ["MCT_SGG_CD", "group"])
TERM = {"미달 · 0.1~10mm": "r_0.1~10", "미달 · 10~30mm": "r_10~30", "미달 · 30mm+": "r_30+",
        "특보 수준": "r_30+", "호우 다음날": "r30_lag1"}
est = est[est.항목.isin(set(TERM.values()))].copy()
for _, idx in est.groupby("항목").groups.items():
    b, k = eb_shrink(est.loc[idx, "계수"], est.loc[idx, "표준오차"])
    est.loc[idx, "b_eb"] = b
    est.loc[idx, "sd_post"] = np.sqrt(np.clip(k, 0.05, None)) * est.loc[idx, "표준오차"]
est.to_csv(OUT / "group_rain_effects_eb.csv", index=False, encoding="utf-8-sig")
base = est.drop_duplicates("group").set_index("group").기준일값


def day_loss(term, draws=None):
    """해당 조건의 하루 손실(억원, 업종군 합). draws: (n, 업종군) 계수 표본."""
    s = est[est.항목 == term].set_index("group")
    if draws is None:
        return float((base[s.index] * (1 - np.exp(s.b_eb))).sum() / 1e8)
    return (base[s.index].values * (1 - np.exp(draws))).sum(axis=1) / 1e8


sims = {t_: RNG.normal(est[est.항목 == t_].b_eb.values, est[est.항목 == t_].sd_post.values,
                       (2000, (est.항목 == t_).sum())) for t_ in set(TERM.values())}
rain_days = day[day.구분 != "무강수"]
# 호우 다음날이 다른 강수일과 겹치면 두 효과를 모두 더함
rowsA, simA = [], {c: np.zeros(2000) for c in CAT_ORDER}
for dt, r in rain_days.iterrows():
    terms = [(r.구분, TERM[r.구분])] if r.구분 != "호우 다음날" else []
    if r.r30_lag1 == 1:
        terms.append(("호우 다음날", "r30_lag1"))
    for cat, term in terms:
        rowsA.append({"date": dt, "구분": cat, "손실(억)": day_loss(term)})
        simA[cat] += day_loss(term, sims[term])
LA = pd.DataFrame(rowsA)

# ---------------------------------------------------------------- 2B. 예측 모델 기반 하루 손실
x["fold"] = (x.date.dt.isocalendar().week.astype(int) - x.date.dt.isocalendar().week.min()) % 6
bf = BASE_F + ["region_c"]
f2 = bf + RAIN_F + CTRL_F
x["pred"] = np.nan
x["cf"] = np.nan
for k in range(6):
    tr, te = x.fold != k, x.fold == k
    m2 = lgbm(f2).fit(x.loc[tr, f2], x.loc[tr, "target"])
    x.loc[te, "pred"] = x.loc[te, "roll28"] + m2.predict(x.loc[te, f2])
    xcf = x.loc[te, f2].copy()
    xcf[RAIN_F] = 0
    x.loc[te, "cf"] = x.loc[te, "roll28"] + m2.predict(xcf)
mb = x[x.MCT_SGG_CD == CC].assign(loss=lambda d: (np.exp(d.cf) - np.exp(d.pred)) / 1e8)
LB = mb.groupby("date").loss.sum().rename("손실(억)").to_frame().join(day.구분)
LB = LB[LB.구분 != "무강수"]


def summarize(L, label):
    s = L.groupby("구분")["손실(억)"].agg(["count", "sum"]).reindex(CAT_ORDER).fillna(0)
    s.columns = ["일수", "손실합(억)"]
    same_day = s.index.isin(SAME_DAY)
    s["당일 손실 중 비중"] = np.where(same_day, s["손실합(억)"] / s.loc[same_day, "손실합(억)"].sum(), np.nan)
    s.insert(0, "방법", label)
    return s


SA, SB = summarize(LA, "A 회귀"), summarize(LB, "B 예측 모델")
sub_share_A = 1 - SA.loc["특보 수준", "당일 손실 중 비중"]
tot_sim = sum(simA[c] for c in SAME_DAY)
sub_sim = tot_sim - simA["특보 수준"]
lo, hi = np.percentile(sub_sim / tot_sim, [5, 95])
sub_share_B = 1 - SB.loc["특보 수준", "당일 손실 중 비중"]

md("## 2. 2025 하반기 강수 관련 매출 손실, 특보 수준 vs 미달\n")
md("신한카드 개인 결제·상권 업종 기준. '호우 다음날'은 30mm+ 비 다음 날의 추가 효과.\n")
tab = pd.concat([SA, SB]).reset_index().rename(columns={"index": "구분"})
tab["당일 손실 중 비중"] = tab["당일 손실 중 비중"].map(lambda v: "-" if pd.isna(v) else f"{v:.1%}")
md(tab.round(1).to_markdown(index=False))
md(f"\n- **특보 기준에 못 미치는 비의 손실 비중**: A 회귀 **{sub_share_A:.0%}** (90% 구간 {lo:.0%}~{hi:.0%}), "
   f"B 예측 모델 **{sub_share_B:.0%}**")
md("- 비중은 비 온 당일 손실 기준. '호우 다음날'은 별도 효과로, A는 소폭 추가 손실, B는 반등(음수)으로 추정되어 방법 간 차이가 큼.")
md(f"- 당일 손실 총액: A {SA.loc[SAME_DAY, '손실합(억)'].sum():.0f}억 (90% 구간 {np.percentile(tot_sim, 5):.0f}~"
   f"{np.percentile(tot_sim, 95):.0f}억), B {SB['손실합(억)'].sum():.0f}억\n")
pd.concat([SA, SB]).to_csv(OUT / "loss_by_alert_level_2025.csv", encoding="utf-8-sig")

# ---------------------------------------------------------------- 3. 평년 기대 손실
clim = load_climatology()
clim = clim[clim.MCT_SGG_CD == CC]
yrs = clim.date.dt.year.nunique()
r = clim.precipitation_reported_mm
nb = {"특보 수준(일 80mm+ 근사)": (r >= 80).sum() / yrs, "미달 · 30mm+": ((r >= 30) & (r < 80)).sum() / yrs,
      "미달 · 10~30mm": ((r >= 10) & (r < 30)).sum() / yrs, "미달 · 0.1~10mm": ((r > 0) & (r < 10)).sum() / yrs,
      "호우 다음날": (r.shift(1) >= 30).sum() / yrs}
per_day = {"특보 수준(일 80mm+ 근사)": day_loss("r_30+"), "미달 · 30mm+": day_loss("r_30+"),
           "미달 · 10~30mm": day_loss("r_10~30"), "미달 · 0.1~10mm": day_loss("r_0.1~10"),
           "호우 다음날": day_loss("r30_lag1")}
C = pd.DataFrame({"연평균 일수": nb, "하루 손실(억)": per_day})
C["연간 기대 손실(억)"] = C["연평균 일수"] * C["하루 손실(억)"]
sd = C.index != "호우 다음날"
C["당일 손실 중 비중"] = np.where(sd, C["연간 기대 손실(억)"] / C.loc[sd, "연간 기대 손실(억)"].sum(), np.nan)
md(f"## 3. 평년(2015~2024) 기준 연간 기대 손실 — 회귀(A)\n")
md("30mm+ 구간은 특보 수준과 미달의 하루 손실률을 같게 둔 가정 (특보 수준 사례가 1일뿐이라 따로 추정 불가).\n")
C2 = C.copy()
C2["당일 손실 중 비중"] = C2["당일 손실 중 비중"].map(lambda v: "-" if pd.isna(v) else f"{v:.1%}")
md(C2.round(2).to_markdown())
sub_clim = 1 - C.loc["특보 수준(일 80mm+ 근사)", "당일 손실 중 비중"]
tot_clim = C.loc[sd, "연간 기대 손실(억)"].sum()
md(f"\n- 평년 기준으로도 손실의 **{sub_clim:.0%}**가 특보 수준에 못 미치는 비에서 발생 "
   f"(비 온 당일 연간 기대 손실 {tot_clim:.0f}억 중 {tot_clim * sub_clim:.0f}억)\n")
C.to_csv(OUT / "expected_annual_loss_by_bin.csv", encoding="utf-8-sig")

md("## 4. 업종군별 하루 손실률 (축소 후, A)\n")
g = est.pivot(index="group", columns="항목", values="b_eb")
g = (1 - np.exp(g))[["r_0.1~10", "r_10~30", "r_30+", "r30_lag1"]].sort_values("r_10~30", ascending=False)
g.columns = ["0.1~10mm", "10~30mm", "30mm+", "호우 다음날"]
md(g.map("{:+.1%}".format).to_markdown())
md("\n양수 = 손실, 음수 = 증가.\n")

# ---------------------------------------------------------------- 그림
fig, axes = plt.subplots(1, 2, figsize=(13, 5.2), gridspec_kw={"width_ratios": [2.2, 1]})
ax = axes[0]
ld = LA.groupby(["date", "구분"])["손실(억)"].sum().unstack().reindex(columns=CAT_ORDER).fillna(0)
ld = ld[ld.sum(axis=1).abs() > 0]
bottom = np.zeros(len(ld))
for c in CAT_ORDER:
    v = ld[c].values
    ax.bar(ld.index, v, bottom=bottom, width=0.85, color=CAT_COLOR[c], label=c)
    bottom += v
ax.axhline(0, color=INK2, lw=1)
ax.set_ylabel("하루 손실 (억원)")
ax.set_title("춘천 강수 관련 하루 매출 손실 (회귀 A, 2025-07~12)", loc="left")
ax.legend(loc="upper right", ncol=2, fontsize=9)
ax = axes[1]
labels = ["A 회귀", "B 예측 모델", "평년 기대 (A)"]
col = "당일 손실 중 비중"
shares = [SA[col].reindex(SAME_DAY).values, SB[col].reindex(SAME_DAY).values,
          C[col].rename(index={"특보 수준(일 80mm+ 근사)": "특보 수준"}).reindex(SAME_DAY).values]
left = np.zeros(3)
for i, c in enumerate(SAME_DAY):
    v = np.array([s[i] for s in shares]) * 100
    ax.barh(labels, v, left=left, color=CAT_COLOR[c], height=0.55, edgecolor="#fcfcfb", linewidth=2)
    left += v
for yi, s in enumerate(shares):
    ax.text(101, yi, f"미달 {100 - s[0] * 100:.0f}%", va="center", fontsize=10, color=INK2, fontweight="bold")
ax.set_xlim(0, 125)
ax.invert_yaxis()
ax.set_xlabel("손실 비중 (%)")
ax.set_title("비 온 당일 손실 중 특보 수준 vs 미달", loc="left")
ax.grid(axis="y", visible=False)
fig.tight_layout()
fig.savefig(OUT / "01_subdisaster_loss.png")
plt.close(fig)
md("![특보 미달 손실](01_subdisaster_loss.png)\n")

(OUT / "summary.md").write_text("\n".join(log), encoding="utf-8")
