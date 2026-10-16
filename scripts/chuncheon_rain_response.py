"""춘천 강수량-매출 반응 곡선, 비의 강도·지속시간·시간대 효과, 타당성 검증.

목적: '빈도'와 무관하게, 하루 단위로 비 피해가 몇 mm부터 시작되고 강수량에 따라 어떻게 커지는지 확인한다.

1) 강수량-반응 곡선 (춘천 상권 전체 일 결제액)
   log(결제액) = 주 고정효과 + 요일 + 공휴일·연휴 + 연말 전야 + 폭염·열대야(통제) + 강수 항
   - 구간: 0.1~5 / 5~10 / 10~20 / 20~30 / 30~50 / 50mm+ (기준 0mm)
   - 곡선: 강수 여부 + log(1+강수)의 구간별 직선(꺾임점 5·15·40mm), 신뢰구간은 델타 방법
   - 강건성: 업종군 패널(업종군·주·업종군×요일 고정효과, 날짜 군집 표준오차)
2) 비의 성격
   - 영업시간(10~21시) 비 vs 영업시간 외 비 (log(1+mm) 각각)
   - 강도·지속: 강수 5mm+ 날을 시간 최대강수(15mm/h+)와 강수 시간(8시간+)으로 구분
   - 6시간대 모형: 시간대별 결제액 ~ 그 시간대 강수 구간 + 같은 날 다른 시간대 강수(통제),
     주·시간대×요일·시간대×공휴일 고정효과, 날짜 군집 표준오차 → 관측 수 3배
3) 타당성 검증
   - 플라시보: '내일의 비'가 오늘 매출에 효과가 없어야 함
   - 순열 검정: 같은 달 안에서 날짜별 강수를 1,000번 무작위로 섞어, 관측된 효과가 우연히 나올 확률 계산

실행: uv run --no-project --with pandas --with matplotlib --with tabulate --with statsmodels python -X utf8 scripts/chuncheon_rain_response.py
"""
import warnings

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import statsmodels.api as sm

from common import GROUP_OF, ROOT, commerce, load_card, load_weather_hourly
from weather_models import EVE, HOL, weather_features

warnings.filterwarnings("ignore")
OUT = ROOT / "outputs" / "chuncheon_rain_response"
OUT.mkdir(parents=True, exist_ok=True)
CC = "강원 춘천시"
RNG = np.random.default_rng(11)
BINS = [0, 5, 10, 20, 30, 50, np.inf]
BIN_LABELS = ["0.1~5", "5~10", "10~20", "20~30", "30~50", "50+"]
KNOTS = [5, 15, 40]
BLUE, ORANGE, INK2, MUTED, GRID = "#2a78d6", "#eb6834", "#52514e", "#898781", "#e1e0d9"
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


def pct(b):
    return np.exp(b) - 1


# ---------------------------------------------------------------- 데이터
card = commerce(load_card(1))
card = card[card.MCT_SGG_CD == CC].assign(group=lambda d: d.MCT_RY_CD.map(GROUP_OF))
w = weather_features()
w = w[w.MCT_SGG_CD == CC].set_index("date")
h = load_weather_hourly()
h = h[h.MCT_SGG_CD == CC].assign(p=lambda d: d.precipitation_reported_mm.fillna(0),
                                 hr=lambda d: pd.to_datetime(d.datetime_kst.str[:19]).dt.hour)
hd = h.groupby("date").agg(hmax=("p", "max"), hours=("p", lambda s: (s > 0).sum()),
                           biz=("p", lambda s: s[h.loc[s.index, "hr"].between(10, 21)].sum()))
w = w.join(hd)
w["off"] = (w.rain - w.biz).clip(lower=0)
w["lead_rain"] = w.rain.shift(-1)
w["lead2_rain"] = w.rain.shift(-2)
daily = card.groupby("date").TS_AT.sum().rename("S").to_frame().join(w, how="inner").dropna(subset=["rain"])


def controls(idx):
    X = pd.DataFrame(index=idx)
    X = X.join(pd.get_dummies(idx.isocalendar().week.astype(str), prefix="wk", drop_first=True).set_index(idx))
    X = X.join(pd.get_dummies(idx.dayofweek.astype(str), prefix="d", drop_first=True).set_index(idx))
    X["hol"] = idx.isin(HOL)
    X["eve"] = idx.isin(EVE)
    X["heat33"] = (daily.loc[idx, "temperature_max_c"] >= 33).values
    X["tropical"] = daily.loc[idx, "tropical"].values
    return X.astype(float)


def rain_bins(r, prefix="r"):
    c = pd.cut(r, BINS, labels=BIN_LABELS, right=False)
    c = c.where(r > 0)  # 0mm는 기준
    return pd.get_dummies(c, prefix=prefix).astype(float)


def spline(r):
    z = np.log1p(r)
    B = pd.DataFrame({"wet": (r > 0).astype(float), "s0": z}, index=r.index)
    for k in KNOTS:
        B[f"s{k}"] = np.clip(z - np.log1p(k), 0, None)
    return B


def ols(y, X, cov="HAC", groups=None):
    X = sm.add_constant(X)
    if cov == "HAC":
        return sm.OLS(y, X).fit(cov_type="HAC", cov_kwds={"maxlags": 7})
    return sm.OLS(y, X).fit(cov_type="cluster", cov_kwds={"groups": groups})


y = np.log(daily.S)
C0 = controls(daily.index)
nday = daily.rain.gt(0).groupby(pd.cut(daily.rain, BINS, labels=BIN_LABELS, right=False)).sum()

md("# 춘천 강수량-매출 반응 곡선과 비의 성격, 타당성 검증\n")
md("방법은 `scripts/chuncheon_rain_response.py` 상단 주석 참고. 대상: 춘천 상권 업종 개인 결제 일 합계.\n")

# ---------------------------------------------------------------- 1. 구간 반응
R1 = ols(y, C0.join(rain_bins(daily.rain)))
rows = []
for lab in BIN_LABELS:
    t = f"r_{lab}"
    b, se = R1.params[t], R1.bse[t]
    rows.append({"구간(mm)": lab, "일수": int(nday[lab]), "변화율": pct(b), "하한": pct(b - 1.96 * se),
                 "상한": pct(b + 1.96 * se), "p": R1.pvalues[t]})
D1 = pd.DataFrame(rows)

# 업종군 패널 (강건성)
gp = card.groupby(["group", "date"]).TS_AT.sum().reset_index()
gp = gp[gp.groupby("group").date.transform("nunique") >= 175].merge(daily[["rain"]], left_on="date",
                                                                       right_index=True)
gidx = pd.DatetimeIndex(gp.date)
# 업종군×요일 더미가 업종군 고정효과를 포함
Xg = pd.get_dummies(gp.group + "_d" + gidx.dayofweek.astype(str), drop_first=True)
Xg = Xg.join(pd.get_dummies(gidx.isocalendar().week.astype(str).values, prefix="wk", drop_first=True).set_axis(Xg.index))
Xg["hol"] = gidx.isin(HOL)
Xg["eve"] = gidx.isin(EVE)
Xg["heat33"] = (daily.loc[gidx, "temperature_max_c"] >= 33).values
Xg["tropical"] = daily.loc[gidx, "tropical"].values
Xg = Xg.astype(float).join(rain_bins(gp.rain.reset_index(drop=True)).set_index(Xg.index))
Rg = ols(np.log(gp.TS_AT.values), Xg, cov="cluster", groups=gp.date.factorize()[0])
D1["패널 변화율"] = [pct(Rg.params[f"r_{lab}"]) for lab in BIN_LABELS]
D1["패널 p"] = [Rg.pvalues[f"r_{lab}"] for lab in BIN_LABELS]
D1.to_csv(OUT / "dose_response_bins.csv", index=False, encoding="utf-8-sig")

md("## 1. 강수량 구간별 하루 매출 변화 (기준: 무강수일)\n")
t = D1.copy()
for c in ["변화율", "하한", "상한", "패널 변화율"]:
    t[c] = t[c].map("{:+.1%}".format)
md(t.round(3).to_markdown(index=False))
md("\n'패널'은 업종군 12개를 한 모형에 넣은 강건성 추정(업종군·주·업종군별 요일 효과 통제, 업종군 평균 효과).\n")

# 곡선
R2 = ols(y, C0.join(spline(daily.rain)))
grid = pd.Series(np.r_[0, np.geomspace(0.1, 100, 200)])
G = spline(grid)
cols = list(G.columns)
b = R2.params[cols].values
V = R2.cov_params().loc[cols, cols].values
fit = G.values @ b
se = np.sqrt(np.einsum("ij,jk,ik->i", G.values, V, G.values))
curve = pd.DataFrame({"mm": grid, "변화율": pct(fit), "하한": pct(fit - 1.96 * se), "상한": pct(fit + 1.96 * se)})
curve.to_csv(OUT / "dose_response_curve.csv", index=False, encoding="utf-8-sig")
at = curve.set_index("mm")
pick = [1, 5, 10, 20, 30, 50, 80]
md("**곡선 추정** (강수 여부 + log(1+mm) 구간 직선, 꺾임점 5·15·40mm):\n")
md(pd.DataFrame({"강수량(mm)": pick, "변화율": [f"{pct(np.interp(np.log1p(m), np.log1p(grid), fit)):+.1%}" for m in pick],
                 "95% 구간": [f"[{pct(np.interp(np.log1p(m), np.log1p(grid), fit - 1.96 * se)):+.1%}, "
                             f"{pct(np.interp(np.log1p(m), np.log1p(grid), fit + 1.96 * se)):+.1%}]" for m in pick]
                 }).to_markdown(index=False))
md()

fig, ax = plt.subplots(figsize=(10, 4.8))
c = curve[curve.mm > 0]
ax.fill_between(c.mm, c.하한 * 100, c.상한 * 100, color=BLUE, alpha=0.15, lw=0, label="곡선 95% 구간")
ax.plot(c.mm, c.변화율 * 100, color=BLUE, lw=2, label="곡선 추정")
mid = [2.5, 7.5, 15, 25, 40, 70]
ax.errorbar(mid, D1.변화율 * 100, yerr=[(D1.변화율 - D1.하한) * 100, (D1.상한 - D1.변화율) * 100], fmt="o",
            color=ORANGE, ms=8, elinewidth=1.4, capsize=0, mec="#fcfcfb", mew=1.5, label="구간 추정 (95% 구간)")
for m, v, n in zip(mid, D1.변화율 * 100, D1.일수):
    ax.annotate(f"{n}일", (m, v), xytext=(6, -12), textcoords="offset points", fontsize=8.5, color=INK2)
ax.axhline(0, color=INK2, lw=1)
ax.axvline(80, color=MUTED, lw=1, ls="--")
ax.text(80, ax.get_ylim()[1] * 0.9 if ax.get_ylim()[1] > 0 else 2, " 일강수 80mm\n (특보 수준 근사)", fontsize=8.5,
        color=INK2, va="top")
ax.set_xscale("log")
ax.set_xticks([0.1, 0.5, 1, 2, 5, 10, 20, 50, 100], ["0.1", "0.5", "1", "2", "5", "10", "20", "50", "100"])
ax.minorticks_off()
ax.set_xlabel("일강수량 (mm, 로그 눈금)")
ax.set_ylabel("하루 결제액 변화 (%)")
ax.set_title("춘천 상권 강수량-매출 반응 (기준: 무강수일)", loc="left")
ax.legend(loc="lower left")
fig.tight_layout()
fig.savefig(OUT / "01_dose_response.png")
plt.close(fig)
md("![반응 곡선](01_dose_response.png)\n")

# ---------------------------------------------------------------- 2. 비의 성격
md("## 2. 비의 성격: 시간대·강도·지속시간\n")
Xb = C0.copy()
Xb["wet"] = (daily.rain > 0).astype(float)
Xb["biz_log"] = np.log1p(daily.biz)
Xb["off_log"] = np.log1p(daily.off)
R3 = ols(y, Xb)
md("**영업시간(10~21시) 비 vs 영업시간 외 비** — log(1+mm) 1 증가(약 2.7배)당 변화:\n")
md(pd.DataFrame([{"항목": n, "변화율": f"{pct(R3.params[k]):+.1%}",
                  "95% 구간": f"[{pct(R3.params[k] - 1.96 * R3.bse[k]):+.1%}, {pct(R3.params[k] + 1.96 * R3.bse[k]):+.1%}]",
                  "p": round(R3.pvalues[k], 3)}
                 for k, n in [("biz_log", "영업시간 강수"), ("off_log", "영업시간 외 강수"), ("wet", "강수 여부")]]
                ).to_markdown(index=False))
md()

Xc = C0.join(rain_bins(daily.rain))
m5 = daily.rain >= 5
Xc["고강도(시간 15mm+)"] = (m5 & (daily.hmax >= 15)).astype(float)
Xc["장시간(8시간+)"] = (m5 & (daily.hours >= 8)).astype(float)
R4 = ols(y, Xc)
n_hi, n_long = int(Xc["고강도(시간 15mm+)"].sum()), int(Xc["장시간(8시간+)"].sum())
md("**같은 강수량 구간 안에서 강도·지속시간의 추가 효과** (강수 5mm+ 날 대상, 강수량 구간 통제):\n")
md(pd.DataFrame([{"항목": k, "해당 일수": n, "추가 변화율": f"{pct(R4.params[k]):+.1%}",
                  "95% 구간": f"[{pct(R4.params[k] - 1.96 * R4.bse[k]):+.1%}, {pct(R4.params[k] + 1.96 * R4.bse[k]):+.1%}]",
                  "p": round(R4.pvalues[k], 3)}
                 for k, n in [("고강도(시간 15mm+)", n_hi), ("장시간(8시간+)", n_long)]]).to_markdown(index=False))
md()

# 6시간대 모형
hb = h.groupby(["date", "TIME_GB"]).p.sum().rename("brain").reset_index()
band = card.groupby(["date", "TIME_GB"]).TS_AT.sum().reset_index().merge(hb, on=["date", "TIME_GB"])
band = band[band.TIME_GB != "00_05"]
band = band.merge(daily[["rain", "temperature_max_c", "tropical"]], left_on="date", right_index=True)
band["other"] = (band.rain - band.brain).clip(lower=0)
bidx = pd.DatetimeIndex(band.date)
BB = [0, 2, 5, 10, np.inf]
BL = ["0.1~2", "2~5", "5~10", "10+"]
band = band.reset_index(drop=True)
Xt = pd.get_dummies(bidx.isocalendar().week.astype(str).values, prefix="wk", drop_first=True)
Xt = Xt.join(pd.get_dummies(band.TIME_GB + "_d" + bidx.dayofweek.astype(str), drop_first=True))
Xt = Xt.join(pd.get_dummies(band.TIME_GB.where(bidx.isin(HOL), "none"), prefix="hol").drop(columns="hol_none"))
Xt["eve"] = bidx.isin(EVE)
Xt["heat33"] = band.temperature_max_c.values >= 33
Xt["tropical"] = band.tropical.values
cb = pd.cut(band.brain, BB, labels=BL, right=False).where(band.brain > 0)
Xt = Xt.join(pd.get_dummies(cb, prefix="b"))
Xt["other_log"] = np.log1p(band.other)
Xt = Xt.astype(float)
R5 = ols(np.log(band.TS_AT.values), Xt, cov="cluster", groups=band.date.factorize()[0])
nb = cb.value_counts()
md(f"**6시간대 모형** (06~11·12~17·18~23시, {len(band):,}개 시간대 관측, 해당 시간대 강수 구간, 기준 0mm):\n")
md(pd.DataFrame([{"시간대 강수(mm/6h)": lab, "관측 수": int(nb.get(lab, 0)), "변화율": f"{pct(R5.params[f'b_{lab}']):+.1%}",
                  "95% 구간": f"[{pct(R5.params[f'b_{lab}'] - 1.96 * R5.bse[f'b_{lab}']):+.1%}, "
                             f"{pct(R5.params[f'b_{lab}'] + 1.96 * R5.bse[f'b_{lab}']):+.1%}]",
                  "p": round(R5.pvalues[f"b_{lab}"], 3)} for lab in BL]
                + [{"시간대 강수(mm/6h)": "같은 날 다른 시간대 강수 log(1+mm)", "관측 수": "-",
                    "변화율": f"{pct(R5.params['other_log']):+.1%}",
                    "95% 구간": f"[{pct(R5.params['other_log'] - 1.96 * R5.bse['other_log']):+.1%}, "
                               f"{pct(R5.params['other_log'] + 1.96 * R5.bse['other_log']):+.1%}]",
                    "p": round(R5.pvalues["other_log"], 3)}]).to_markdown(index=False))
md()

# ---------------------------------------------------------------- 3. 타당성 검증
md("## 3. 타당성 검증\n")
Xp = C0.join(rain_bins(daily.rain)).join(rain_bins(daily.lead_rain.fillna(0), prefix="lead"))
R6 = ols(y, Xp)
md("**플라시보 — 내일의 비가 오늘 매출에 미치는 효과** (0에 가까워야 정상):\n")
md(pd.DataFrame([{"내일 강수 구간": lab, "오늘 매출 변화": f"{pct(R6.params[f'lead_{lab}']):+.1%}",
                  "p": round(R6.pvalues[f"lead_{lab}"], 3),
                  "참고: 오늘 강수 효과": f"{pct(R6.params[f'r_{lab}']):+.1%}"}
                 for lab in BIN_LABELS if f"lead_{lab}" in R6.params]).to_markdown(index=False))
md()
Xq = C0.join(rain_bins(daily.rain))
Xq["내일 10mm+ & 오늘 무강수"] = ((daily.lead_rain >= 10) & (daily.rain == 0)).astype(float)
Xq["내일 10mm+ & 오늘 강수"] = ((daily.lead_rain >= 10) & (daily.rain > 0)).astype(float)
Xq["모레 10mm+ & 오늘·내일 무강수"] = ((daily.lead2_rain >= 10) & (daily.rain == 0) & (daily.lead_rain.fillna(0) == 0)).astype(float)
R7 = ols(y, Xq)
md("**플라시보 세분화** — 오늘 비가 오지 않았는데도 앞으로의 비가 오늘 매출과 관련되는지:\n")
md(pd.DataFrame([{"조건": k, "해당 일수": int(Xq[k].sum()), "오늘 매출 변화": f"{pct(R7.params[k]):+.1%}",
                  "95% 구간": f"[{pct(R7.params[k] - 1.96 * R7.bse[k]):+.1%}, {pct(R7.params[k] + 1.96 * R7.bse[k]):+.1%}]",
                  "p": round(R7.pvalues[k], 3)}
                 for k in ["내일 10mm+ & 오늘 무강수", "내일 10mm+ & 오늘 강수", "모레 10mm+ & 오늘·내일 무강수"]]).to_markdown(index=False))
md()

# 순열 검정: 10mm+ 여부와 0.1~10mm 여부 두 항으로 단순화한 모형의 10mm+ 계수
Xbase = sm.add_constant(C0).values
yv = y.values
month = daily.index.month.values


def coef10(r):
    Z = np.column_stack([Xbase, ((r > 0) & (r < 10)).astype(float), (r >= 10).astype(float)])
    beta, *_ = np.linalg.lstsq(Z, yv, rcond=None)
    return beta[-1]


obs = coef10(daily.rain.values)
perm = np.empty(1000)
for i in range(1000):
    r = daily.rain.values.copy()
    for m in np.unique(month):
        idx = np.where(month == m)[0]
        r[idx] = RNG.permutation(r[idx])
    perm[i] = coef10(r)
p_perm = (np.sum(perm <= obs) + 1) / (len(perm) + 1)
md(f"**순열 검정** — 강수 10mm+ 날의 효과: 관측 {pct(obs):+.1%}, 같은 달 안에서 강수 날짜를 1,000번 섞었을 때 "
   f"이보다 크거나 같은 감소가 나온 비율 **p = {p_perm:.3f}** (무작위 분포 5~95%: {pct(np.percentile(perm, 5)):+.1%} ~ "
   f"{pct(np.percentile(perm, 95)):+.1%})\n")

fig, ax = plt.subplots(figsize=(8, 3.6))
ax.hist(pct(perm) * 100, bins=40, color="#9ec5f4", edgecolor="#fcfcfb")
ax.axvline(pct(obs) * 100, color=ORANGE, lw=2.5)
ax.text(pct(obs) * 100, ax.get_ylim()[1] * 0.9, f" 실제 {pct(obs):+.1%}\n p={p_perm:.3f}", color=INK2, fontsize=9, va="top")
ax.set_xlabel("강수 10mm+ 날의 매출 변화 (%) — 강수 날짜를 무작위로 섞은 1,000회")
ax.set_title("순열 검정: 비 효과가 우연일 가능성", loc="left")
fig.tight_layout()
fig.savefig(OUT / "02_permutation.png")
plt.close(fig)
md("![순열 검정](02_permutation.png)\n")

(OUT / "summary.md").write_text("\n".join(log), encoding="utf-8")
