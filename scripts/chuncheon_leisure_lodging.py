"""인사이트 2 — 춘천 레저·숙박이 비 오는 날 취약한 상권인가.

모든 효과는 같은 회귀 틀로 추정한다 (단위마다 따로):
  log(일 결제액) = 주 고정효과 + 요일 + 공휴일(추석 연휴 포함) + 연말 전야
                   + 최고기온 구간(30~33·33~35·35℃+) + 강수 0.1~10mm + 강수 10mm+ [+ 10mm+ 1~3일 뒤]
  표준오차는 HAC(Newey-West, 7일). 비 피해율 = 1 − exp(10mm+ 계수), 기준은 비 안 온 날.

1) 업종군 12개의 10mm+ 피해율과 매출 비중                       (데이터1: 일×업종, 개인 결제)
2) 회복: 10mm+ 당일과 1~3일 뒤 계수 합(누적 효과), 보충률 = −(1~3일 뒤 합)/당일
3) 외지인 매출 비중(카드 고객 거주 시도 ≠ 강원) vs 피해율        (데이터2)
4) 레저·숙박 세부 업종 9개: 전체, 고객 거주지(강원/외지)별 피해율   (데이터1·2)

실행: uv run --no-project --with pandas --with statsmodels --with tabulate python -X utf8 scripts/chuncheon_leisure_lodging.py
"""
import json
import warnings

import numpy as np
import pandas as pd
import statsmodels.api as sm

from common import GROUP_OF, INDUSTRY_GROUPS, ROOT, commerce, load_card
from scipy.stats import norm

from weather_models import EVE, HOL, weather_features

warnings.filterwarnings("ignore")
OUT = ROOT / "outputs" / "chuncheon_leisure_lodging"
OUT.mkdir(parents=True, exist_ok=True)
CC = "강원 춘천시"
FOCUS = ["야외·레저", "숙박·여행"]
LAGS = [1, 2, 3]
log = []


def md(text=""):
    print(text)
    log.append(text)


w = weather_features()
w = w[w.MCT_SGG_CD == CC].set_index("date").sort_index()
w["r_lt10"] = ((w.rain > 0) & (w.rain < 10)).astype(float)
w["r10"] = (w.rain >= 10).astype(float)
for k in LAGS:
    w[f"r10_l{k}"] = w.r10.shift(k).fillna(0)


def fit(daily, lags=False, temp="bins"):
    """daily: date-index 일 결제액 Series → 회귀 결과. temp="cont"면 기온 구간 대신 최고(2차)·최저기온 연속값 통제."""
    d = daily[daily > 0].to_frame("y").join(w, how="inner")
    X = pd.get_dummies(d.index.isocalendar().week.astype(str), prefix="wk", drop_first=True).set_index(d.index)
    X = X.join(pd.get_dummies(d.index.dayofweek.astype(str), prefix="dow", drop_first=True).set_index(d.index))
    X["holiday"] = d.index.isin(HOL)
    X["eve"] = d.index.isin(EVE)
    if temp == "bins":
        for lab in ["30~33", "33~35", "35+"]:
            X[f"t_{lab}"] = d.tbin.eq(lab)
    else:
        X["tmax"] = d.temperature_max_c
        X["tmax2"] = d.temperature_max_c ** 2
        X["tmin"] = d.temperature_min_c
    X["r_lt10"] = d.r_lt10
    X["r10"] = d.r10
    if lags:
        for k in LAGS:
            X[f"r10_l{k}"] = d[f"r10_l{k}"]
    X = sm.add_constant(X.astype(float))
    return sm.OLS(np.log(d.y), X).fit(cov_type="HAC", cov_kwds={"maxlags": 7}), len(d)


def loss(res, term="r10"):
    b, se = res.params[term], res.bse[term]
    return {"피해율": 1 - np.exp(b), "하한": 1 - np.exp(b + 1.96 * se), "상한": 1 - np.exp(b - 1.96 * se),
            "p": res.pvalues[term]}


card = commerce(load_card(1))
card = card[card.MCT_SGG_CD == CC].assign(group=lambda x: x.MCT_RY_CD.map(GROUP_OF))
c2 = commerce(load_card(2))
c2 = c2[c2.MCT_SGG_CD == CC].assign(group=lambda x: x.MCT_RY_CD.map(GROUP_OF),
                                     외지=lambda x: ~x.CLN_SGG_CD.str.startswith("강원"))
n_rain = int(w.r10.sum())

md("# 인사이트 2 — 춘천 레저·숙박은 비 오는 날 취약한 상권인가\n")
md("방법은 `scripts/chuncheon_leisure_lodging.py` 상단 주석 참고. 피해율 = 비 10mm+ 날 매출 감소율(비 안 온 날 대비, "
   f"주·요일·공휴일·기온 통제). 2025-07~12 춘천, 비 10mm+ {n_rain}일.\n")

# ---------------------------------------------------------------- 1·2·3. 업종군
total = card.TS_AT.sum()
out_share = c2.groupby(["group", "외지"]).TS_AT.sum().unstack()
out_share = out_share[True] / out_share.sum(axis=1)
rows = []
for g in INDUSTRY_GROUPS:
    s = card[card.group == g]
    if s.empty:
        continue
    daily = s.groupby("date").TS_AT.sum()
    res, n = fit(daily)
    rl, _ = fit(daily, lags=True)
    b0 = rl.params["r10"]
    after = sum(rl.params[f"r10_l{k}"] for k in LAGS)
    names = ["r10"] + [f"r10_l{k}" for k in LAGS]
    cov = rl.cov_params().loc[names, names].values
    rows.append({"group": g, "매출비중": s.TS_AT.sum() / total, "일평균(백만)": daily.mean() / 1e6, "일수": n,
                 **loss(res), "외지비중": out_share.get(g, np.nan),
                 "당일(시차모형)": 1 - np.exp(b0), "누적0~3일": 1 - np.exp(b0 + after),
                 "누적_하한": 1 - np.exp(b0 + after + 1.96 * np.sqrt(cov.sum())),
                 "누적_상한": 1 - np.exp(b0 + after - 1.96 * np.sqrt(cov.sum())),
                 "1~3일합": after, "1~3일합_se": np.sqrt(cov[1:, 1:].sum()),
                 "보충률": -after / b0 if b0 < -0.02 else np.nan})
G = pd.DataFrame(rows).set_index("group").sort_values("피해율", ascending=False)
G.to_csv(OUT / "group_rain10.csv", encoding="utf-8-sig")

md("## 1. 업종군별 비 피해율 (10mm+)\n")
t = G[["매출비중", "피해율", "하한", "상한", "p", "외지비중"]].copy()
for c in ["매출비중", "피해율", "하한", "상한", "외지비중"]:
    t[c] = t[c].map("{:.1%}".format)
md(t.round(3).to_markdown())
rho = G[["피해율", "외지비중"]].corr(method="spearman").iat[0, 1]
md(f"\n- 외지인 비중과 피해율의 순위 상관(스피어만): **{rho:.2f}**\n")

md("## 2. 회복: 비 온 뒤 1~3일 안에 손실을 메우는가\n")
md("누적 = 당일 + 1~3일 뒤 효과 합 (양수 = 손실). 보충률 1 = 손실을 모두 메움, 0 = 못 메움, 음수 = 손실이 이어짐.\n")
t = G[["당일(시차모형)", "누적0~3일", "누적_하한", "누적_상한", "1~3일합", "1~3일합_se", "보충률"]].copy()
for c in ["당일(시차모형)", "누적0~3일", "누적_하한", "누적_상한"]:
    t[c] = t[c].map("{:+.1%}".format)
md(t.round(3).to_markdown())
md()

# ---------------------------------------------------------------- 4. 세부 업종
SUB = [c for g in FOCUS for c in INDUSTRY_GROUPS[g]]
rows = []
for ind in SUB:
    s = card[card.MCT_RY_CD == ind]
    if s.empty:
        continue
    res, n = fit(s.groupby("date").TS_AT.sum())
    r = {"업종": ind, "업종군": GROUP_OF[ind], "매출비중_업종군내": s.TS_AT.sum() / card[card.group == GROUP_OF[ind]].TS_AT.sum(),
         "일수": n, **loss(res)}
    s2 = c2[c2.MCT_RY_CD == ind]
    r["외지비중"] = s2[s2.외지].TS_AT.sum() / s2.TS_AT.sum()
    for lab, m in [("강원", ~s2.외지), ("외지", s2.외지)]:
        daily = s2[m].groupby("date").TS_AT.sum()
        if daily.size >= 150:
            rr, _ = fit(daily)
            e = loss(rr)
            r.update({f"{lab}_피해율": e["피해율"], f"{lab}_하한": e["하한"], f"{lab}_상한": e["상한"], f"{lab}_p": e["p"]})
    rows.append(r)
S = pd.DataFrame(rows).set_index("업종")
S.to_csv(OUT / "subindustry_rain10.csv", encoding="utf-8-sig")
md("## 3. 레저·숙박 세부 업종 (10mm+ 피해율, 양수 = 감소 · 음수 = 증가)\n")
t = S.copy()
for c in [c for c in t.columns if c.endswith(("피해율", "하한", "상한", "비중", "업종군내"))]:
    t[c] = t[c].map(lambda v: "-" if pd.isna(v) else f"{v:+.1%}")
md(t.round(3).to_markdown())
md("\n- 고객 거주지는 카드 고객의 거주 시도(데이터2, 법인 제외). '강원'에는 춘천 밖 강원 거주자도 포함된다.")
md("- 숙박은 플랫폼(앱) 선결제가 춘천 숙박업소가 아닌 온라인 업종으로 잡혀, 카드 데이터에는 현장 결제분 위주로 남는다.\n")

# ---------------------------------------------------------------- 5. 강건성: 기온 통제 방식
md("## 4. 강건성: 기온을 연속값(최고기온 2차식·최저기온)으로 통제해도 같은가\n")
md(f"비 10mm+ 날 최고기온 평균 {w[w.r10 == 1].temperature_max_c.mean():.1f}℃ vs 비 안 온 날 {w[w.rain == 0].temperature_max_c.mean():.1f}℃ "
   "(비가 여름에 몰려 비 온 날이 더 더움) → 기온 구간만으로 덜 걸러진 기온 효과가 있는지 확인. 값은 매출 변화율(음수 = 감소).\n")
rows = []
checks = [("야외·레저(업종군)", card.group == "야외·레저", None), ("골프장", card.MCT_RY_CD == "실내/실외골프장", None),
          ("레저타운·놀이동산", card.MCT_RY_CD == "종합레저타운/놀이동산", None),
          ("사우나·목욕탕", card.MCT_RY_CD == "싸우나/목욕탕", None),
          ("사우나·목욕탕 외지", None, (c2.MCT_RY_CD == "싸우나/목욕탕") & c2.외지),
          ("사우나·목욕탕 강원", None, (c2.MCT_RY_CD == "싸우나/목욕탕") & ~c2.외지),
          ("생활소매(업종군)", card.group == "생활소매", None)]
for name, m1, m2 in checks:
    daily = (card[m1] if m1 is not None else c2[m2]).groupby("date").TS_AT.sum()
    r = {"대상": name}
    for lab, spec in [("기온구간", "bins"), ("기온연속", "cont")]:
        e = loss(fit(daily, temp=spec)[0])
        r.update({f"{lab}_변화": -e["피해율"], f"{lab}_하한": -e["상한"], f"{lab}_상한": -e["하한"], f"{lab}_p": e["p"]})
    rows.append(r)
RB = pd.DataFrame(rows).set_index("대상")
RB.to_csv(OUT / "robustness_temperature.csv", encoding="utf-8-sig")
t = RB.copy()
for c in [c for c in t.columns if not c.endswith("_p")]:
    t[c] = t[c].map("{:+.1%}".format)
md(t.round(3).to_markdown())
rl = G.loc["생활소매"]
z = rl["1~3일합"] / rl["1~3일합_se"]
rebound_p = float(2 * (1 - norm.cdf(abs(z))))
md(f"\n- 생활소매 1~3일 뒤 반등: log {rl['1~3일합']:+.3f} (z = {z:.2f}, p = {rebound_p:.3f})\n")

(OUT / "summary.md").write_text("\n".join(log), encoding="utf-8")

# 발표 장표(docs/slides/build_insight2.js)용 값
slides = {
    "n_rain": n_rain, "rho_outsider": rho, "retail_rebound_p": rebound_p,
    "robust": {k: {c: float(v) for c, v in r.items()} for k, r in RB.iterrows()},
    "groups": [{"name": g, "share": r.매출비중, "loss": r.피해율, "lo": r.하한, "hi": r.상한, "p": r.p,
                "outsider": r.외지비중, "day0": r["당일(시차모형)"], "cum": r["누적0~3일"],
                "cum_lo": r.누적_하한, "cum_hi": r.누적_상한} for g, r in G.iterrows()],
    "sub": [{"name": i, "group": r.업종군, "loss": r.피해율, "lo": r.하한, "hi": r.상한, "p": r.p, "outsider": r.외지비중,
             **{k: (None if pd.isna(r.get(k)) else r.get(k)) for k in ["강원_피해율", "강원_p", "외지_피해율", "외지_p",
                                                                     "외지_하한", "외지_상한", "강원_하한", "강원_상한"]}}
            for i, r in S.iterrows()],
}

(OUT / "slides_data.json").write_text(json.dumps(slides, ensure_ascii=False, indent=1, default=float), encoding="utf-8")
