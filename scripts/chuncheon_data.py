"""춘천 강수 모델 공통 데이터·설정 (chuncheon_model.py, chuncheon_subdisaster.py에서 사용).

build_panel(): 지역 × 업종군 × 일 패널 (목표 = log 결제액 − 최근 28일 평균, 달력·이력·강수·통제 변수)
"""
import lightgbm as lgb
import numpy as np
import pandas as pd

from common import GROUP_OF, commerce, load_card, load_weather_hourly
from weather_models import EVE, HOL, weather_features

CC = "강원 춘천시"
PARAMS = dict(n_estimators=400, learning_rate=0.03, num_leaves=7, min_child_samples=40, subsample=0.8,
              subsample_freq=1, colsample_bytree=0.8, reg_lambda=5.0, random_state=0, verbose=-1)
BASE_F = ["dow", "holiday", "eve", "dom", "lag7_rel", "lag14_rel", "roll7_rel", "group_c"]
RAIN_F = ["rain", "rain_hmax", "rain_hours", "rain_lag1", "rain_lag2", "wet_run"]
CTRL_F = ["tmax_anom", "heat33"]
MONO = {"rain": -1, "rain_hmax": -1, "rain_hours": -1}
RAIN_BINS = [-np.inf, 0, 10, 30, np.inf]
RAIN_LABELS = ["0", "0.1~10", "10~30", "30+"]


def lgbm(feats):
    return lgb.LGBMRegressor(**PARAMS, monotone_constraints=[MONO.get(f, 0) for f in feats])


def build_panel():
    """(card, w, x): 상권 카드 데이터, 지역·일 기상 변수, 지역×업종군×일 학습 패널."""
    card = commerce(load_card(1)).assign(group=lambda x: x.MCT_RY_CD.map(GROUP_OF))
    w = weather_features()
    wh = load_weather_hourly().assign(p=lambda x: x.precipitation_reported_mm.fillna(0))
    hw = wh.groupby(["MCT_SGG_CD", "date"]).agg(rain_hmax=("p", "max"), rain_hours=("p", lambda s: (s > 0).sum()))
    w = w.merge(hw.reset_index(), on=["MCT_SGG_CD", "date"], how="left")
    g = w.groupby("MCT_SGG_CD")
    w["rain_lag1"] = g.rain.shift(1)
    w["rain_lag2"] = g.rain.shift(2)
    wet = (w.rain >= 1).astype(int)
    w["wet_run"] = wet.groupby([w.MCT_SGG_CD, (wet != wet.groupby(w.MCT_SGG_CD).shift()).cumsum()]).cumsum() * wet
    w["tmax_anom"] = w.temperature_max_c - g.temperature_max_c.transform(lambda s: s.shift(1).rolling(14, min_periods=5).mean())
    w["heat33"] = (w.temperature_max_c >= 33).astype(int)

    x = card.groupby(["MCT_SGG_CD", "group", "date"]).TS_AT.sum().reset_index()
    units = x[["MCT_SGG_CD", "group"]].drop_duplicates()
    grid = units.merge(pd.DataFrame({"date": pd.date_range("2025-07-01", "2025-12-31")}), how="cross")
    x = grid.merge(x, how="left", on=["MCT_SGG_CD", "group", "date"]).sort_values(["MCT_SGG_CD", "group", "date"])
    x["y"] = np.log(x.TS_AT)
    gy = x.groupby(["MCT_SGG_CD", "group"]).y
    x["roll28"] = gy.transform(lambda s: s.shift(1).rolling(28, min_periods=7).mean())
    x["lag7_rel"] = gy.shift(7) - x.roll28
    x["lag14_rel"] = gy.shift(14) - x.roll28
    x["roll7_rel"] = gy.transform(lambda s: s.shift(1).rolling(7, min_periods=4).mean()) - x.roll28
    x["target"] = x.y - x.roll28
    x = x.merge(w[["MCT_SGG_CD", "date"] + RAIN_F + CTRL_F], on=["MCT_SGG_CD", "date"], how="left")
    x["dow"] = x.date.dt.dayofweek
    x["holiday"] = x.date.isin(HOL).astype(int)
    x["eve"] = x.date.isin(EVE).astype(int)
    x["dom"] = x.date.dt.day
    x["group_c"] = (x.MCT_SGG_CD.str[3:] + "_" + x.group).astype("category")
    x["region_c"] = x.MCT_SGG_CD.astype("category")
    x["rbin"] = pd.cut(x.rain, RAIN_BINS, labels=RAIN_LABELS).astype(str)
    x = x.dropna(subset=["target", "roll28", "tmax_anom", "rain"]).reset_index(drop=True)
    x["month"] = x.date.dt.month
    return card, w, x
