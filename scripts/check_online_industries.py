"""강남 '컴퓨터/소프트웨어'·'쇼핑몰' 업종 점검.

두 업종이 강남 개인 결제액의 약 19%를 차지한다. 지역 상권의 매장 매출인지,
본사 소재지 기준으로 잡히는 결제(통신판매·대형 단일 사업자 등)인지 판단하기 위해
일반 상권 업종과 행태 지표를 비교한다.

실행: uv run --no-project --with pandas --with matplotlib --with tabulate python -X utf8 scripts/check_online_industries.py
"""
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
CARD_DIR = ROOT / "2026빅콘테스트_신한카드_데이터_레이아웃"
OUT = ROOT / "outputs" / "industry_check"
OUT.mkdir(parents=True, exist_ok=True)

TARGETS = ["컴퓨터/소프트웨어", "쇼핑몰"]
# 비교 대상: 매장 방문형 대표 업종
REFS = ["할인점/슈퍼마켓/양판점", "백화점", "한식", "커피전문점", "의복/의류", "가전", "일반병원"]
HOLIDAYS = pd.to_datetime(["2025-08-15", "2025-10-03", "2025-10-05", "2025-10-06",
                           "2025-10-07", "2025-10-08", "2025-10-09", "2025-12-25"])
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


card1 = pd.read_csv(CARD_DIR / "신한카드_빅콘테스트2026_데이터1.txt", sep="\t", encoding="cp949",
                    dtype={"TA_YMD": str})
card2 = pd.read_csv(CARD_DIR / "신한카드_빅콘테스트2026_데이터2.txt", sep="\t", encoding="cp949",
                    dtype={"TA_YMD": str})
for d in (card1, card2):
    d["date"] = pd.to_datetime(d.TA_YMD, format="%Y%m%d")
p1 = card1[card1.SEX_CCD != "법인"]
inds = TARGETS + REFS

md("# 강남 '컴퓨터/소프트웨어'·'쇼핑몰' 업종 점검\n")
md("데이터 레이아웃상 카드 데이터는 **오프라인 결제건 한정**이다. 따라서 온라인 결제 여부가 아니라 "
   "'강남구 지역 상권의 매장 매출로 볼 수 있는가'를 일반 상권 업종과 비교해 판단한다.\n")


def profile(region):
    s = p1[(p1.MCT_SGG_CD == region) & p1.MCT_RY_CD.isin(inds)]
    tot = p1[p1.MCT_SGG_CD == region].TS_AT.sum()
    daily = s.groupby(["MCT_RY_CD", "date"]).agg(TS_AT=("TS_AT", "sum"), USE_CNT=("USE_CNT", "sum")).reset_index()
    daily["hol"] = daily.date.isin(HOLIDAYS)
    daily["dow"] = daily.date.dt.dayofweek
    rows = {}
    for ind, g in daily.groupby("MCT_RY_CD"):
        wkday = g[(g.dow < 5) & ~g.hol].TS_AT.mean()
        tb = s[s.MCT_RY_CD == ind].groupby("TIME_GB").TS_AT.sum()
        tb = tb / tb.sum()
        rows[ind] = {
            "결제액 비중": g.TS_AT.sum() / tot,
            "건당금액(만원)": g.TS_AT.sum() / g.USE_CNT.sum() / 1e4,
            "00~05시 비중": tb.get("00_05", 0),
            "18~23시 비중": tb.get("18_23", 0),
            "일요일/평일": g[(g.dow == 6) & ~g.hol].TS_AT.mean() / wkday,
            "공휴일/평일": g[g.hol].TS_AT.mean() / wkday,
            "일매출 변동계수": g.TS_AT.std() / g.TS_AT.mean(),
            "최대일/중앙값": g.TS_AT.max() / g.TS_AT.median(),
        }
    return pd.DataFrame(rows).T.loc[[i for i in inds if i in rows]]


gn = profile("서울 강남구")
cc = profile("강원 춘천시")
gn.to_csv(OUT / "profile_gangnam.csv", encoding="utf-8-sig")
md("## 1. 행태 지표 비교 (강남, 개인 결제)\n")
md(gn.round(3).to_markdown())
md("\n같은 지표, 춘천:\n")
md(cc.round(3).to_markdown())
md()

# 고객 거주지: 매장형 업종은 인근(서울·경기) 비중이 높고, 본사 소재지 결제는 전국 인구 분포에 가까워짐
md("## 2. 고객 거주지 구성 (데이터2)\n")
r2 = card2[(card2.MCT_SGG_CD == "서울 강남구") & card2.MCT_RY_CD.isin(inds)]
res = r2.groupby(["MCT_RY_CD", "CLN_SGG_CD"]).TS_AT.sum().unstack(0)
res = res / res.sum()
cap = res.loc[["서울", "경기", "인천"]].sum()
res_tab = pd.DataFrame({"서울": res.loc["서울"], "수도권(서울·경기·인천)": cap,
                        "비수도권": 1 - cap}).loc[[i for i in inds if i in res.columns]]
res_tab.to_csv(OUT / "residence_gangnam.csv", encoding="utf-8-sig")
md(res_tab.round(3).to_markdown())
md()

# 매출 급등일: 특정 날짜 몰림은 단일 대형 사업자(신제품 출시, 대량 결제 등)의 신호
md("## 3. 매출 급등일 (강남)\n")
gd = p1[(p1.MCT_SGG_CD == "서울 강남구")].groupby(["MCT_RY_CD", "date"]).agg(
    TS_AT=("TS_AT", "sum"), USE_CNT=("USE_CNT", "sum")).reset_index()
for ind in TARGETS:
    g = gd[gd.MCT_RY_CD == ind].copy()
    g["중앙값 대비"] = g.TS_AT / g.TS_AT.median()
    g["건당(만원)"] = g.TS_AT / g.USE_CNT / 1e4
    top = g.nlargest(5, "TS_AT")[["date", "TS_AT", "USE_CNT", "건당(만원)", "중앙값 대비"]]
    top["date"] = top.date.dt.strftime("%Y-%m-%d (%a)")
    top["TS_AT"] = (top.TS_AT / 1e8).round(1)
    md(f"**{ind}** 상위 5일 (결제액 억원)\n")
    md(top.rename(columns={"TS_AT": "결제액(억)"}).round(2).to_markdown(index=False))
    md()

# 연령 구성
age = p1[(p1.MCT_SGG_CD == "서울 강남구") & p1.MCT_RY_CD.isin(inds)].groupby(
    ["MCT_RY_CD", "AGE_CCD"]).TS_AT.sum().unstack(0)
age = (age / age.sum()).T.loc[[i for i in inds if i in age.columns]]

# ---------------------------------------------------------------- 그림
fig, axes = plt.subplots(2, 1, figsize=(11, 6.5), sharex=True)
for ax, ind, c in zip(axes, TARGETS, ["#2a78d6", "#eb6834"]):
    g = gd[gd.MCT_RY_CD == ind]
    ax.plot(g.date, g.TS_AT / 1e8, color=c, lw=1.3)
    h = g[g.date.isin(HOLIDAYS)]
    ax.scatter(h.date, h.TS_AT / 1e8, s=34, color="#e34948", zorder=3, edgecolor="#fcfcfb", linewidth=1.5,
               label="공휴일")
    ax.set_title(f"강남 {ind} 일별 개인 결제액 (억원)", loc="left")
    ax.set_ylim(bottom=0)
axes[0].legend(loc="upper left")
fig.savefig(OUT / "01_daily_targets.png")
plt.close(fig)
md("![일별 추이](01_daily_targets.png)\n")

fig, axes = plt.subplots(1, 2, figsize=(12, 4.5))
lab = list(gn.index)
y = np.arange(len(lab))[::-1]
colors = ["#eb6834" if i in TARGETS else "#86b6ef" for i in lab]
axes[0].barh(y, gn["건당금액(만원)"], color=colors, height=0.65)
axes[0].set_title("건당 결제금액 (만원)", loc="left")
axes[1].barh(y, res_tab["비수도권"] * 100, color=colors, height=0.65)
axes[1].set_title("비수도권 거주 고객 결제 비중 (%)", loc="left")
for ax in axes:
    ax.set_yticks(y, lab)
    ax.grid(axis="y", visible=False)
fig.tight_layout()
fig.savefig(OUT / "02_ticket_residence.png")
plt.close(fig)
md("![건당금액·거주지](02_ticket_residence.png)\n")
md("주황 = 점검 대상, 파랑 = 비교용 매장형 업종\n")

md("## 4. 연령 구성 (강남)\n")
md(age.round(3).to_markdown())
md()

md("""## 5. 판단

| 근거 | 컴퓨터/소프트웨어 | 쇼핑몰 | 매장형 업종 |
|---|---|---|---|
| 00~05시 결제 비중 | 16% | 7% | 0~5% (한식 4.8%) |
| 공휴일/평일 | 1.05 (휴일에도 그대로) | 0.64 | 1.0~1.2 (유통) |
| 비수도권 고객 비중 | 41% | 40% | 6~15% (백화점·한식·의류·병원) |
| 급등일 | 매월 1일 (7/1, 9/1, 10/1, 11/1) | 11/1~3, 11/11 할인행사 기간 | 공휴일·주말 |
| 하루 결제건수 | 약 40만~47만 건 | 약 20만 건 | - |

- **컴퓨터/소프트웨어**: 새벽 결제, 매월 1일 급등, 전국 고객 구성 → 정기결제·구독형 과금이
  강남 소재 사업자 기준으로 집계된 것으로 판단. 지역 상권 매출이 아님.
- **쇼핑몰**: 대형 할인행사 기간 급등, 공휴일 감소, 전국 고객 구성 → 통신판매형 사업자의
  결제로 판단. 지역 상권 매출이 아님.
- 결론: 두 업종을 상권 분석에서 **제외**한다 (`scripts/common.py`의 `NON_COMMERCE`에 추가).
- 참고: 강남 '할인점/슈퍼마켓/양판점'(비수도권 36%)과 '커피전문점'(28%)도 외지 고객 비중이 높지만
  새벽 결제가 거의 없고 주말·공휴일 패턴이 매장형이라 유지한다. 체인 본사 집계가 일부 섞였을 수 있어
  해석 시 유의.
""")

(OUT / "summary.md").write_text("\n".join(log), encoding="utf-8")
