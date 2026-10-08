"""날씨 효과 회귀모형 공통 함수 (업종군 분석·취약도 지수에서 사용)."""
import numpy as np
import pandas as pd
import statsmodels.api as sm

from common import HOLIDAYS, load_weather_daily

# 추석 연휴는 주말(10/4)까지 하나의 연휴로 처리
HOL = HOLIDAYS.union(pd.to_datetime(["2025-10-04"]))
EVE = pd.to_datetime(["2025-12-24", "2025-12-31"])
TEMP_BINS = [-np.inf, 30, 33, 35, np.inf]
TEMP_LABELS = ["<30", "30~33", "33~35", "35+"]
RAIN_BINS = [-np.inf, 0, 10, 30, np.inf]
RAIN_LABELS = ["0", "0.1~10", "10~30", "30+"]
HEAT_TERMS = ["t_30~33", "t_33~35", "t_35+", "tropical"]
RAIN_TERMS = ["r_0.1~10", "r_10~30", "r_30+", "r30_lag1"]
TERMS = HEAT_TERMS + RAIN_TERMS
LABEL = {"t_30~33": "최고 30~33℃", "t_33~35": "최고 33~35℃", "t_35+": "최고 35℃+",
         "tropical": "열대야(최저 25℃+)", "r_0.1~10": "강수 0.1~10mm", "r_10~30": "강수 10~30mm",
         "r_30+": "호우(30mm+)", "r30_lag1": "호우 다음날"}


def weather_features():
    """지역·일별 기상 구간 변수."""
    w = load_weather_daily()[["MCT_SGG_CD", "date", "temperature_max_c", "temperature_min_c",
                              "precipitation_reported_mm"]].copy()
    w["rain"] = w.precipitation_reported_mm.fillna(0)
    w["tbin"] = pd.cut(w.temperature_max_c, TEMP_BINS, labels=TEMP_LABELS, right=False)
    w["rbin"] = pd.cut(w.rain, RAIN_BINS, labels=RAIN_LABELS)
    w["tropical"] = (w.temperature_min_c >= 25).astype(float)
    w = w.sort_values(["MCT_SGG_CD", "date"])
    w["r30_lag1"] = (w.groupby("MCT_SGG_CD").rain.shift(1) >= 30).astype(float)
    return w.dropna(subset=["temperature_max_c"])  # 강남 9/10~11 관측 결측일 제외


def design(g):
    """주 고정효과 + 요일 + 공휴일 + 연말 전야 + 기상 구간."""
    X = pd.DataFrame(index=g.index)
    X = X.join(pd.get_dummies(g.date.dt.isocalendar().week.astype(str), prefix="wk", drop_first=True))
    X = X.join(pd.get_dummies(g.date.dt.dayofweek.astype(str), prefix="dow", drop_first=True))
    X["holiday"] = g.date.isin(HOL)
    X["eve"] = g.date.isin(EVE)
    for lab in TEMP_LABELS[1:]:
        X[f"t_{lab}"] = g.tbin.eq(lab)
    for lab in RAIN_LABELS[1:]:
        X[f"r_{lab}"] = g.rbin.eq(lab)
    X["tropical"] = g.tropical
    X["r30_lag1"] = g.r30_lag1
    return sm.add_constant(X.astype(float))


def fit_panel(df, keys, value="TS_AT"):
    """keys 단위(예: 지역×업종군)마다 log(value)를 회귀해 기상 계수 표를 반환."""
    rows = []
    for k, g in df.groupby(keys):
        g = g[g[value] > 0].sort_values("date").reset_index(drop=True)
        X = design(g)
        res = sm.OLS(np.log(g[value]), X).fit(cov_type="HAC", cov_kwds={"maxlags": 7})
        normal = g[value][g.tbin.eq("<30") & g.rbin.eq("0") & ~g.date.isin(HOL)].mean()
        for t in TERMS:
            if t in res.params and X[t].sum() > 0:
                rows.append({**dict(zip(keys, k if isinstance(k, tuple) else (k,))), "항목": t,
                             "계수": res.params[t], "표준오차": res.bse[t], "p": res.pvalues[t],
                             "일수": int(X[t].sum()), "기준일값": normal, "n": len(g), "R2": res.rsquared})
    out = pd.DataFrame(rows)
    out["변화율"] = np.exp(out.계수) - 1
    out["하한"] = np.exp(out.계수 - 1.96 * out.표준오차) - 1
    out["상한"] = np.exp(out.계수 + 1.96 * out.표준오차) - 1
    return out


def bh(p):
    from statsmodels.stats.multitest import multipletests
    return multipletests(p, method="fdr_bh")[1]


def eb_shrink(b, se):
    """경험적 베이즈 축소: 표본이 적어 표준오차가 큰 계수를 집단 평균 쪽으로 당김 (DerSimonian-Laird)."""
    b, se = np.asarray(b, float), np.asarray(se, float)
    w = 1 / se ** 2
    mu = np.sum(w * b) / np.sum(w)
    q = np.sum(w * (b - mu) ** 2)
    tau2 = max(0.0, (q - (len(b) - 1)) / (np.sum(w) - np.sum(w ** 2) / np.sum(w)))
    k = tau2 / (tau2 + se ** 2)
    return mu + k * (b - mu), k
