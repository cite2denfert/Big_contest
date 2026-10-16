"""춘천 업종군 단위 강수 피해 예측 모델 (모델 1) + 충격-회복 곡선.

활용: 기상 예보(강수)를 넣으면 다음 날 업종군별 매출과 '비 때문에 줄어드는 매출'을 예측한다.

예측 모델
  단위: 춘천 업종군(12개) 일별 결제액 (상권 업종·개인 결제)
  목표: log(결제액) - 최근 28일 평균 log(결제액) → 예측값 = 최근 수준 + 예측 편차
  M0 기준선: 지난주 같은 요일
  M1 LightGBM, 기상 제외: 달력 + 최근 매출 이력 + 업종군
  M2 LightGBM, 강수 포함: M1 + 강수 변수(일강수, 시간 최대강수, 강수 시간 수, 전날·전전날 강수, 연속 강수일)
     + 최고기온 편차·폭염 여부(통제용). 강수 변수에는 '많을수록 매출이 늘지 않는다' 단조 제약.
  M3 해석형: M1 예측 × 업종군별 강수 구간 보정(학습 기간 잔차를 0 중심으로 축소한 평균)
  학습 데이터: (A) 춘천만 / (B) 춘천+강남(업종군·지역 변수 포함) — 평가는 항상 춘천
검증: 시간 순 확장 창 — 9·10·11·12월을 차례로 시험, 시험 달 이전 전 기간으로 학습 (미래 예측과 같은 조건)
지표: WAPE(절대오차 합/실제 합), 편향(평균 log 오차; 강수일에 0에 가까울수록 비 효과를 잘 반영)

충격-회복 곡선
  춘천 업종군별 log(결제액) = 주 고정효과 + 요일 + 공휴일 + Σ_{k=0..5} b_k·[k일 전 호우(30mm+)]
  누적 효과와 보충률(1~5일 뒤 효과 합 ÷ 당일 손실)로 회복탄력성을 본다.

실행: uv run --no-project --with pandas --with matplotlib --with tabulate --with statsmodels --with lightgbm --with scikit-learn python -X utf8 scripts/chuncheon_model.py
"""
import warnings

import lightgbm as lgb
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import statsmodels.api as sm


from common import INDUSTRY_GROUPS, ROOT
from chuncheon_data import BASE_F, CC, CTRL_F, RAIN_F, RAIN_LABELS, build_panel, lgbm
from weather_models import EVE, HOL, eb_shrink

warnings.filterwarnings("ignore")
OUT = ROOT / "outputs" / "chuncheon_model"
OUT.mkdir(parents=True, exist_ok=True)
MODELS = ["M0 지난주 같은 요일", "M1 기상 제외", "M2 강수 포함", "M3 M1+강수 보정"]
MCOLOR = dict(zip(MODELS, ["#c3c2b7", "#86b6ef", "#1c5cab", "#eb6834"]))
INK2, MUTED, GRID = "#52514e", "#898781", "#e1e0d9"
plt.rcParams.update({
    "font.family": "Malgun Gothic", "axes.unicode_minus": False, "savefig.dpi": 150,
    "savefig.bbox": "tight", "axes.facecolor": "#fcfcfb", "figure.facecolor": "#fcfcfb",
    "axes.edgecolor": "#c3c2b7", "xtick.color": MUTED, "ytick.color": MUTED, "axes.grid": True,
    "grid.color": GRID, "grid.linewidth": 0.6, "axes.spines.top": False, "axes.spines.right": False,
    "axes.titlesize": 12, "axes.titleweight": "bold", "legend.frameon": False,
})
TEST_MONTHS = [9, 10, 11, 12]
log = []


def md(text=""):
    print(text)
    log.append(text)


# ---------------------------------------------------------------- 데이터
# ---------------------------------------------------------------- 데이터
card, w, x = build_panel()
cc = x.MCT_SGG_CD == CC

md("# 춘천 업종군 강수 피해 예측 모델\n")
md("방법은 `scripts/chuncheon_model.py` 상단 주석 참고.\n")
md(f"- 춘천 업종군 {x[cc].group.nunique()}개, 학습 가능 행 {cc.sum():,}행 (2025-07-08~12-31)")
ev = x[cc].drop_duplicates("date")
md("- 춘천 월별 강수일: " + ", ".join(
    f"{m}월 10mm+ {int((ev[ev.month == m].rain >= 10).sum())}일·30mm+ {int((ev[ev.month == m].rain >= 30).sum())}일"
    for m in range(7, 13)))
md()



def rain_adjust(train, pred_col):
    """M3: 학습 기간 M1 잔차의 업종군×강수구간 평균을 0 중심으로 축소한 보정값."""
    r = train.assign(res=train.y - train[pred_col])
    adj = {}
    for lab in RAIN_LABELS[1:]:
        s = r[r.rbin == lab].groupby("group").res.agg(["mean", "std", "count"])
        s = s[s["count"] >= 2]
        if s.empty:
            continue
        base = r[r.rbin == "0"].groupby("group").res.mean().reindex(s.index).fillna(0)
        b = s["mean"] - base
        se = (s["std"].fillna(s["std"].median()) / np.sqrt(s["count"])).clip(lower=0.01)
        shr, _ = eb_shrink(b.values, se.values)
        adj.update({(gname, lab): v for gname, v in zip(s.index, shr)})
    return adj


oofs = {}
for scheme, train_mask in [("A 춘천만 학습", cc), ("B 춘천+강남 학습", x.MCT_SGG_CD.notna())]:
    oof = x[cc][["group", "date", "month", "y", "roll28", "rain", "rbin", "TS_AT"]].copy()
    oof["M0 지난주 같은 요일"] = x.loc[cc, "roll28"] + x.loc[cc, "lag7_rel"].fillna(0)
    for m in TEST_MONTHS:
        tr = train_mask & (x.month < m)
        te = cc & (x.month == m)
        bf = BASE_F + (["region_c"] if scheme.startswith("B") else [])
        m1 = lgbm(bf).fit(x.loc[tr, bf], x.loc[tr, "target"])
        oof.loc[te, "M1 기상 제외"] = x.loc[te, "roll28"] + m1.predict(x.loc[te, bf])
        f2 = bf + RAIN_F + CTRL_F
        m2 = lgbm(f2).fit(x.loc[tr, f2], x.loc[tr, "target"])
        oof.loc[te, "M2 강수 포함"] = x.loc[te, "roll28"] + m2.predict(x.loc[te, f2])
        xcf = x.loc[te, f2].copy()
        for c in RAIN_F:
            xcf[c] = 0
        oof.loc[te, "cf"] = x.loc[te, "roll28"] + m2.predict(xcf)
        # M3: 춘천 학습 구간의 M1 적합 잔차로 강수 보정
        trc = cc & (x.month < m)
        fit_c = x[trc].assign(p=x.loc[trc, "roll28"] + m1.predict(x.loc[trc, bf]))
        adj = rain_adjust(fit_c, "p")
        oof.loc[te, "M3 M1+강수 보정"] = oof.loc[te, "M1 기상 제외"] + [
            adj.get((gname, lab), 0.0) for gname, lab in zip(oof.loc[te, "group"], oof.loc[te, "rbin"])]
    oofs[scheme] = oof[oof.month.isin(TEST_MONTHS)]

SUB = {"전체": lambda o: o.rain >= 0, "강수 10mm+": lambda o: o.rain >= 10, "호우 30mm+": lambda o: o.rain >= 30,
       "무강수": lambda o: o.rain == 0}
rows = []
for scheme, oof in oofs.items():
    for sname, f in SUB.items():
        s = oof[f(oof)]
        for mname in MODELS:
            rows.append({"학습": scheme, "구간": sname, "모델": mname, "업종군×일": len(s),
                         "WAPE": np.abs(np.exp(s[mname]) - s.TS_AT).sum() / s.TS_AT.sum(),
                         "편향": (s.y - s[mname]).mean()})
P = pd.DataFrame(rows)
P.to_csv(OUT / "timecv_performance.csv", index=False, encoding="utf-8-sig")

md("## 1. 시간 순 검증 성능 (9~12월 각 달을 그 이전 기간으로 학습해 예측)\n")
for metric, fmt, note in [("WAPE", "{:.1%}", "낮을수록 좋음"),
                          ("편향", "{:+.3f}", "실제−예측 평균 log. 음수 = 과대예측 (비 효과를 놓치면 강수일에 음수)")]:
    t = P.pivot_table(index=["학습", "구간"], columns="모델", values=metric, sort=False)[MODELS]
    md(f"**{metric}** ({note})\n")
    md(t.map(fmt.format).to_markdown())
    md()

fig, axes = plt.subplots(1, 2, figsize=(13, 4.3), sharey=True)
for ax, scheme in zip(axes, oofs):
    s = P[P.학습 == scheme]
    xx = np.arange(len(SUB))
    for i, mname in enumerate(MODELS):
        v = s[s.모델 == mname].set_index("구간").reindex(list(SUB)).WAPE * 100
        ax.bar(xx + (i - 1.5) * 0.2, v, width=0.19, color=MCOLOR[mname], label=mname)
        for xi, vi in zip(xx, v):
            ax.text(xi + (i - 1.5) * 0.2, vi + 0.3, f"{vi:.1f}", ha="center", fontsize=7, color=INK2)
    ax.set_xticks(xx, list(SUB))
    ax.set_title(f"춘천 예측 오차 WAPE (%) — {scheme}", loc="left")
    ax.grid(axis="x", visible=False)
fig.tight_layout(rect=(0, 0.08, 1, 1))
h, l = axes[0].get_legend_handles_labels()
fig.legend(h, l, loc="lower center", ncol=4)
fig.savefig(OUT / "01_timecv_wape.png")
plt.close(fig)
md("![시간 순 검증](01_timecv_wape.png)\n")

# ---------------------------------------------------------------- 예측 피해 (M2, 강수 변수 0으로 바꾼 반사실)
best = "B 춘천+강남 학습" if P[(P.학습.str.startswith("B")) & (P.구간 == "강수 10mm+") & (P.모델 == "M2 강수 포함")].WAPE.iloc[0] \
    <= P[(P.학습.str.startswith("A")) & (P.구간 == "강수 10mm+") & (P.모델 == "M2 강수 포함")].WAPE.iloc[0] else "A 춘천만 학습"
oof = oofs[best]
oof["예측손실(백만)"] = (np.exp(oof.cf) - np.exp(oof["M2 강수 포함"])) / 1e6
oof["예측손실률"] = 1 - np.exp(oof["M2 강수 포함"] - oof.cf)
oof["실제편차"] = oof.y - oof["M1 기상 제외"]
md(f"## 2. 예측 피해 (시험 기간 9~12월, {best}의 M2)\n")
md("예측 피해 = '강수 변수를 0으로 바꾼 예측' − '실제 예보(관측) 강수로 한 예측'. "
   "시험 기간에 학습하지 않은 날에 대한 예측이라 실제 예보 활용과 같은 조건.\n")
dmg = oof[oof.rain >= 10].groupby("group").agg(일수=("date", "nunique"), 예측손실률=("예측손실률", "mean"),
                                              예측손실_백만=("예측손실(백만)", "sum"),
                                              실제편차_M1대비=("실제편차", "mean")).sort_values("예측손실_백만", ascending=False)
dmg["실제편차_M1대비"] = np.exp(dmg.실제편차_M1대비) - 1
d2 = dmg.copy()
d2["예측손실률"] = d2.예측손실률.map("{:.1%}".format)
d2["실제편차_M1대비"] = d2.실제편차_M1대비.map("{:+.1%}".format)
md("강수 10mm+ 일, 업종군별 (실제편차 = 실제 매출이 기상 제외 예측보다 얼마나 낮았나 → 예측손실률과 비교):\n")
md(d2.round(1).to_markdown())
rho = dmg[["예측손실률", "실제편차_M1대비"]].corr(method="spearman").iat[0, 1]
md(f"\n- 업종군 순위 일치도(예측 손실률 vs 실제 편차, 스피어만): **{-rho:.2f}** (1에 가까울수록 피해가 큰 업종군을 맞힘)\n")
dmg.to_csv(OUT / "predicted_damage_rain10.csv", encoding="utf-8-sig")

# ---------------------------------------------------------------- 충격-회복 곡선
md("## 3. 충격-회복 곡선 (호우 30mm+ 당일~5일 뒤, 춘천 업종군)\n")
LAGS = range(6)
wc = w[w.MCT_SGG_CD == CC].set_index("date")
shock = pd.DataFrame({f"L{k}": (wc.rain.shift(k) >= 30).astype(float) for k in LAGS}, index=wc.index)
day = card[card.MCT_SGG_CD == CC].groupby(["group", "date"]).TS_AT.sum().reset_index()
rows = []
for gname, s in day.groupby("group"):
    s = s.set_index("date").join(shock, how="inner").dropna()
    if len(s) < 170:
        continue
    X = pd.get_dummies(s.index.isocalendar().week.astype(str), prefix="wk", drop_first=True).set_index(s.index)
    X = X.join(pd.get_dummies(s.index.dayofweek.astype(str), prefix="d", drop_first=True).set_index(s.index))
    X["hol"] = s.index.isin(HOL)
    X["eve"] = s.index.isin(EVE)
    X = sm.add_constant(X.join(s[[f"L{k}" for k in LAGS]]).astype(float))
    res = sm.OLS(np.log(s.TS_AT), X).fit(cov_type="HAC", cov_kwds={"maxlags": 7})
    b = res.params[[f"L{k}" for k in LAGS]]
    cov = res.cov_params().loc[b.index, b.index]
    after = b.iloc[1:].sum()
    rows.append({"group": gname, **{f"b{k}": b.iloc[k] for k in LAGS}, **{f"se{k}": res.bse[f"L{k}"] for k in LAGS},
                 "당일": np.exp(b.iloc[0]) - 1, "1~5일 합": after,
                 "1~5일 합_se": np.sqrt(cov.iloc[1:, 1:].values.sum()),
                 "누적(0~5일)": b.sum(), "누적_se": np.sqrt(cov.values.sum()),
                 "보충률": -after / b.iloc[0] if b.iloc[0] < -0.02 else np.nan})
R = pd.DataFrame(rows).set_index("group").reindex([gname for gname in INDUSTRY_GROUPS if gname in set(day.group)])
R = R.dropna(subset=["b0"])
R.to_csv(OUT / "shock_recovery.csv", encoding="utf-8-sig")
t = R[["당일", "1~5일 합", "1~5일 합_se", "누적(0~5일)", "누적_se", "보충률"]].copy()
t["당일"] = t.당일.map("{:+.1%}".format)
t["유의(1~5일)"] = np.where((R["1~5일 합"].abs() / R["1~5일 합_se"]) > 1.96, "예", "아니오")
md("보충률 = −(1~5일 뒤 효과 합) ÷ 당일 효과. 1이면 손실을 모두 메움, 0이면 못 메움, 음수면 손실이 이어짐.\n")
md(t.round(3).to_markdown())
md()

fig, ax = plt.subplots(figsize=(10, 5))
order = R.sort_values("b0").index[:6]
cols = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#4a3aa7"]
for c, gname in zip(cols, order):
    v = R.loc[gname, [f"b{k}" for k in LAGS]].values.astype(float)
    ax.plot(list(LAGS), (np.exp(v) - 1) * 100, marker="o", ms=7, lw=2, color=c, label=gname, mec="#fcfcfb", mew=1.5)
ax.axhline(0, color=INK2, lw=1)
ax.set_xticks(list(LAGS), ["당일", "1일 뒤", "2일 뒤", "3일 뒤", "4일 뒤", "5일 뒤"])
ax.set_ylabel("결제액 변화 (%)")
ax.set_title("춘천 호우(30mm+) 후 업종군별 매출 경로 — 당일 하락이 큰 6개 업종군", loc="left")
ax.legend(ncol=3, loc="lower right")
fig.tight_layout()
fig.savefig(OUT / "02_shock_recovery.png")
plt.close(fig)
md("![충격-회복](02_shock_recovery.png)\n")

(OUT / "summary.md").write_text("\n".join(log), encoding="utf-8")
