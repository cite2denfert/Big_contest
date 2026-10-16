"""춘천 예상 피해 규모 — 하이브리드 모델 (기준 매출 = ML, 강수 피해율 = 회귀).

배경: LightGBM(M2)의 반사실 피해는 비 오는 날이 적어 강수 효과를 약하게 배우고 업종군 간 차이도 거의 못 가린다
      (outputs/chuncheon_model). 그래서 역할을 나눈다.

  기준 매출 B_g,t  : M2(춘천+강남 학습)에 강수 변수를 0으로 넣은 예측 = '비가 안 왔다면 매출'
  피해율 b_g,bin   : 춘천 업종군별 회귀(주 고정효과·요일·공휴일·기온 구간 통제)의 강수 구간 계수
                     (0.1~10 / 10~30 / 30+mm, 호우 다음날)를 0 중심 경험적 베이즈로 축소
  예상 매출        : B_g,t × exp(b_g,bin(t) + b_g,lag1·[전날 30mm+])
  예상 피해        : B_g,t − 예상 매출
  90% 구간         : 축소 계수의 사후분포(정규 근사) 2,000회 표본 — 계수 불확실성만 반영

검증: 시간 순 확장 창. 9·10·11·12월을 차례로 시험하고, 기준 매출 모델과 회귀 피해율 모두 시험 달 이전 자료로만 추정.
  - 피해는 관측되지 않으므로, 관측 가능한 '비 오는 날 매출 예측 정확도'(WAPE·편향)로 검증한다.
  - 실측 부족분 = 기준 매출 − 실제 매출 (기준 매출이 무강수일에 편향이 없을 때 실제 피해의 근사)과 예상 피해 비교.
  - 업종군 순위 일치도: 예상 피해율 vs 실측 부족률(스피어만).
조견표: 전 기간 회귀로 강수 구간별 하루 예상 피해(업종군·도시 합, 90% 구간) — 지원 규모 산정용.

실행: uv run --no-project --with pandas --with matplotlib --with tabulate --with statsmodels --with lightgbm --with scikit-learn python -X utf8 scripts/chuncheon_hybrid.py
"""
import warnings

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from chuncheon_data import BASE_F, CC, CTRL_F, RAIN_F, build_panel, lgbm
from common import INDUSTRY_GROUPS, ROOT
from weather_models import eb_shrink, fit_panel

warnings.filterwarnings("ignore")
OUT = ROOT / "outputs" / "chuncheon_hybrid"
OUT.mkdir(parents=True, exist_ok=True)
RNG = np.random.default_rng(11)
NSIM = 2000
TEST_MONTHS = [9, 10, 11, 12]
RTERMS = ["r_0.1~10", "r_10~30", "r_30+", "r30_lag1"]
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


def rain_rates(panel):
    """춘천 업종군별 강수 계수(0 중심 EB 축소)와 사후 SD. index=(group, 항목)."""
    est = fit_panel(panel, ["MCT_SGG_CD", "group"])
    est = est[est.항목.isin(RTERMS)].copy()
    for _, idx in est.groupby("항목").groups.items():
        b, k = eb_shrink(est.loc[idx, "계수"], est.loc[idx, "표준오차"])
        est.loc[idx, "b_eb"] = b
        est.loc[idx, "sd_post"] = np.sqrt(np.clip(k, 0.05, None)) * est.loc[idx, "표준오차"]
    return est.set_index(["group", "항목"])


def rain_term(r):
    return "r_30+" if r >= 30 else "r_10~30" if r >= 10 else "r_0.1~10" if r > 0 else None


# ---------------------------------------------------------------- 데이터
card, w, x = build_panel()
cc = x.MCT_SGG_CD == CC
wcols = ["MCT_SGG_CD", "date", "tbin", "rbin", "tropical", "r30_lag1"]
# 회귀용 패널은 build_panel의 28일 이력 요건으로 잘린 7월 초도 쓰도록 카드 원자료에서 다시 구성
raw = card[card.MCT_SGG_CD == CC].groupby(["MCT_SGG_CD", "group", "date"]).TS_AT.sum().reset_index()
raw = raw.merge(w[wcols], on=["MCT_SGG_CD", "date"])

bf = BASE_F + ["region_c"]
f1, f2 = bf, bf + RAIN_F + CTRL_F
te_all = []
for m in TEST_MONTHS:
    tr = x.month < m
    te = cc & (x.month == m)
    m1 = lgbm(f1).fit(x.loc[tr, f1], x.loc[tr, "target"])
    m2 = lgbm(f2).fit(x.loc[tr, f2], x.loc[tr, "target"])
    xcf = x.loc[te, f2].copy()
    xcf[RAIN_F] = 0
    o = x.loc[te, ["group", "date", "month", "y", "TS_AT", "rain"]].copy()
    o["M1"] = np.exp(x.loc[te, "roll28"] + m1.predict(x.loc[te, f1]))
    o["M2"] = np.exp(x.loc[te, "roll28"] + m2.predict(x.loc[te, f2]))
    o["base"] = np.exp(x.loc[te, "roll28"] + m2.predict(xcf))
    # 회귀 피해율: 시험 달 이전 춘천 자료만
    tr_raw = raw[raw.date.dt.month < m]
    nd = tr_raw.groupby("group").date.transform("nunique")
    est = rain_rates(tr_raw[nd >= 0.9 * tr_raw.date.nunique()])
    o = o.merge(w[w.MCT_SGG_CD == CC][["date", "r30_lag1"]], on="date", how="left")
    b = np.zeros(len(o))
    draws = np.zeros((NSIM, len(o)))
    for i, (gname, rr, lag) in enumerate(zip(o.group, o.rain, o.r30_lag1)):
        for term in [rain_term(rr), "r30_lag1" if lag == 1 else None]:
            if term and (gname, term) in est.index:
                e = est.loc[(gname, term)]
                b[i] += e.b_eb
                draws[:, i] += RNG.normal(e.b_eb, e.sd_post, NSIM)
    o["H"] = o.base * np.exp(b)
    o["H_M1"] = o.M1 * np.exp(b)  # 민감도: 기준 매출을 M1(기상 제외)로
    o["dmg_H"] = o.base - o.H
    o["dmg_M2"] = o.base - o.M2
    o["short"] = o.base - o.TS_AT  # 실측 부족분
    o["rate_H"] = 1 - np.exp(b)
    te_all.append((o, draws))

O = pd.concat([o for o, _ in te_all], ignore_index=True)
D = np.concatenate([d for _, d in te_all], axis=1)
O.to_csv(OUT / "test_predictions.csv", index=False, encoding="utf-8-sig")

md("# 춘천 예상 피해 규모 — 하이브리드 모델\n")
md("방법은 `scripts/chuncheon_hybrid.py` 상단 주석 참고. 기준 매출 = ML(M2, 강수 0 반사실), "
   "강수 피해율 = 회귀(업종군별, 0 중심 축소). 시험 기간 9~12월, 모든 추정은 시험 달 이전 자료로만.\n")

# ---------------------------------------------------------------- 1. 매출 예측 정확도 (관측 가능한 검증)
MODELS = {"M1 기상 제외": "M1", "M2 강수 포함(ML)": "M2", "하이브리드": "H", "하이브리드(기준=M1)": "H_M1"}
SUB = {"전체": O.rain >= 0, "강수 10mm+": O.rain >= 10, "호우 30mm+": O.rain >= 30, "무강수": O.rain == 0}
rows = []
for lvl in ["업종군×일", "도시 합×일"]:
    for sname, mask in SUB.items():
        s = O[mask]
        if lvl == "도시 합×일":
            s = s.groupby("date")[["TS_AT"] + list(MODELS.values())].sum()
        for mname, col in MODELS.items():
            rows.append({"단위": lvl, "구간": sname, "모델": mname,
                         "WAPE": np.abs(s[col] - s.TS_AT).sum() / s.TS_AT.sum(),
                         "편향": np.log(s.TS_AT / s[col]).mean()})
P = pd.DataFrame(rows)
P.to_csv(OUT / "timecv_performance.csv", index=False, encoding="utf-8-sig")
md("## 1. 비 오는 날 매출 예측 정확도 (시간 순 검증)\n")
md("피해 자체는 관측되지 않으므로, '피해를 반영한 예상 매출'이 실제 매출과 얼마나 맞는지로 검증한다.\n")
for metric, fmt, note in [("WAPE", "{:.1%}", "낮을수록 좋음"),
                          ("편향", "{:+.3f}", "평균 log(실제/예측). 음수 = 과대예측, 즉 피해를 작게 봄")]:
    t = P.pivot_table(index=["단위", "구간"], columns="모델", values=metric, sort=False)[list(MODELS)]
    md(f"**{metric}** ({note})\n")
    md(t.map(fmt.format).to_markdown())
    md()

# ---------------------------------------------------------------- 2. 예상 피해 vs 실측 부족분
city = O.groupby("date").agg(rain=("rain", "first"), base=("base", "sum"), actual=("TS_AT", "sum"),
                             dmg_H=("dmg_H", "sum"), dmg_M2=("dmg_M2", "sum"), short=("short", "sum"))
city_draw = pd.DataFrame((O.base.values * (1 - np.exp(D))).T).groupby(O.date.values).sum().T  # NSIM × 일
dry_bias = np.log(city[city.rain == 0].actual / city[city.rain == 0].base).mean()
# 기준 매출(최근 28일 평균 기반)이 비가 잦은 달에 낮게 잡히는 만큼을 그 달 무강수일 편향으로 보정한 실측 부족분
mon = city.index.month
mbias = {m: np.log(city[(mon == m) & (city.rain == 0)].actual / city[(mon == m) & (city.rain == 0)].base).mean()
         for m in TEST_MONTHS}
city["short_adj"] = city.base * np.exp(np.array([mbias[m] for m in mon])) - city.actual
rows = []
for sname, lo_mm, hi_mm in [("0.1~10mm", 0.1, 10), ("10~30mm", 10, 30), ("30mm+", 30, np.inf), ("10mm+ 합", 10, np.inf)]:
    s = city[(city.rain >= lo_mm) & (city.rain < hi_mm)]
    sims = city_draw[s.index].sum(axis=1).values
    rows.append({"구간": sname, "일수": len(s), "실측 부족분(억)": s.short.sum() / 1e8,
                 "실측 부족분 보정(억)": s.short_adj.sum() / 1e8,
                 "하이브리드(억)": s.dmg_H.sum() / 1e8,
                 "90% 구간": f"{np.percentile(sims, 5) / 1e8:.1f}~{np.percentile(sims, 95) / 1e8:.1f}",
                 "ML(M2)(억)": s.dmg_M2.sum() / 1e8, "하루 평균 하이브리드(억)": s.dmg_H.mean() / 1e8,
                 "실측 부족률": s.short.sum() / s.base.sum(), "하이브리드 피해율": s.dmg_H.sum() / s.base.sum(),
                 "ML 피해율": s.dmg_M2.sum() / s.base.sum()})
L = pd.DataFrame(rows).set_index("구간")
L.to_csv(OUT / "damage_vs_shortfall.csv", encoding="utf-8-sig")
md("## 2. 예상 피해 vs 실측 부족분 (시험 기간 9~12월, 도시 합)\n")
md(f"실측 부족분 = 기준 매출(ML, 강수 0) − 실제 매출. 하루하루는 잡음이 커서 합계로 비교한다. "
   f"무강수일에도 실제 매출이 기준 매출보다 평균 {dry_bias:+.3f}(log) 높다(월별: "
   + ", ".join(f"{m}월 {v:+.3f}" for m, v in mbias.items())
   + "). 기준 수준을 무강수 평일만으로 계산해도 남는 편향으로, 9월 중순~10월(추석 전후·가을 행락철) 매출 상승을 "
   "이전 달로 학습한 모델이 따라가지 못한 몫으로 보인다. '보정'은 이 편향을 월별로 더한 값이다. 편향이 계절 상승 때문이면 "
   "비 온 날에도 그대로 적용되어 보정값이 맞고, 비 갠 날의 보복 소비 때문이면 보정값이 과하다. 실제 피해는 두 값 사이로 본다.\n")
L2 = L.copy()
for c in ["실측 부족률", "하이브리드 피해율", "ML 피해율"]:
    L2[c] = L2[c].map("{:.1%}".format)
md(L2.round(1).to_markdown())
md()

# 업종군 순위 일치도
g10 = O[O.rain >= 10].groupby("group").agg(일수=("date", "nunique"), base=("base", "sum"), short=("short", "sum"),
                                         dmg_H=("dmg_H", "sum"), dmg_M2=("dmg_M2", "sum"))
g10["실측 부족률"] = g10.short / g10.base
g10["하이브리드 피해율"] = g10.dmg_H / g10.base
g10["ML 피해율"] = g10.dmg_M2 / g10.base
g10 = g10.sort_values("실측 부족률", ascending=False)
rho_H = g10[["하이브리드 피해율", "실측 부족률"]].corr(method="spearman").iat[0, 1]
rho_M = g10[["ML 피해율", "실측 부족률"]].corr(method="spearman").iat[0, 1]
g10.to_csv(OUT / "group_damage_rain10.csv", encoding="utf-8-sig")
md("**업종군별 (강수 10mm+ 날)**\n")
gt = g10[["일수", "실측 부족률", "하이브리드 피해율", "ML 피해율"]].copy()
for c in gt.columns[1:]:
    gt[c] = gt[c].map("{:+.1%}".format)
md(gt.to_markdown())
md(f"\n- 업종군 순위 일치도(스피어만, 1 = 완벽): 하이브리드 **{rho_H:.2f}**, ML(M2) {rho_M:.2f}\n")

# ---------------------------------------------------------------- 3. 조견표 (전 기간 회귀)
nd = raw.groupby("group").date.transform("nunique")
est = rain_rates(raw[nd >= 175])
est.reset_index().to_csv(OUT / "rain_rates_full.csv", index=False, encoding="utf-8-sig")
groups = [gname for gname in INDUSTRY_GROUPS if gname in est.index.get_level_values(0)]
rows, city_rows = [], []
for term, lab in [("r_0.1~10", "0.1~10mm"), ("r_10~30", "10~30mm"), ("r_30+", "30mm+"), ("r30_lag1", "호우 다음날")]:
    e = est.xs(term, level="항목").reindex(groups).dropna(subset=["b_eb"])
    sims = RNG.normal(e.b_eb.values, e.sd_post.values, (NSIM, len(e)))
    loss = e.기준일값.values * (1 - np.exp(sims))
    for j, gname in enumerate(e.index):
        rows.append({"group": gname, "구간": lab, "피해율": 1 - np.exp(e.b_eb.iloc[j]),
                     "하루 피해(백만)": e.기준일값.iloc[j] * (1 - np.exp(e.b_eb.iloc[j])) / 1e6,
                     "하한(백만)": np.percentile(loss[:, j], 5) / 1e6, "상한(백만)": np.percentile(loss[:, j], 95) / 1e6})
    tot = loss.sum(axis=1)
    city_rows.append({"구간": lab, "하루 피해(억)": (e.기준일값 * (1 - np.exp(e.b_eb))).sum() / 1e8,
                      "90% 하한": np.percentile(tot, 5) / 1e8, "90% 상한": np.percentile(tot, 95) / 1e8,
                      "평상일 매출 대비": (e.기준일값 * (1 - np.exp(e.b_eb))).sum() / e.기준일값.sum()})
T = pd.DataFrame(rows)
T.to_csv(OUT / "lookup_group.csv", index=False, encoding="utf-8-sig")
TC = pd.DataFrame(city_rows).set_index("구간")
TC.to_csv(OUT / "lookup_city.csv", encoding="utf-8-sig")
md("## 3. 조견표: 강수 예보 구간별 하루 예상 피해 (전 기간 회귀, 평상일 매출 기준)\n")
md("지원 규모 산정용. 신한카드 개인 결제·상권 업종 기준이라 춘천 전체 상권으로 확대하려면 카드사 점유율 보정이 필요하다.\n")
tc = TC.copy()
tc["평상일 매출 대비"] = tc["평상일 매출 대비"].map("{:.1%}".format)
md(tc.round(2).to_markdown())
md()
piv = T.pivot_table(index="group", columns="구간", values="피해율", sort=False)
piv = piv.reindex(columns=["0.1~10mm", "10~30mm", "30mm+", "호우 다음날"])
piv = piv.loc[piv["10~30mm"].sort_values(ascending=False).index]
md("**업종군별 피해율** (양수 = 손실)\n")
md(piv.map("{:+.1%}".format).to_markdown())
md()

# ---------------------------------------------------------------- 그림
fig, axes = plt.subplots(1, 2, figsize=(13, 4.5))
ax = axes[0]
s = P[(P.단위 == "도시 합×일")]
names = ["M1 기상 제외", "M2 강수 포함(ML)", "하이브리드"]
cols = ["#86b6ef", "#1c5cab", "#eb6834"]
xx = np.arange(len(SUB))
for i, (mname, c) in enumerate(zip(names, cols)):
    v = s[s.모델 == mname].set_index("구간").reindex(list(SUB)).WAPE * 100
    ax.bar(xx + (i - 1) * 0.26, v, width=0.25, color=c, label=mname)
    for xi, vi in zip(xx, v):
        ax.text(xi + (i - 1) * 0.26, vi + 0.2, f"{vi:.1f}", ha="center", fontsize=8, color=INK2)
ax.set_xticks(xx, list(SUB))
ax.set_title("도시 합 하루 매출 예측 오차 WAPE (%)", loc="left")
ax.grid(axis="x", visible=False)
ax.legend(loc="upper left")
ax = axes[1]
sub = L.loc[["0.1~10mm", "10~30mm", "30mm+"]]
xx = np.arange(len(sub))
for i, (c_, lab, c) in enumerate([("실측 부족분(억)", "실측 부족분", "#c3c2b7"),
                                  ("실측 부족분 보정(억)", "실측 부족분(편향 보정)", "#898781"),
                                  ("ML(M2)(억)", "ML(M2)", "#1c5cab"), ("하이브리드(억)", "하이브리드", "#eb6834")]):
    ax.bar(xx + (i - 1.5) * 0.2, sub[c_], width=0.19, color=c, label=lab)
    for xi, vi in zip(xx, sub[c_]):
        ax.text(xi + (i - 1.5) * 0.2, vi + 0.8 if vi >= 0 else vi - 0.8, f"{vi:.0f}", ha="center", va="bottom" if vi >= 0 else "top", fontsize=8, color=INK2)
ax.axhline(0, color=INK2, lw=0.8)
ax.set_xticks(xx, [f"{k}\n({int(n)}일)" for k, n in zip(sub.index, sub.일수)])
ax.set_ylabel("억원 (9~12월 합)")
ax.set_title("강수 구간별 피해: 예측 vs 실측 부족분", loc="left")
ax.grid(axis="x", visible=False)
ax.legend(loc="upper left")
fig.tight_layout()
fig.savefig(OUT / "01_hybrid_validation.png")
plt.close(fig)
md("![하이브리드 검증](01_hybrid_validation.png)\n")

(OUT / "summary.md").write_text("\n".join(log), encoding="utf-8")
