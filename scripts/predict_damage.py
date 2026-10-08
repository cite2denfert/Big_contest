"""기상 기반 상권 매출 예측·피해 추정·피해 경보 분류 모델.

단위: 지역 × 업종(116개) 일별 결제액, 비교용으로 지역 × 업종군(26개)
목표: log(결제액) - 최근 28일 평균 log(결제액)   → 예측값 = 최근 수준 + 예측 편차 (1일 앞 예측)

모델
  M0 기준선: 지난주 같은 요일 값
  M1 LightGBM: 달력 + 최근 매출 이력 + 업종·지역 (기상 제외)
  M2 LightGBM: M1 + 기상
     기상 변수는 계절을 대신 학습하지 않도록 '사건·편차' 형태로 구성:
     최고기온 편차(최근 14일 평균 대비), 폭염(33℃+)·극한폭염(35℃+) 여부, 폭염 연속일수, 열대야,
     일강수, 시간 최대강수, 전날 강수. 일강수·시간 최대강수에는 '많을수록 매출이 늘지 않는다'는 단조 제약.
평가
  주 교차검증(주 단위 블록을 6겹에 번갈아 배정, 시험 주가 전 기간에 고르게 분포) — 주 평가
  월 교차검증(한 달씩 시험) — 계절 외삽이 필요한 엄격한 평가
  지표: WAPE(결제액 기준 절대오차 합/실제 합). 전체·호우일(30mm+)·강수 10mm+·폭염일(33℃+)로 나눠 비교.
피해 추정: M2로 '실제 날씨' 예측과 '평상 날씨(폭염·강수·열대야 없음)' 예측의 차이 (반사실 추정)
경보 분류: '기상 외 요인 예상치(M1) 대비 10% 이상 감소'를 예보 기상으로 분류. AUC·PR-AUC.

실행: uv run --no-project --with pandas --with matplotlib --with tabulate --with statsmodels --with lightgbm --with scikit-learn python -X utf8 scripts/predict_damage.py
"""
import warnings

import lightgbm as lgb
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score, roc_auc_score

from common import GROUP_OF, REGIONS, ROOT, commerce, load_card, load_weather_hourly
from weather_models import EVE, HOL, weather_features

warnings.filterwarnings("ignore")
OUT = ROOT / "outputs" / "prediction"
OUT.mkdir(parents=True, exist_ok=True)
COLOR = {"서울 강남구": "#2a78d6", "강원 춘천시": "#eb6834"}
MODELS = ["M0 지난주 같은 요일", "M1 기상 제외", "M2 기상 포함"]
MCOLOR = dict(zip(MODELS, ["#c3c2b7", "#86b6ef", "#1c5cab"]))
INK2, MUTED, GRID = "#52514e", "#898781", "#e1e0d9"
plt.rcParams.update({
    "font.family": "Malgun Gothic", "axes.unicode_minus": False, "savefig.dpi": 150,
    "savefig.bbox": "tight", "axes.facecolor": "#fcfcfb", "figure.facecolor": "#fcfcfb",
    "axes.edgecolor": "#c3c2b7", "xtick.color": MUTED, "ytick.color": MUTED, "axes.grid": True,
    "grid.color": GRID, "grid.linewidth": 0.6, "axes.spines.top": False, "axes.spines.right": False,
    "axes.titlesize": 12, "axes.titleweight": "bold", "legend.frameon": False,
})
PARAMS = dict(n_estimators=500, learning_rate=0.03, num_leaves=15, min_child_samples=80, subsample=0.8,
              subsample_freq=1, colsample_bytree=0.8, reg_lambda=3.0, random_state=0, verbose=-1)
BASE_F = ["dow", "holiday", "eve", "dom", "lag7_rel", "lag14_rel", "roll7_rel", "region_c", "unit_c", "group_c"]
WX_F = ["tmax_anom", "heat33", "heat35", "heat_run", "tropical", "rain", "rain_hmax", "rain_lag1"]
MONO = {"rain": -1, "rain_hmax": -1}
NORMAL = {"tmax_anom": lambda s: s.clip(upper=0), "heat33": 0, "heat35": 0, "heat_run": 0, "tropical": 0,
          "rain": 0, "rain_hmax": 0, "rain_lag1": 0}
log = []


def md(text=""):
    print(text)
    log.append(text)


# ---------------------------------------------------------------- 데이터
card = commerce(load_card(1)).assign(group=lambda x: x.MCT_RY_CD.map(GROUP_OF))
w = weather_features()
wh = load_weather_hourly()
w = w.merge(wh.groupby(["MCT_SGG_CD", "date"]).precipitation_reported_mm.max().rename("rain_hmax").reset_index(),
            on=["MCT_SGG_CD", "date"], how="left")
w["tmax_anom"] = w.temperature_max_c - w.groupby("MCT_SGG_CD").temperature_max_c.transform(
    lambda s: s.shift(1).rolling(14, min_periods=5).mean())
w["heat33"] = (w.temperature_max_c >= 33).astype(int)
w["heat35"] = (w.temperature_max_c >= 35).astype(int)
w["heat_run"] = w.groupby("MCT_SGG_CD").heat33.transform(
    lambda h: h.groupby((h != h.shift()).cumsum()).cumsum() * h)
w["rain_lag1"] = w.groupby("MCT_SGG_CD").rain.shift(1)


def build(level):
    """level: 'MCT_RY_CD'(업종) 또는 'group'(업종군)."""
    x = card.groupby(["MCT_SGG_CD", level, "date"]).TS_AT.sum().reset_index().rename(columns={level: "unit"})
    nd = x.groupby(["MCT_SGG_CD", "unit"]).date.transform("nunique")
    sh = x.groupby(["MCT_SGG_CD", "unit"]).TS_AT.transform("sum") / x.groupby("MCT_SGG_CD").TS_AT.transform("sum")
    x = x[(nd >= 175) & (sh >= 0.001)]
    units = x[["MCT_SGG_CD", "unit"]].drop_duplicates()
    grid = units.merge(pd.DataFrame({"date": pd.date_range("2025-07-01", "2025-12-31")}), how="cross")
    x = grid.merge(x, how="left", on=["MCT_SGG_CD", "unit", "date"]).sort_values(["MCT_SGG_CD", "unit", "date"])
    x["y"] = np.log(x.TS_AT)
    g = x.groupby(["MCT_SGG_CD", "unit"]).y
    x["roll28"] = g.transform(lambda s: s.shift(1).rolling(28, min_periods=7).mean())
    x["lag7_rel"] = g.shift(7) - x.roll28
    x["lag14_rel"] = g.shift(14) - x.roll28
    x["roll7_rel"] = g.transform(lambda s: s.shift(1).rolling(7, min_periods=4).mean()) - x.roll28
    x["target"] = x.y - x.roll28
    x = x.merge(w[["MCT_SGG_CD", "date", "temperature_max_c"] + WX_F], on=["MCT_SGG_CD", "date"], how="left")
    x["dow"] = x.date.dt.dayofweek
    x["holiday"] = x.date.isin(HOL).astype(int)
    x["eve"] = x.date.isin(EVE).astype(int)
    x["dom"] = x.date.dt.day
    x["group"] = x.unit.map(GROUP_OF).fillna(x.unit)
    x["region_c"] = x.MCT_SGG_CD.astype("category")
    x["unit_c"] = x.unit.astype("category")
    x["group_c"] = x.group.astype("category")
    x = x.dropna(subset=["target", "roll28", "temperature_max_c", "tmax_anom"]).reset_index(drop=True)
    wk = x.date.dt.isocalendar().week.astype(int)
    x["fold_week"] = (wk - wk.min()) % 6
    x["fold_month"] = x.date.dt.month
    return x, len(units)


def lgbm(feats, **kw):
    mono = [MONO.get(f, 0) for f in feats]
    return lgb.LGBMRegressor(**{**PARAMS, **kw}, monotone_constraints=mono)


def run_cv(x, fold_col):
    oof = x[["MCT_SGG_CD", "unit", "group", "date", "y", "roll28", "rain", "temperature_max_c", "tropical",
             "TS_AT"]].copy()
    oof["M0 지난주 같은 요일"] = x.roll28 + x.lag7_rel.fillna(0)
    for k in sorted(x[fold_col].unique()):
        tr, te = x[fold_col] != k, x[fold_col] == k
        m1 = lgbm(BASE_F).fit(x.loc[tr, BASE_F], x.loc[tr, "target"])
        oof.loc[te, "M1 기상 제외"] = x.loc[te, "roll28"] + m1.predict(x.loc[te, BASE_F])
        f2 = BASE_F + WX_F
        m2 = lgbm(f2).fit(x.loc[tr, f2], x.loc[tr, "target"])
        oof.loc[te, "M2 기상 포함"] = x.loc[te, "roll28"] + m2.predict(x.loc[te, f2])
        xcf = x.loc[te, f2].copy()
        for c, v in NORMAL.items():
            xcf[c] = v(xcf[c]) if callable(v) else v
        oof.loc[te, "cf"] = x.loc[te, "roll28"] + m2.predict(xcf)
    return oof


SUBSETS = {"전체": lambda o: o.rain >= 0, "호우일(30mm+)": lambda o: o.rain >= 30,
           "강수 10mm+": lambda o: o.rain >= 10, "폭염일(33℃+)": lambda o: o.temperature_max_c >= 33}


def perf(oof, tag):
    rows = []
    for r in REGIONS + ["전체"]:
        sr = oof if r == "전체" else oof[oof.MCT_SGG_CD == r]
        for sname, f in SUBSETS.items():
            s = sr[f(sr)]
            for mname in MODELS:
                rows.append({"설정": tag, "지역": r, "구간": sname, "모델": mname, "n": len(s),
                             "WAPE": np.abs(np.exp(s[mname]) - s.TS_AT).sum() / s.TS_AT.sum()})
    return pd.DataFrame(rows)


md("# 기상 기반 매출 예측 · 피해 추정 · 피해 경보 모델\n")
md("방법은 `scripts/predict_damage.py` 상단 주석 참고.\n")

results, oofs, data = [], {}, {}
for level, lname in [("MCT_RY_CD", "업종"), ("group", "업종군")]:
    x, nunit = build(level)
    data[lname] = x
    md(f"- {lname} 단위: {nunit}개 지역×{lname}, {len(x):,}행")
    for fold_col, cname in [("fold_week", "주 CV"), ("fold_month", "월 CV")]:
        oof = run_cv(x, fold_col)
        oofs[(lname, cname)] = oof
        results.append(perf(oof, f"{lname}·{cname}"))
P = pd.concat(results)
P.to_csv(OUT / "cv_performance.csv", index=False, encoding="utf-8-sig")

md("\n## 1. 예측 성능 (WAPE, 낮을수록 좋음)\n")
tab = P[P.지역 == "전체"].pivot_table(index=["설정", "구간"], columns="모델", values="WAPE", sort=False)[MODELS]
tab["M2−M1 (%p)"] = (tab["M2 기상 포함"] - tab["M1 기상 제외"]) * 100
fmt = tab.copy().astype(object)
for c in MODELS:
    fmt[c] = tab[c].map("{:.1%}".format)
fmt["M2−M1 (%p)"] = tab["M2−M1 (%p)"].map("{:+.2f}".format)
md("두 지역 합산. M2−M1이 음수면 기상 변수가 오차를 줄인 것.\n")
md(fmt.to_markdown())
md()
reg = P[(P.설정 == "업종·주 CV") & (P.지역 != "전체")].pivot_table(
    index=["지역", "구간"], columns="모델", values="WAPE", sort=False)[MODELS]
reg["M2−M1 (%p)"] = (reg["M2 기상 포함"] - reg["M1 기상 제외"]) * 100
fmt = reg.copy().astype(object)
for c in MODELS:
    fmt[c] = reg[c].map("{:.1%}".format)
fmt["M2−M1 (%p)"] = reg["M2−M1 (%p)"].map("{:+.2f}".format)
md("지역별 (업종 단위 · 주 CV):\n")
md(fmt.to_markdown())
md()

fig, axes = plt.subplots(1, 2, figsize=(13, 4.3), sharey=True)
for ax, r in zip(axes, REGIONS):
    s = P[(P.설정 == "업종·주 CV") & (P.지역 == r)]
    xx = np.arange(len(SUBSETS))
    for i, mname in enumerate(MODELS):
        v = s[s.모델 == mname].set_index("구간").reindex(list(SUBSETS)).WAPE * 100
        ax.bar(xx + (i - 1) * 0.26, v, width=0.24, color=MCOLOR[mname], label=mname)
        for xi, vi in zip(xx, v):
            ax.text(xi + (i - 1) * 0.26, vi + 0.3, f"{vi:.1f}", ha="center", fontsize=7.5, color=INK2)
    ax.set_xticks(xx, list(SUBSETS))
    ax.set_title(f"{r} 예측 오차 WAPE (%) — 업종 단위, 주 CV", loc="left")
    ax.grid(axis="x", visible=False)
axes[0].set_ylim(0, 33)
fig.tight_layout(rect=(0, 0.07, 1, 1))
h, l = axes[0].get_legend_handles_labels()
fig.legend(h, l, loc="lower center", ncol=3)
fig.savefig(OUT / "01_cv_wape.png")
plt.close(fig)
md("![예측 성능](01_cv_wape.png)\n")

# ---------------------------------------------------------------- 반사실 피해 추정
oof = oofs[("업종", "주 CV")]
md("## 2. 반사실 피해 추정 (업종 단위 M2, 주 CV 예측: 실제 날씨 − 평상 날씨)\n")
oof["손실(억)"] = (np.exp(oof.cf) - np.exp(oof["M2 기상 포함"])) / 1e8
oof["손실률"] = 1 - np.exp(oof["M2 기상 포함"] - oof.cf)
EV = {"호우일(30mm+)": lambda o: o.rain >= 30, "강수 10~30mm": lambda o: (o.rain >= 10) & (o.rain < 30),
      "폭염일(33℃+)": lambda o: o.temperature_max_c >= 33, "열대야": lambda o: o.tropical == 1}
rows = []
for r in REGIONS:
    sr = oof[oof.MCT_SGG_CD == r]
    for name, f in EV.items():
        s = sr[f(sr)]
        if s.empty:
            continue
        day = s.groupby("date").agg(loss=("손실(억)", "sum"), base=("cf", lambda v: np.exp(v).sum() / 1e8))
        rows.append({"지역": r, "조건": name, "발생일수": len(day), "1일 평균 손실(억)": day.loss.mean(),
                     "1일 평균 손실률": (day.loss / day.base).mean(), "기간 합계 손실(억)": day.loss.sum()})
C = pd.DataFrame(rows)
C.to_csv(OUT / "counterfactual_loss.csv", index=False, encoding="utf-8-sig")
C2 = C.copy()
C2["1일 평균 손실률"] = C2["1일 평균 손실률"].map("{:+.1%}".format)
md(C2.round(2).to_markdown(index=False))
md("\n손실(+)은 평상 날씨였다면 더 많았을 매출. 조건이 겹치는 날(예: 폭염+열대야)은 각 행에 중복 집계됨.\n")

vul = pd.read_csv(ROOT / "outputs" / "vulnerability" / "vulnerability_group.csv", encoding="utf-8-sig")
grp = oof[oof.rain >= 30].groupby(["MCT_SGG_CD", "group"]).agg(ML_손실억=("손실(억)", "sum")).reset_index()
cmp_ = grp.merge(vul.rename(columns={"지역": "MCT_SGG_CD", "단위": "group"})[
    ["MCT_SGG_CD", "group", "호우_2025실제(억)"]], on=["MCT_SGG_CD", "group"], how="left")
cmp_.to_csv(OUT / "counterfactual_vs_regression_rain.csv", index=False, encoding="utf-8-sig")
md("**두 방법 비교 — 2025 하반기 호우 손실 (업종군별)**: ML 반사실(호우 30mm+ 당일) vs 회귀 기반 취약도 지수"
   "(`호우_2025실제`, 30mm+ 당일·10~30mm·다음날 포함)\n")
for r in REGIONS:
    s = cmp_[cmp_.MCT_SGG_CD == r]
    rho = s[["ML_손실억", "호우_2025실제(억)"]].corr(method="spearman").iat[0, 1]
    md(f"- {r}: 업종군 순위 스피어만 상관 {rho:.2f} | ML 합계 {s.ML_손실억.sum():.0f}억, "
       f"회귀 합계 {s['호우_2025실제(억)'].sum():.0f}억")
md()

fig, axes = plt.subplots(2, 1, figsize=(12, 7), sharex=True)
for ax, r in zip(axes, REGIONS):
    s = oof[(oof.MCT_SGG_CD == r) & (oof.date < "2025-10-01")].groupby("date").agg(
        실제=("TS_AT", "sum"), 예측=("M2 기상 포함", lambda v: np.exp(v).sum()), 평상=("cf", lambda v: np.exp(v).sum()),
        rain=("rain", "first"))
    for dt in s.index[s.rain >= 30]:
        ax.axvspan(dt - pd.Timedelta(hours=12), dt + pd.Timedelta(hours=12), color="#cde2fb", lw=0)
    ax.plot(s.index, s.실제 / 1e8, color=MUTED, lw=1.2, label="실제")
    ax.plot(s.index, s.평상 / 1e8, color=INK2, lw=1.4, ls="--", label="예측: 평상 날씨")
    ax.plot(s.index, s.예측 / 1e8, color=COLOR[r], lw=2, label="예측: 실제 날씨 (M2)")
    ax.set_title(f"{r} 일별 상권 결제액 (억원) — 음영 = 호우일(30mm+), 7~9월", loc="left")
axes[0].legend(loc="lower left", ncol=3)
fig.tight_layout()
fig.savefig(OUT / "02_counterfactual_timeseries.png")
plt.close(fig)
md("![반사실 추이](02_counterfactual_timeseries.png)\n")

# ---------------------------------------------------------------- 피해 경보 분류
md("## 3. 피해 경보 분류 모델 (업종 단위, 주 CV)\n")
md("라벨: 실제 결제액이 기상 외 요인 예상치(M1, 교차검증 예측) 대비 10% 이상 낮은 날 = 1. "
   "입력: 예보로 알 수 있는 기상 + 달력 + 업종·지역.\n")
x = data["업종"]
x["label"] = ((oof.y - oof["M1 기상 제외"]) <= np.log(0.9)).astype(int)
CF = ["dow", "holiday", "eve", "region_c", "unit_c", "group_c"]
prob = pd.DataFrame(index=x.index, columns=["기상 제외", "기상 포함"], dtype=float)
for k in sorted(x.fold_week.unique()):
    tr, te = x.fold_week != k, x.fold_week == k
    for name, feats in [("기상 제외", CF), ("기상 포함", CF + WX_F)]:
        clf = lgb.LGBMClassifier(**{**PARAMS, "n_estimators": 300}).fit(x.loc[tr, feats], x.loc[tr, "label"])
        prob.loc[te, name] = clf.predict_proba(x.loc[te, feats])[:, 1]
rows = []
for r in REGIONS + ["전체"]:
    for sname, f in {"전체": lambda o: o.rain >= 0, "강수 10mm+": lambda o: o.rain >= 10,
                     "폭염일(33℃+)": lambda o: o.temperature_max_c >= 33}.items():
        idx = ((x.MCT_SGG_CD == r) if r != "전체" else (x.rain >= 0)) & f(x)
        yv = x.label[idx]
        row = {"지역": r, "구간": sname, "표본": int(idx.sum()), "양성비율": yv.mean()}
        for name in prob.columns:
            row[f"AUC {name}"] = roc_auc_score(yv, prob[name][idx])
            row[f"PR-AUC {name}"] = average_precision_score(yv, prob[name][idx])
        rows.append(row)
K = pd.DataFrame(rows)
K.to_csv(OUT / "alert_classifier.csv", index=False, encoding="utf-8-sig")
md(K.round(3).to_markdown(index=False))
md("\nPR-AUC는 양성비율(무작위 분류 시 기대값)과 비교해 읽는다.\n")

# ---------------------------------------------------------------- 해석: SHAP
md("## 4. 기상 변수 기여도 (업종 단위 전체 데이터로 학습한 M2의 SHAP)\n")
f2 = BASE_F + WX_F
full = lgbm(f2).fit(x[f2], x.target)
shap = pd.DataFrame(full.booster_.predict(x[f2], pred_contrib=True)[:, :-1], columns=f2, index=x.index)
imp = shap.abs().groupby(x.MCT_SGG_CD).mean().T.loc[WX_F + ["lag7_rel", "roll7_rel", "dow", "holiday"]]
md("평균 |SHAP| (log 결제액 편차 단위, 0.01 ≈ 1%):\n")
md(imp.round(4).to_markdown())
md()
md("SHAP는 전체 기간 평균 예측 대비 기여도라 '평상 날씨 대비 손실'(2절 반사실 추정)과 크기가 다르다. "
   "변수별 상대적 중요도와 반응 모양을 보는 용도로만 쓴다.\n")
fig, axes = plt.subplots(1, 2, figsize=(12, 4.3))
for r in REGIONS:
    m = x.MCT_SGG_CD == r
    s = x[m].sample(min(4000, m.sum()), random_state=0)
    axes[0].scatter(s.rain, (shap.loc[s.index, ["rain", "rain_hmax"]].sum(axis=1)) * 100, s=7, alpha=0.35,
                    color=COLOR[r], label=r)
    axes[1].scatter(s.temperature_max_c, shap.loc[s.index, ["tmax_anom", "heat33", "heat35", "heat_run",
                                                           "tropical"]].sum(axis=1) * 100,
                    s=7, alpha=0.35, color=COLOR[r], label=r)
axes[0].set_xscale("symlog", linthresh=1)
axes[0].set_xlabel("일강수량 (mm, symlog)")
axes[1].set_xlabel("일최고기온 (℃)")
for ax, t in zip(axes, ["강수 변수의 매출 기여 (SHAP, %)", "기온·폭염 변수의 매출 기여 (SHAP, %)"]):
    ax.axhline(0, color=INK2, lw=1)
    ax.set_title(t, loc="left")
    ax.set_ylabel("log 편차 기여 × 100 (약 %)")
axes[0].legend(markerscale=3)
fig.tight_layout()
fig.savefig(OUT / "03_shap_dependence.png")
plt.close(fig)
md("![SHAP 의존도](03_shap_dependence.png)\n")

oof.to_csv(OUT / "oof_predictions_industry_weekcv.csv", index=False, encoding="utf-8-sig")
(OUT / "summary.md").write_text("\n".join(log), encoding="utf-8")
