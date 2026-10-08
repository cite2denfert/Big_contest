"""업종군 단위 폭염·호우 효과 + 강남 업종 제외 기준 민감도 점검.

1) 13개 업종군 × 2개 지역마다 일별 log(결제액) 회귀 (모형 구조는 weather_models.design)
2) 제외 기준을 바꿔도 '전체 상권' 날씨 효과가 유지되는지 확인
   - 기본: 비상권 13개 업종 제외
   - +컴퓨터/소프트웨어·쇼핑몰 포함
   - +ZZ_나머지 포함
   - 결제건수 기준(기본 제외), ZZ_나머지 단독(결제건수 기준)

실행: uv run --no-project --with pandas --with matplotlib --with tabulate --with statsmodels python -X utf8 scripts/group_regression.py
"""
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from common import GROUP_OF, INDUSTRY_GROUPS, NON_COMMERCE, REGIONS, ROOT, load_card
from weather_models import LABEL, TERMS, bh, fit_panel, weather_features

OUT = ROOT / "outputs" / "group_regression"
OUT.mkdir(parents=True, exist_ok=True)
INK2, MUTED = "#52514e", "#898781"
plt.rcParams.update({
    "font.family": "Malgun Gothic", "axes.unicode_minus": False, "savefig.dpi": 150,
    "savefig.bbox": "tight", "axes.facecolor": "#fcfcfb", "figure.facecolor": "#fcfcfb",
    "axes.edgecolor": "#c3c2b7", "xtick.color": MUTED, "ytick.color": MUTED,
    "axes.titlesize": 12, "axes.titleweight": "bold",
})
log = []


def md(text=""):
    print(text)
    log.append(text)


card = load_card(1)
card = card[card.SEX_CCD != "법인"]
w = weather_features()

md("# 업종군 단위 폭염·호우 효과\n")
md("업종군 정의: `scripts/common.py`의 `INDUSTRY_GROUPS` (13개 군). 모형: `scripts/weather_models.py` "
   "(주 고정효과·요일·공휴일 통제, HAC 표준오차). 이번 모형부터 **열대야(일최저 25℃ 이상)** 를 추가했다.\n")

# ---------------------------------------------------------------- 1. 제외 기준 민감도
md("## 1. 강남 업종 제외 기준 민감도\n")
base = card[~card.MCT_RY_CD.isin(NON_COMMERCE)]
scen = {
    "기본(13개 제외)": (base, "TS_AT"),
    "+컴퓨터·쇼핑몰": (card[~card.MCT_RY_CD.isin(set(NON_COMMERCE) - {"컴퓨터/소프트웨어", "쇼핑몰"})], "TS_AT"),
    "+ZZ_나머지": (card[~card.MCT_RY_CD.isin(set(NON_COMMERCE) - {"ZZ_나머지"})], "TS_AT"),
    "기본, 결제건수": (base, "USE_CNT"),
    "ZZ_나머지만, 결제건수": (card[card.MCT_RY_CD == "ZZ_나머지"], "USE_CNT"),
}
rows = []
for name, (d, val) in scen.items():
    t = d.groupby(["MCT_SGG_CD", "date"])[val].sum().reset_index().merge(w, on=["MCT_SGG_CD", "date"])
    est = fit_panel(t, ["MCT_SGG_CD"], value=val)
    est["시나리오"] = name
    rows.append(est)
S = pd.concat(rows)
S["효과"] = S.apply(lambda s: f"{s.변화율:+.1%}" + ("*" if s.p < 0.05 else ""), axis=1)
for r in REGIONS:
    tab = S[S.MCT_SGG_CD == r].pivot(index="항목", columns="시나리오", values="효과").reindex(TERMS)
    tab.index = [LABEL[i] for i in tab.index]
    md(f"**{r}** (* p<0.05)\n")
    md(tab[list(scen)].to_markdown())
    md()
S.to_csv(OUT / "exclusion_sensitivity.csv", index=False, encoding="utf-8-sig")

# ---------------------------------------------------------------- 2. 업종군 회귀
md("## 2. 업종군별 효과\n")
base = base.assign(group=base.MCT_RY_CD.map(GROUP_OF))
gd = base.groupby(["MCT_SGG_CD", "group", "date"]).TS_AT.sum().reset_index().merge(w, on=["MCT_SGG_CD", "date"])
nd = gd.groupby(["MCT_SGG_CD", "group"]).date.transform("nunique")
gd = gd[nd >= 175]
G = fit_panel(gd, ["MCT_SGG_CD", "group"])
G["q"] = np.nan
for _, idx in G.groupby(["MCT_SGG_CD", "항목"]).groups.items():
    G.loc[idx, "q"] = bh(G.loc[idx, "p"])
share = gd.groupby(["MCT_SGG_CD", "group"]).TS_AT.sum()
G["매출비중"] = [share[(r, g)] / share[r].sum() for r, g in zip(G.MCT_SGG_CD, G.group)]
G.to_csv(OUT / "group_coefficients.csv", index=False, encoding="utf-8-sig")

SHOW = ["t_33~35", "t_35+", "tropical", "r_10~30", "r_30+", "r30_lag1"]
SHORT = {"t_33~35": "최고\n33~35℃", "t_35+": "최고\n35℃+", "tropical": "열대야", "r_10~30": "강수\n10~30mm",
         "r_30+": "호우\n30mm+", "r30_lag1": "호우\n다음날"}
order = list(INDUSTRY_GROUPS)
fig, axes = plt.subplots(1, 2, figsize=(15, 7.2), gridspec_kw={"wspace": 0.42})
lim = 30
for ax, r in zip(axes, REGIONS):
    s = G[G.MCT_SGG_CD == r]
    mat = s.pivot(index="group", columns="항목", values="변화율").reindex(index=order, columns=SHOW) * 100
    q = s.pivot(index="group", columns="항목", values="q").reindex(index=order, columns=SHOW)
    im = ax.imshow(mat.clip(-lim, lim), cmap="RdBu", vmin=-lim, vmax=lim, aspect="auto")
    for i in range(mat.shape[0]):
        for j in range(mat.shape[1]):
            v = mat.iat[i, j]
            if np.isnan(v):
                continue
            sig = q.iat[i, j] < 0.05
            ax.text(j, i, f"{v:+.0f}" + ("*" if sig else ""), ha="center", va="center", fontsize=9,
                    fontweight="bold" if sig else "normal",
                    color="#ffffff" if abs(v) > 18 else "#0b0b0b")
    ax.set_xticks(range(len(SHOW)), [SHORT[t] for t in SHOW], fontsize=9)
    ax.set_yticks(range(len(order)), order)
    ax.set_title(r, loc="left")
    for sp in ax.spines.values():
        sp.set_visible(False)
cb = fig.colorbar(im, ax=axes, shrink=0.6, pad=0.02)
cb.set_label("결제액 변화 (%), ±30%에서 색 고정")
fig.suptitle("업종군 × 기상 조건 결제액 변화 (%) — 굵은 글씨·* = q<0.05", x=0.01, ha="left", fontweight="bold")
fig.savefig(OUT / "01_group_heatmap.png")
plt.close(fig)
md("![업종군 히트맵](01_group_heatmap.png)\n")

for r in REGIONS:
    s = G[(G.MCT_SGG_CD == r) & (G.q < 0.05) & G.항목.isin(SHOW)].sort_values("변화율")
    md(f"**{r} 유의한 업종군 효과 (q<0.05)**\n")
    t = s[["group", "항목", "변화율", "하한", "상한", "일수", "매출비중"]].copy()
    t["항목"] = t.항목.map(LABEL)
    for c in ["변화율", "하한", "상한", "매출비중"]:
        t[c] = t[c].map("{:+.1%}".format if c != "매출비중" else "{:.1%}".format)
    md(t.to_markdown(index=False) if len(t) else "없음")
    md()

(OUT / "summary.md").write_text("\n".join(log), encoding="utf-8")
