// 인사이트 2 장표: 춘천 레저·숙박은 비 오는 날 가장 약한 상권
// 데이터: outputs/chuncheon_leisure_lodging/slides_data.json (scripts/chuncheon_leisure_lodging.py가 생성)
// 실행: NODE_PATH=<pptxgenjs가 설치된 node_modules> node docs/slides/build_insight2.js
const path = require("path");
const fs = require("fs");
const pptxgen = require("pptxgenjs");

const ROOT = path.resolve(__dirname, "..", "..");
const D = JSON.parse(fs.readFileSync(path.join(ROOT, "outputs/chuncheon_leisure_lodging/slides_data.json"), "utf8"));
const OUT = path.join(__dirname, "insight2_leisure_lodging.pptx");
const APPLY_THEME = process.env.PPTX_APPLY_THEME;

const THEME = {
  name: "Chuncheon Rain",
  headFontFace: "Malgun Gothic",
  bodyFontFace: "Malgun Gothic",
  colors: {
    dk1: "1D2B33", lt1: "FFFFFF", dk2: "15303D", lt2: "EEF2F5",
    accent1: "D9622B", accent2: "2F6FA8", accent3: "C5CBD1", accent4: "E9A27F",
    accent5: "5B7083", accent6: "8FB4D6", hlink: "2F6FA8", folHlink: "5B7083",
  },
};
const HEX = { orange: "D9622B", blue: "2F6FA8", gray: "C5CBD1", lightOrange: "E9A27F", ink: "1D2B33",
              muted: "6B7780", grid: "E3E7EA", dark: "15303D", tint: "F3F6F8" };

const pct = (v, d = 0) => `${v < 0 ? "-" : v > 0 ? "+" : ""}${Math.abs(v * 100).toFixed(d)}%`;
// 피해율 구간(lo, hi) → 매출 변화 구간, 작은 값부터
const ci = (lo, hi) => `${pct(-hi)} ~ ${pct(-lo)}`;
const chg = (loss) => -loss; // 피해율(양수 = 감소) → 매출 변화율(음수 = 감소)
const G = Object.fromEntries(D.groups.map((g) => [g.name, g]));
const S = Object.fromEntries(D.sub.map((s) => [s.name, s]));
const LABEL = {
  "실내/실외골프장": "골프장(실내·실외)", "종합레저타운/놀이동산": "레저타운·놀이동산", "스포츠시설": "스포츠시설",
  "헬스장": "헬스장", "싸우나/목욕탕": "사우나·목욕탕", "호텔/콘도": "호텔·콘도", "모텔,여관,기타숙박": "모텔·여관",
  "고속버스/철도/여객선": "고속버스·철도·여객선",
};
const SOURCE = "자료: 신한카드 춘천 개인 결제(2025.7~12, 상권 업종), 기상청 ASOS 춘천 · 주·요일·공휴일·폭염 통제 회귀";

const pres = new pptxgen();
pres.layout = "LAYOUT_WIDE"; // 13.333 x 7.5
pres.theme = { headFontFace: THEME.headFontFace, bodyFontFace: THEME.bodyFontFace };
pres.title = "인사이트 2 — 춘천 레저·숙박의 비 피해";
const C = pres.SchemeColor;

pres.defineSlideMaster({
  title: "SECTION",
  background: { color: HEX.dark },
  objects: [
    { placeholder: { options: { name: "title", type: "title", x: 0.8, y: 1.5, w: 11.7, h: 2.0, fontSize: 44, bold: true, align: "left",
                                color: C.background1, valign: "bottom", margin: 0 }, text: "" } },
    { placeholder: { options: { name: "body", type: "body", x: 0.8, y: 3.7, w: 11.7, h: 0.6, fontSize: 20,
                                color: "C8D6DF", margin: 0 }, text: "" } },
  ],
});
pres.defineSlideMaster({
  title: "CONTENT",
  background: { color: "FFFFFF" },
  margin: [0.5, 0.6, 0.6, 0.6],
  objects: [
    { text: { text: "인사이트 2 · 레저·숙박의 비 피해", options: { x: 0.6, y: 0.35, w: 8, h: 0.3, fontSize: 12, bold: true,
                                                                color: C.accent1, margin: 0 } } },
    { placeholder: { options: { name: "title", type: "title", x: 0.6, y: 0.7, w: 12.1, h: 0.9, fontSize: 30, bold: true, align: "left",
                                color: C.text1, valign: "top", margin: 0 }, text: "" } },
    { text: { text: SOURCE, options: { x: 0.6, y: 6.95, w: 11, h: 0.3, fontSize: 10, color: HEX.muted, margin: 0 } } },
  ],
  slideNumber: { x: 12.3, y: 6.95, w: 0.5, h: 0.3, fontSize: 10, color: HEX.muted, align: "right" },
});

pres.addSection({ title: "인사이트 2" });
const SEC = "인사이트 2";

const AXIS = { catAxisLabelColor: HEX.ink, valAxisLabelColor: HEX.muted, catAxisLabelFontFace: "+mn-lt",
               valAxisLabelFontFace: "+mn-lt", catAxisLabelFontSize: 12, valAxisLabelFontSize: 10,
               valGridLine: { color: HEX.grid, size: 0.75 }, catGridLine: { style: "none" },
               dataLabelFontFace: "+mn-lt", dataLabelFontSize: 11, dataLabelColor: HEX.ink,
               valAxisLabelFormatCode: "0%", dataLabelFormatCode: "+0%;-0%;0%", catAxisLineShow: false,
               valAxisLineShow: false };

function caption(slide, text, x, y, w) {
  slide.addText(text, { x, y, w, h: 0.35, fontSize: 13, bold: true, color: HEX.ink, margin: 0, isTextBox: true,
                        objectName: "chart caption" });
}

// ---------------------------------------------------------------- 1. 섹션 표지
{
  const s = pres.addSlide({ masterName: "SECTION", sectionTitle: SEC });
  s.addText("춘천 레저·숙박은\n비 오는 날 가장 약한 상권", { placeholder: "title" });
  s.addText("인사이트 2 · 업종별 비 피해와 회복", { placeholder: "body" });
  const chips = [
    [pct(chg(G["야외·레저"].loss)), "야외·레저", "비 10mm+ 날 매출 변화"],
    [pct(chg(G["숙박·여행"].cum)), "숙박·여행", "비 온 뒤 3일 누적 변화"],
    [pct(chg(G["생활소매"].cum), 1), "생활소매", "3일 누적: 다음 날 회복"],
  ];
  chips.forEach(([v, name, desc], i) => {
    const x = 0.8 + i * 3.9;
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y: 4.85, w: 3.6, h: 1.55, rectRadius: 0.12,
      fill: { color: "1F4252" }, line: { color: "1F4252" }, objectName: `stat card ${i + 1}` });
    s.addText(v, { x: x + 0.3, y: 4.98, w: 3.0, h: 0.75, fontSize: 36, bold: true, margin: 0, isTextBox: true,
                   color: i < 2 ? "F08A57" : "9CC3E6" });
    s.addText([{ text: name, options: { bold: true, breakLine: true } }, { text: desc }],
              { x: x + 0.3, y: 5.72, w: 3.1, h: 0.6, fontSize: 13, color: "DCE6EC", margin: 0, isTextBox: true });
  });
  s.addNotes("인사이트 1에서 비가 오면 춘천 상권 전체 매출이 줄어든다는 걸 봤습니다. 이번에는 '어떤 업종이 가장 약한가'입니다. " +
    "결론부터 말씀드리면, 야외·레저는 비 오는 당일 매출이 40% 줄어 업종 중 가장 크게 떨어지고, 숙박은 비 온 뒤 사흘에 걸쳐 손실이 쌓입니다. " +
    "반대로 생활소매는 다음 날 장보기로 손실을 거의 다 메웁니다.");
}

// ---------------------------------------------------------------- 2. 분석 설계 · 컬럼 선택
{
  const s = pres.addSlide({ masterName: "CONTENT", sectionTitle: SEC });
  s.addText("어떤 컬럼으로, 어떻게 비교했나", { placeholder: "title" });
  const hdr = (t) => ({ text: t, options: { bold: true, color: "FFFFFF", fill: { color: HEX.dark } } });
  const rows = [
    [hdr("컬럼"), hdr("의미"), hdr("이 분석에서 쓴 이유")],
    ["TA_YMD", "결제일", "일별 기상 관측과 날짜로 1:1 연결"],
    ["MCT_RY_CD", "가맹점 업종", "업종군 12개, 레저·숙박 세부 업종 9개를 직접 비교"],
    ["TS_AT", "결제 금액", "피해를 매출 금액으로 보기 위해 사용"],
    ["CLN_SGG_CD", "고객 거주 시도 (데이터2)", "외지 관광객과 강원 고객을 나눠 누가 빠지는지 확인"],
    ["일강수량 · 최고기온", "기상청 ASOS 춘천", "비 10mm+ 여부, 폭염 날 통제"],
  ];
  s.addTable(rows, { x: 0.6, y: 1.85, w: 7.7, colW: [2.0, 2.2, 3.5], fontSize: 13, color: HEX.ink,
    border: { type: "solid", pt: 0.75, color: HEX.grid }, rowH: 0.62, valign: "middle", margin: 0.08,
    objectName: "column table" });
  s.addText("법인 결제와 비상권 업종 13개는 제외 (전처리 장 참고)", { x: 0.6, y: 5.75, w: 7.7, h: 0.35, fontSize: 12,
    color: HEX.muted, margin: 0, isTextBox: true });

  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: 8.8, y: 1.85, w: 3.95, h: 4.25, rectRadius: 0.1,
    fill: { color: HEX.tint }, line: { color: HEX.tint }, objectName: "definition card" });
  const items = [
    ["비 피해율", "비 10mm+ 온 날의 매출 변화 (비 안 온 날 대비)"],
    ["같이 통제", "같은 주 · 요일 · 공휴일(추석 연휴) · 폭염"],
    ["회복", "비 온 뒤 1~3일 효과까지 더한 누적 변화"],
  ];
  items.forEach(([h, b], i) => {
    const y = 2.1 + i * 1.3;
    s.addShape(pres.shapes.OVAL, { x: 9.05, y, w: 0.5, h: 0.5, fill: { color: HEX.orange }, line: { color: HEX.orange },
                                   objectName: `step ${i + 1}` });
    s.addText(String(i + 1), { x: 9.05, y, w: 0.5, h: 0.5, fontSize: 16, bold: true, color: "FFFFFF", align: "center",
                               valign: "middle", margin: 0, isTextBox: true });
    s.addText([{ text: h, options: { bold: true, fontSize: 15, breakLine: true } }, { text: b, options: { fontSize: 13 } }],
              { x: 9.75, y: y - 0.05, w: 2.85, h: 1.1, color: HEX.ink, valign: "top", margin: 0, isTextBox: true });
  });
  s.addNotes("분석에 쓴 컬럼과 이유입니다. 날짜(TA_YMD)로 기상과 연결하고, 업종(MCT_RY_CD)으로 업종을 비교했고, 결제금액(TS_AT)으로 피해를 금액 기준으로 봤습니다. " +
    "데이터2의 고객 거주지(CLN_SGG_CD)로 외지 관광객과 강원 고객을 나눴습니다. " +
    "비 피해율은 비가 10mm 넘게 온 날 매출이 비 안 온 날보다 얼마나 낮은지입니다. 같은 주, 요일, 공휴일, 폭염 효과는 빼고 비교했습니다. " +
    "회복은 비 온 뒤 1~3일까지의 효과를 더한 누적값으로 봤습니다.");
}

// ---------------------------------------------------------------- 3. 업종군 비 피해
{
  const s = pres.addSlide({ masterName: "CONTENT", sectionTitle: SEC });
  s.addText("비 오는 날 야외·레저 매출 40% 감소, 업종 중 최대", { placeholder: "title" });
  const gs = D.groups; // 피해율 큰 순
  const colors = gs.map((g) => (g.name === "야외·레저" ? HEX.orange : g.name === "숙박·여행" ? HEX.lightOrange : HEX.gray));
  caption(s, "업종군별 비 10mm+ 날 매출 변화 (비 안 온 날 대비)", 0.6, 1.75, 7.9);
  s.addChart(pres.charts.BAR, [{ name: "매출 변화", labels: gs.map((g) => g.name), values: gs.map((g) => chg(g.loss)) }], {
    x: 0.5, y: 2.1, w: 8.0, h: 4.7, barDir: "bar", catAxisOrientation: "maxMin", valAxisMinVal: -0.5, valAxisMaxVal: 0,
    valAxisMajorUnit: 0.1, chartColors: colors, showValue: true, dataLabelPosition: "outEnd", showLegend: false,
    barGapWidthPct: 45, ...AXIS, catAxisLabelPos: "low", objectName: "group rain chart" });

  const L = G["야외·레저"];
  s.addText(pct(chg(L.loss)), { x: 9.0, y: 1.95, w: 3.7, h: 1.1, fontSize: 64, bold: true, color: HEX.orange, margin: 0,
                                isTextBox: true });
  s.addText([{ text: "야외·레저", options: { bold: true, breakLine: true } },
             { text: "비 10mm+ 날 매출 변화", options: { breakLine: true } },
             { text: `95% 구간 ${ci(L.lo, L.hi)}`, options: { color: HEX.muted, fontSize: 12 } }],
            { x: 9.0, y: 3.05, w: 3.75, h: 0.95, fontSize: 14, color: HEX.ink, margin: 0, isTextBox: true });
  s.addText([
    { text: "매출 절반을 차지하는 외식·생활소매보다 6~8배 큰 감소",
      options: { bullet: true, breakLine: true } },
    { text: `숙박·여행 ${pct(chg(G["숙박·여행"].loss))}은 당일만 보면 불확실하지만, 비 온 뒤 며칠에 걸쳐 손실이 드러남 (다음 장)`,
      options: { bullet: true } },
  ], { x: 9.0, y: 4.15, w: 3.75, h: 2.4, fontSize: 14, color: HEX.ink, margin: 0, paraSpaceAfter: 8, valign: "top",
       isTextBox: true });
  s.addNotes(`업종군 12개를 비교한 결과입니다. 비가 10mm 넘게 오는 날 야외·레저 매출은 40% 줄어, 다른 업종보다 압도적으로 큽니다. ` +
    `95% 신뢰구간도 ${ci(L.lo, L.hi)}로 확실합니다. 춘천 매출의 절반을 차지하는 외식과 생활소매는 5~7% 정도 줄어듭니다. ` +
    `숙박·여행은 당일 ${pct(chg(G["숙박·여행"].loss))}로 통계적으로는 불확실한데, 다음 장에서 보듯 비 온 뒤 며칠에 걸쳐 손실이 커집니다.`);
}

// ---------------------------------------------------------------- 4. 회복
{
  const s = pres.addSlide({ masterName: "CONTENT", sectionTitle: SEC });
  s.addText("레저는 당일에, 숙박은 며칠에 걸쳐 무너지고 회복하지 못한다", { placeholder: "title" });
  const names = ["야외·레저", "숙박·여행", "외식", "생활소매"];
  caption(s, "비 10mm+ 날 매출 변화: 당일 vs 3일 뒤까지 누적", 0.6, 1.75, 7.9);
  s.addChart(pres.charts.BAR, [
    { name: "비 온 당일", labels: names, values: names.map((n) => chg(G[n].day0)) },
    { name: "3일 뒤까지 누적", labels: names, values: names.map((n) => chg(G[n].cum)) },
  ], { x: 0.5, y: 2.1, w: 8.0, h: 4.7, barDir: "col", barGrouping: "clustered", valAxisMinVal: -0.5, valAxisMaxVal: 0.05,
       valAxisMajorUnit: 0.1, chartColors: [HEX.blue, HEX.orange], showValue: true, dataLabelPosition: "outEnd",
       showLegend: true, legendPos: "t", legendFontFace: "+mn-lt", legendFontSize: 12, legendColor: HEX.ink,
       barGapWidthPct: 60, catAxisLabelPos: "high", ...AXIS, dataLabelFormatCode: "+0.0%;-0.0%;0%",
       objectName: "recovery chart" });
  const rows = [
    ["야외·레저", `${pct(chg(G["야외·레저"].day0), 1)} → ${pct(chg(G["야외·레저"].cum), 1)}`, "잃은 손님이 돌아오지 않음", HEX.orange],
    ["숙박·여행", `${pct(chg(G["숙박·여행"].day0), 1)} → ${pct(chg(G["숙박·여행"].cum), 1)}`, "취소가 이어져 손실이 커짐", HEX.orange],
    ["생활소매", `${pct(chg(G["생활소매"].day0), 1)} → ${pct(chg(G["생활소매"].cum), 1)}`, "다음 날 장보기로 회복", HEX.blue],
  ];
  rows.forEach(([n, v, d, col], i) => {
    const y = 1.95 + i * 1.45;
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: 9.0, y, w: 3.75, h: 1.25, rectRadius: 0.1, fill: { color: HEX.tint },
                                                line: { color: HEX.tint }, objectName: `recovery card ${i + 1}` });
    s.addText([{ text: n, options: { bold: true, fontSize: 14, color: HEX.ink, breakLine: true } },
               { text: v, options: { bold: true, fontSize: 20, color: col, breakLine: true } },
               { text: d, options: { fontSize: 13, color: HEX.ink } }],
              { x: 9.2, y: y + 0.08, w: 3.4, h: 1.1, margin: 0, valign: "top", isTextBox: true });
  });
  s.addText(`누적 95% 구간
야외·레저 ${ci(G["야외·레저"].cum_lo, G["야외·레저"].cum_hi)} · ` +
            `숙박·여행 ${ci(G["숙박·여행"].cum_lo, G["숙박·여행"].cum_hi)}`,
            { x: 9.0, y: 6.3, w: 3.8, h: 0.5, fontSize: 10, color: HEX.muted, margin: 0, isTextBox: true });
  s.addNotes("비 온 뒤 회복을 본 장입니다. 파란 막대는 비 온 당일, 주황 막대는 그 뒤 사흘까지 더한 누적 변화입니다. " +
    "생활소매는 당일 5% 줄지만 다음 날 장보기로 거의 다 메워 누적으로는 0에 가깝습니다. 손님이 날짜만 미룬 겁니다. " +
    "야외·레저는 당일 40% 빠진 뒤 그대로입니다. 비 때문에 취소한 골프나 나들이는 다시 오지 않는다는 뜻입니다. " +
    "숙박·여행은 당일보다 그 뒤가 더 나빠 누적 38% 감소입니다. 비 예보로 이어지는 예약 취소로 보입니다. " +
    "그래서 레저와 숙박은 손실이 사라지는 업종, 즉 지원이 필요한 업종입니다.");
}

// ---------------------------------------------------------------- 5. 세부 업종
{
  const s = pres.addSlide({ masterName: "CONTENT", sectionTitle: SEC });
  s.addText("피해는 골프장·레저타운·교통에 집중, 사우나는 오히려 늘었다", { placeholder: "title" });
  const subs = D.sub.filter((r) => LABEL[r.name]).sort((a, b) => b.loss - a.loss);
  const col = (r) => (r.p < 0.05 ? (r.loss > 0 ? HEX.orange : HEX.blue) : HEX.gray);
  caption(s, "레저·숙박 세부 업종별 비 10mm+ 날 매출 변화", 0.6, 1.75, 7.9);
  s.addChart(pres.charts.BAR, [{ name: "매출 변화", labels: subs.map((r) => LABEL[r.name]), values: subs.map((r) => chg(r.loss)) }], {
    x: 0.5, y: 2.1, w: 8.0, h: 4.7, barDir: "bar", catAxisOrientation: "maxMin", valAxisMinVal: -0.7, valAxisMaxVal: 0.3,
    valAxisMajorUnit: 0.1, chartColors: subs.map(col), showValue: true, dataLabelPosition: "outEnd", showLegend: false,
    barGapWidthPct: 45, catAxisLabelPos: "low", ...AXIS, objectName: "subindustry chart" });

  const keys = [[HEX.orange, "뚜렷한 감소"], [HEX.gray, "차이 불확실"], [HEX.blue, "뚜렷한 증가"]];
  keys.forEach(([c, t], i) => {
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: 9.0 + i * 1.27, y: 1.95, w: 0.28, h: 0.28, rectRadius: 0.05,
                                                fill: { color: c }, line: { color: c }, objectName: `key ${i + 1}` });
    s.addText(t, { x: 9.33 + i * 1.27, y: 1.9, w: 0.95, h: 0.38, fontSize: 11, color: HEX.ink, margin: 0, isTextBox: true });
  });
  const o = (n) => pct(S[n].outsider).replace("+", "");
  s.addText([
    { text: `감소 업종은 외지 고객 비중이 높음: 골프장 ${o("실내/실외골프장")}, 레저타운 ${o("종합레저타운/놀이동산")}, 교통 ${o("고속버스/철도/여객선")}`,
      options: { bullet: true, breakLine: true } },
    { text: `동네 주민 시설은 영향 없음: 헬스장(외지 ${o("헬스장")}), 스포츠시설(${o("스포츠시설")})`,
      options: { bullet: true, breakLine: true } },
    { text: `사우나·목욕탕 ${pct(chg(S["싸우나/목욕탕"].loss))}: 비가 오면 실내로 이동`, options: { bullet: true } },
  ], { x: 9.0, y: 2.55, w: 3.75, h: 3.3, fontSize: 14, color: HEX.ink, margin: 0, paraSpaceAfter: 10, valign: "top",
       isTextBox: true });
  s.addText("여행사·항공사는 결제일이 적어 제외. 숙박 카드 결제는 앱 선결제가 빠진 현장 결제 위주", {
    x: 9.0, y: 6.05, w: 3.8, h: 0.7, fontSize: 10, color: HEX.muted, margin: 0, isTextBox: true });
  s.addNotes("레저와 숙박 안을 업종별로 쪼갠 결과입니다. 주황은 뚜렷하게 줄어든 업종, 회색은 차이가 불확실한 업종, 파랑은 뚜렷하게 늘어난 업종입니다. " +
    "골프장은 58%, 고속버스·철도는 47%, 레저타운·놀이동산은 45% 줄었습니다. 세 업종 모두 외지 고객 비중이 80% 안팎입니다. " +
    "반대로 헬스장과 스포츠시설처럼 동네 주민이 쓰는 곳은 비의 영향이 없습니다. " +
    `사우나는 오히려 ${pct(chg(S["싸우나/목욕탕"].loss)).replace("+", "")} 늘었습니다. 비가 오면 관광객이 아예 안 오는 게 아니라 실내로 옮겨 간다는 신호입니다. ` +
    "호텔·콘도도 21% 줄었지만 결제가 들쭉날쭉해 통계적으로는 불확실합니다. 숙박은 앱 선결제가 데이터에서 빠지는 한계도 있습니다.");
}

// ---------------------------------------------------------------- 6. 외지 vs 강원
{
  const s = pres.addSlide({ masterName: "CONTENT", sectionTitle: SEC });
  s.addText("외지 관광객이 더 크게 빠지고, 비가 오면 실내로 옮겨 간다", { placeholder: "title" });
  const names = ["실내/실외골프장", "종합레저타운/놀이동산", "싸우나/목욕탕"];
  caption(s, "고객 거주지별 비 10mm+ 날 매출 변화", 0.6, 1.75, 7.9);
  s.addChart(pres.charts.BAR, [
    { name: "강원 고객", labels: names.map((n) => LABEL[n]), values: names.map((n) => chg(S[n]["강원_피해율"])) },
    { name: "외지 고객", labels: names.map((n) => LABEL[n]), values: names.map((n) => chg(S[n]["외지_피해율"])) },
  ], { x: 0.5, y: 2.1, w: 8.0, h: 4.7, barDir: "col", barGrouping: "clustered", valAxisMinVal: -0.8, valAxisMaxVal: 0.6,
       valAxisMajorUnit: 0.2, chartColors: [HEX.blue, HEX.orange], showValue: true, dataLabelPosition: "outEnd",
       showLegend: true, legendPos: "t", legendFontFace: "+mn-lt", legendFontSize: 12, legendColor: HEX.ink,
       barGapWidthPct: 60, catAxisLabelPos: "low", ...AXIS, objectName: "residence chart" });
  const g = S["실내/실외골프장"], sa = S["싸우나/목욕탕"];
  const cards = [
    ["골프장", `강원 ${pct(chg(g["강원_피해율"]))} · 외지 ${pct(chg(g["외지_피해율"]))}`, "외지 관광객이 더 크게 취소", HEX.orange],
    ["사우나·목욕탕", `강원 ${pct(chg(sa["강원_피해율"]))} · 외지 ${pct(chg(sa["외지_피해율"]))}`, "비 오는 날 외지 관광객이 실내로", HEX.blue],
    ["레저타운·놀이동산", "강원·외지 모두 약 -45%", "고객 대부분(80%)이 외지", HEX.orange],
  ];
  cards.forEach(([n, v, d, c], i) => {
    const y = 1.95 + i * 1.45;
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: 9.0, y, w: 3.75, h: 1.25, rectRadius: 0.1, fill: { color: HEX.tint },
                                                line: { color: HEX.tint }, objectName: `residence card ${i + 1}` });
    s.addText([{ text: n, options: { bold: true, fontSize: 14, color: HEX.ink, breakLine: true } },
               { text: v, options: { bold: true, fontSize: 17, color: c, breakLine: true } },
               { text: d, options: { fontSize: 13, color: HEX.ink } }],
              { x: 9.2, y: y + 0.08, w: 3.4, h: 1.1, margin: 0, valign: "top", isTextBox: true });
  });
  s.addText(`강원 고객 = 강원도 거주(춘천 밖 포함). 사우나 외지 고객 95% 구간 ${ci(sa["외지_하한"], sa["외지_상한"])}로 넓음`,
            { x: 9.0, y: 6.3, w: 3.8, h: 0.5, fontSize: 10, color: HEX.muted, margin: 0, isTextBox: true });
  s.addNotes("같은 업종 안에서 고객이 어디 사는지에 따라 나눠 봤습니다. " +
    `골프장은 강원 고객이 ${pct(chg(g["강원_피해율"]))}, 외지 고객이 ${pct(chg(g["외지_피해율"]))}로 외지 관광객이 더 크게 빠집니다. ` +
    "레저타운·놀이동산은 둘 다 45% 정도 줄었는데, 애초에 고객 80%가 외지인입니다. " +
    `사우나는 외지 고객 매출이 ${pct(chg(sa["외지_피해율"]))} 늘었습니다. 비 오는 날 춘천에 온 관광객이 실내 시설로 옮겨 간 겁니다. ` +
    "결국 레저 피해는 외지 관광객이 비 때문에 일정을 취소하거나 바꾸는 문제이고, 실내로 붙잡을 여지도 있다는 뜻입니다.");
}

// ---------------------------------------------------------------- 7. 정리
{
  const s = pres.addSlide({ masterName: "SECTION", sectionTitle: SEC });
  s.addText("정리: 춘천의 비 취약 상권은\n레저(당일 충격)와 숙박(회복 실패)", { placeholder: "title" });
  s.addText("원인은 외지 관광객의 이탈 → 모델은 이 손실과 회복을 예측하고, 정책은 재방문을 만든다", { placeholder: "body" });
  const cards = [
    ["1", "당일 충격", `야외·레저 ${pct(chg(G["야외·레저"].loss))}\n업종 중 최대 감소`],
    ["2", "회복 실패", `숙박·여행 3일 누적 ${pct(chg(G["숙박·여행"].cum))}\n레저도 손실을 메우지 못함`],
    ["3", "원인", "외지 관광객 이탈\n비 오면 실내(사우나 등)로 이동"],
  ];
  cards.forEach(([n, h, b], i) => {
    const x = 0.8 + i * 3.9;
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y: 4.7, w: 3.6, h: 1.65, rectRadius: 0.12, fill: { color: "1F4252" },
                                                line: { color: "1F4252" }, objectName: `summary card ${i + 1}` });
    s.addShape(pres.shapes.OVAL, { x: x + 0.25, y: 4.9, w: 0.45, h: 0.45, fill: { color: HEX.orange },
                                   line: { color: HEX.orange }, objectName: `summary number ${i + 1}` });
    s.addText(n, { x: x + 0.25, y: 4.9, w: 0.45, h: 0.45, fontSize: 15, bold: true, color: "FFFFFF", align: "center",
                   valign: "middle", margin: 0, isTextBox: true });
    s.addText(h, { x: x + 0.85, y: 4.9, w: 2.6, h: 0.45, fontSize: 17, bold: true, color: "FFFFFF", valign: "middle",
                   margin: 0, isTextBox: true });
    s.addText(b, { x: x + 0.25, y: 5.45, w: 3.2, h: 0.8, fontSize: 13, color: "DCE6EC", margin: 0, valign: "top",
                   isTextBox: true });
  });
  s.addText("한계: 숙박 앱 선결제 미포함 · 6개월(비 10mm+ 26일) · 고객 거주지는 시도 단위 · 외지 비중과 피해의 관계는 레저·숙박 안에서만 확인", {
    x: 0.8, y: 6.65, w: 11.7, h: 0.35, fontSize: 11, color: "9FB3BF", margin: 0, isTextBox: true });
  s.addNotes("정리하겠습니다. 춘천에서 비에 가장 약한 상권은 두 곳입니다. 야외·레저는 비 오는 당일 40% 빠지는 충격이 가장 크고, " +
    "숙박은 당일보다 그 뒤 사흘에 걸쳐 손실이 쌓여 회복하지 못합니다. 원인은 외지 관광객이 비 때문에 오지 않는 데 있고, " +
    "비가 와도 실내로 옮겨 가는 관광객이 있다는 점은 대책의 실마리입니다. " +
    "다음 장 AI 모델에서는 이 두 업종의 매출 감소와 회복을 예측하고, 정책 제안에서는 관광객을 다시 오게 하는 방법을 다룹니다. " +
    "한계로, 숙박은 앱 선결제가 데이터에서 빠지고, 기간이 6개월이며, 업종군 전체로 보면 외지인 비중과 피해의 관계는 뚜렷하지 않아 레저·숙박 안에서만 주장합니다.");
}

pres.writeFile({ fileName: OUT }).then(async (f) => {
  if (APPLY_THEME) {
    const { applyTheme } = require(APPLY_THEME);
    await applyTheme(OUT, THEME);
  }
  console.log("wrote", f);
});
