"""강남구·춘천시 지역 특성 프로파일 (제공 데이터 기반 정량 지표).

카드(상권 업종, 개인 결제)·고객 거주지(데이터2)·SK 유동인구·기상에서 지역 성격을 보여주는 지표를 만들고,
날씨 민감도 해석과 취약도 지수의 '적응력/노출' 요소로 쓴다.

실행: uv run --no-project --with pandas --with matplotlib --with tabulate python -X utf8 scripts/region_profile.py
"""
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from common import FLOW_DIR, GROUP_OF, HOLIDAYS, INDUSTRY_GROUPS, NON_COMMERCE, REGIONS, ROOT, commerce, load_card
from weather_models import weather_features

OUT = ROOT / "outputs" / "region_profile"
OUT.mkdir(parents=True, exist_ok=True)
COLOR = {"서울 강남구": "#2a78d6", "강원 춘천시": "#eb6834"}
HOME = {"서울 강남구": "서울", "강원 춘천시": "강원"}
FLOW_SGG = {"11230": "서울 강남구", "32010": "강원 춘천시"}
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


c1 = commerce(load_card(1)).assign(group=lambda d: d.MCT_RY_CD.map(GROUP_OF))
c2 = load_card(2)
c2 = c2[~c2.MCT_RY_CD.isin(NON_COMMERCE)].assign(group=lambda d: d.MCT_RY_CD.map(GROUP_OF))
w = weather_features()

ind = {}
for r in REGIONS:
    s = c1[c1.MCT_SGG_CD == r]
    d = s.groupby("date").TS_AT.sum()
    normal = ~d.index.isin(HOLIDAYS)
    wkend = d[normal & (d.index.dayofweek >= 5)].mean() / d[normal & (d.index.dayofweek < 5)].mean()
    tb = s.groupby("TIME_GB").TS_AT.sum() / s.TS_AT.sum()
    age = s.groupby("AGE_CCD").TS_AT.sum() / s.TS_AT.sum()
    g = s.groupby("group").TS_AT.sum() / s.TS_AT.sum()
    s2 = c2[c2.MCT_SGG_CD == r]
    outside = s2[s2.CLN_SGG_CD != HOME[r]].TS_AT.sum() / s2.TS_AT.sum()
    ww = w[w.MCT_SGG_CD == r]
    ind[r] = {
        "일평균 상권 결제액(억원)": d.mean() / 1e8,
        "주말/평일 결제액 비": wkend,
        "야간(18~23시) 결제 비중": tb.get("18_23", 0),
        "60대 이상 고객 결제 비중": age[[a for a in age.index if a[:2] in ("60", "70", "80", "90")]].sum(),
        "타 시·도 거주 고객 결제 비중": outside,
        "외식 비중": g.get("외식", 0),
        "생활소매 비중": g.get("생활소매", 0),
        "의료 비중": g.get("의료", 0),
        "야외·레저 + 차량·교통 비중": g.get("야외·레저", 0) + g.get("차량·교통", 0),
        "폭염일(최고 33℃+, 2025 하반기)": int((ww.temperature_max_c >= 33).sum()),
        "열대야일(최저 25℃+)": int(ww.tropical.sum()),
        "호우일(30mm+)": int((ww.rain >= 30).sum()),
    }

# 유동인구
fa, fw, ft = [], [], []
for f in sorted(FLOW_DIR.glob("flow_age_pop_*.csv")):
    fa.append(pd.read_csv(f, sep="|", dtype={"BLOCK_CD": str}).drop_duplicates())
for f in sorted(FLOW_DIR.glob("flow_wkdy_pop_*.csv")):
    fw.append(pd.read_csv(f, sep="|", dtype={"BLOCK_CD": str}).drop_duplicates())
for f in sorted(FLOW_DIR.glob("flow_time_pop_*.csv")):
    ft.append(pd.read_csv(f, sep="|", dtype={"BLOCK_CD": str}).drop_duplicates())
fa, fw, ft = (pd.concat(x).assign(region=lambda d: d.BLOCK_CD.str[:5].map(FLOW_SGG)) for x in (fa, fw, ft))
acols = [c for c in fa.columns if "FLOW_POP" in c]
wcols = [c for c in fw.columns if c.startswith("FLOW_POP_CNT_")]
tcols = [f"TMST_{h:02d}" for h in range(24)]
for r in REGIONS:
    a = fa[fa.region == r][acols].sum()
    wk = fw[fw.region == r][wcols].sum()
    t = ft[ft.region == r][tcols].sum()
    cells = fa[fa.region == r].groupby("STD_YM").size().mean()
    ind[r].update({
        "유동인구 60대 이상 비중": a[[c for c in acols if c.endswith("60GU")]].sum() / a.sum(),
        "유동인구 주말/평일 비": wk[["FLOW_POP_CNT_SAT", "FLOW_POP_CNT_SUN"]].mean() / wk[wcols[:5]].mean(),
        "유동인구 야간(18~23시) 비중": t[tcols[18:]].sum() / t.sum(),
        "유동인구 집계 격자 수(월평균)": cells,
    })
P = pd.DataFrame(ind)
P.to_csv(OUT / "region_indicators.csv", encoding="utf-8-sig")
fmt = P.copy().astype(object)
for k in P.index:
    for r in REGIONS:
        v = P.at[k, r]
        fmt.at[k, r] = (f"{v:.1%}" if "비중" in k else f"{v:.2f}" if k.endswith("비") else f"{v:,.0f}")

md("# 지역 특성 프로파일 — 강남구 vs 춘천시\n")
md("## 1. 제공 데이터 기반 지표\n")
md("카드: 신한카드 개인 결제·상권 업종(비상권 13개 업종 제외), 2025-07~12. 유동인구: SK 월별 일평균, 격자 합계.\n")
md(fmt.to_markdown())
md()

# 그림 1: 업종군 구성
gs = c1.groupby(["MCT_SGG_CD", "group"]).TS_AT.sum()
gs = (gs / gs.groupby(level=0).transform("sum")).unstack(0).reindex(list(INDUSTRY_GROUPS)).fillna(0)
out = c2.groupby(["MCT_SGG_CD", "group"]).apply(
    lambda s: s[s.CLN_SGG_CD != HOME[s.name[0]]].TS_AT.sum() / s.TS_AT.sum(), include_groups=False).unstack(0)
out = out.reindex(list(INDUSTRY_GROUPS))
fig, axes = plt.subplots(1, 2, figsize=(13, 6))
y = np.arange(len(gs))[::-1]
for i, r in enumerate(REGIONS):
    axes[0].barh(y + (0.5 - i) * 0.38, gs[r] * 100, height=0.36, color=COLOR[r], label=r)
    axes[1].barh(y + (0.5 - i) * 0.38, out[r] * 100, height=0.36, color=COLOR[r], label=r)
axes[0].set_title("업종군별 결제액 구성 (%)", loc="left")
axes[1].set_title("업종군별 타 시·도 거주 고객 결제 비중 (%)", loc="left")
for ax in axes:
    ax.set_yticks(y, gs.index)
    ax.grid(axis="y", visible=False)
axes[0].legend(loc="lower right")
fig.tight_layout()
fig.savefig(OUT / "01_group_mix_visitors.png")
plt.close(fig)
md("![업종군 구성·외지 고객](01_group_mix_visitors.png)\n")
out.to_csv(OUT / "group_visitor_share.csv", encoding="utf-8-sig")

# 그림 2: 요일 패턴 (결제액 vs 유동인구)
fig, axes = plt.subplots(1, 2, figsize=(12, 4), sharey=True)
days = list("월화수목금토일")
for ax, r in zip(axes, REGIONS):
    s = c1[(c1.MCT_SGG_CD == r) & ~c1.date.isin(HOLIDAYS)].groupby("date").TS_AT.sum()
    sv = s.groupby(s.index.dayofweek).mean()
    wk = fw[fw.region == r][wcols].sum()
    ax.plot(days, sv / sv.mean(), color=COLOR[r], marker="o", lw=2, label="결제액")
    ax.plot(days, wk.values / wk.mean(), color=INK2, marker="s", lw=2, ls="--", label="유동인구")
    ax.axhline(1, color=MUTED, lw=1)
    ax.set_title(f"{r} 요일 지수 (평균 = 1)", loc="left")
axes[0].legend()
fig.tight_layout()
fig.savefig(OUT / "02_weekday_sales_flow.png")
plt.close(fig)
md("![요일 패턴](02_weekday_sales_flow.png)\n")

md("""## 2. 지역 유형 해석

| | 서울 강남구 | 강원 춘천시 |
|---|---|---|
| 상권 성격 | 평일 업무·의료·광역 소비 중심지 | 거주민 생활 상권 + 주말 관광·여가 |
| 근거 | 주말 결제·유동이 평일보다 낮음, 타 시·도 고객 비중 높음, 의료 비중 큼 | 토요일 결제 최고, 강원 거주 고객이 대부분, 생활소매·외식·차량 비중 큼 |
| 이동 방식(추정) | 대중교통·지하 연결 공간 비중이 큼 | 자차 이동, 야외 여가(골프·레저) 비중 큼 |
| 날씨 민감도(회귀 결과) | 업종별 신호가 약함 (외식만 비에 유의하게 감소) | 호우 시 야외·레저, 패션, 차량, 외식, 생활소매 유의하게 감소 |

- 강남은 외지 고객과 업무 목적 소비 비중이 커서 소비가 날씨에 따라 미뤄지거나 취소되기 어렵다.
  지하상가·대형 실내 시설이 많은 구조도 날씨 영향을 완충하는 것으로 보인다.
- 춘천은 소비가 거주민의 자차 이동과 야외 여가에 기대고 있어, 비가 오면 외출 자체가 줄면서 매출이 바로 감소한다.
- 그래서 **같은 날씨라도 지역 유형에 따라 피해가 다르게 나타난다**. 취약도 지수는 지역별로 따로 계산하고,
  '외지 고객 의존도'와 '야외·이동형 업종 비중'을 지역 특성 변수로 반영한다.

## 3. 외부 참고 자료 (공개 자료, 맥락 설명용)

- 2025년은 연평균기온 13.7℃로 관측 이래 두 번째로 더운 해였고, 여름철 전국 평균기온 25.7℃는 역대 1위였다
  (기상청 '2025년 기후특성' 보도 인용 기사: [베지뉴스](https://www.vegannews.co.kr/news/article.html?no=381333),
  [헤럴드경제](https://www.heraldk.com/article/2026010517011401751)).
- 서울의 2025년 여름 열대야는 46일로 역대 1위로 보도되었다. 서울 열대야 평년값(1991~2020)은 연 12.5일이다
  ([Korea JoongAng Daily](https://www.koreajoongangdaily.com/korea/no-relief-even-after-dark-record-tropical-nights-add-to-koreas-heat-crisis/12810767)).
- 2025년 7월 16~20일 전국 집중호우(호우 긴급재난문자 161건), 8월 13일 수도권 시간당 100mm 극한호우가 있었다
  ([서울신문](https://m.seoul.co.kr/news/2025/08/13/20250813500194)).
- 강남구 사업체 수는 10만 7,804개(2022년 기준)로 서울 자치구 중 가장 많다
  ([강남구청 보도자료](https://www.gangnam.go.kr/board/B_000031/1073493/view.do?mid=ID01)).
- 춘천 원도심 상권은 명동·중앙시장(낭만시장)·닭갈비골목이 이어진 구조이고, 남춘천역 풍물시장은 5일장(2·7일)으로 운영된다
  ([서울신문 2010](https://m.go.seoul.co.kr/news/2010/04/30/20100430025034),
  [뉴스토마토](https://newstomato.com/ReadNews.aspx?no=782670)). 전통시장·5일장은 야외 노출형이라 호우에 취약할 가능성이 크다
  (카드 데이터는 시군구·업종 단위라 시장 단위로 직접 검증할 수는 없음).

※ 외부 자료는 지역 맥락 설명에만 쓰고, 모형 입력에는 제공 데이터와 기상청 관측자료만 사용했다.
""")

(OUT / "summary.md").write_text("\n".join(log), encoding="utf-8")
