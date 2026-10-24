// 인사이트 2 장표: 춘천 레저·숙박은 비 오는 날 가장 약한 상권
// 데이터: outputs/chuncheon_leisure_lodging/slides_data.json (scripts/chuncheon_leisure_lodging.py가 생성)
// 실행: NODE_PATH=<pptxgenjs가 설치된 node_modules> node docs/slides/build_insight2.js
const path = require("path");
const fs = require("fs");
const pptxgen = require("pptxgenjs");

const ROOT = path.resolve(__dirname, "..", "..");
const D = JSON.parse(fs.readFileSync(path.join(ROOT, "outputs/chuncheon_leisure_lodging/slides_data.json"), "utf8"));
const OUT = process.env.PPTX_OUT || path.join(__dirname, "insight2_leisure_lodging.pptx");
const APPLY_THEME = process.env.PPTX_APPLY_THEME;

const THEME = {
  name: "Team Green",
  headFontFace: "Malgun Gothic",
  bodyFontFace: "Malgun Gothic",
  colors: {
    dk1: "192E26", lt1: "FFFFFF", dk2: "4A6E52", lt2: "F6F9F1",
    accent1: "4A6E52", accent2: "96A89C", accent3: "BAD666", accent4: "9DBB45",
    accent5: "617069", accent6: "D5DDD1", hlink: "4A6E52", folHlink: "617069",
  },
};
// 팀 장표 색: 진한 초록(강조·감소), 연한 세이지(비교 기준), 라임(포인트·증가)
const HEX = { primary: "4A6E52", light: "96A89C", neutral: "D5DDD1", lime: "BAD666", up: "9DBB45", upText: "5F7F25",
              ink: "192E26", muted: "617069", grid: "DCE3D5", bg: "F6F9F1", tint: "EAF0E3" };

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
  title: "CONTENT",
  background: { color: HEX.bg },
  margin: [0.5, 0.6, 0.6, 0.6],
  objects: [
    { rect: { x: 0.6, y: 0.43, w: 0.32, h: 0.09, fill: { color: HEX.lime }, line: { color: HEX.lime } } },
    { text: { text: "기후위기와 취약 상권 분석", options: { x: 1.02, y: 0.33, w: 6, h: 0.3, fontSize: 10, bold: true,
                                                          color: C.text1, margin: 0 } } },
    { placeholder: { options: { name: "title", type: "title", x: 0.6, y: 0.68, w: 12.1, h: 0.62, fontSize: 28, bold: true,
                                align: "left", color: C.text1, valign: "top", margin: 0 }, text: "" } },
    { placeholder: { options: { name: "body", type: "body", x: 0.6, y: 1.3, w: 12.1, h: 0.35, fontSize: 13,
                                align: "left", color: HEX.muted, valign: "top", margin: 0 }, text: "" } },
    { line: { x: 0.6, y: 6.85, w: 12.13, h: 0, line: { color: HEX.grid, width: 0.75 } } },
    { text: { text: SOURCE, options: { x: 0.6, y: 6.95, w: 11, h: 0.3, fontSize: 10, color: HEX.muted, margin: 0 } } },
  ],
  slideNumber: { x: 12.23, y: 6.95, w: 0.5, h: 0.3, fontSize: 11, bold: true, color: HEX.ink, align: "right" },
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

const RB = D.robust;

function card3(s, x, y, w, h, title, value, desc, color, name) {
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w, h, rectRadius: 0.1, fill: { color: HEX.tint },
                                              line: { color: HEX.tint }, objectName: name });
  s.addText([{ text: title, options: { bold: true, fontSize: 14, color: HEX.ink, breakLine: true } },
             { text: value, options: { bold: true, fontSize: 18, color, breakLine: true } },
             { text: desc, options: { fontSize: 13, color: HEX.ink } }],
            { x: x + 0.2, y: y + 0.07, w: w - 0.35, h: h - 0.12, margin: 0, valign: "top", isTextBox: true });
}

function footnote(s, text, y = 6.1, h = 0.65) {
  s.addText(text, { x: 9.0, y, w: 3.8, h, fontSize: 10, color: HEX.muted, margin: 0, valign: "bottom", isTextBox: true,
                    objectName: "footnote" });
}

// ---------------------------------------------------------------- 1. 업종군 비 피해
{
  const s = pres.addSlide({ masterName: "CONTENT", sectionTitle: SEC });
  s.addText("인사이트 2 · 비 오면 야외·레저 매출 40% 감소", { placeholder: "title" });
  s.addText("2025년 7–12월 · 일 강수량 10mm 이상을 '비 오는 날'로 구분 · 업종군 12개를 주·요일·공휴일·기온 통제 후 비교",
            { placeholder: "body" });
  const gs = D.groups; // 피해율 큰 순
  const colors = gs.map((g) => (g.name === "야외·레저" ? HEX.primary : g.name === "숙박·여행" ? HEX.light : HEX.neutral));
  caption(s, "업종군별 비 10mm+ 날 매출 변화 (비 안 온 날 대비)", 0.6, 1.75, 7.9);
  s.addChart(pres.charts.BAR, [{ name: "매출 변화", labels: gs.map((g) => g.name), values: gs.map((g) => chg(g.loss)) }], {
    x: 0.5, y: 2.1, w: 8.0, h: 4.7, barDir: "bar", catAxisOrientation: "maxMin", valAxisMinVal: -0.5, valAxisMaxVal: 0,
    valAxisMajorUnit: 0.1, chartColors: colors, showValue: true, dataLabelPosition: "outEnd", showLegend: false,
    barGapWidthPct: 45, ...AXIS, catAxisLabelPos: "low", objectName: "group rain chart" });

  const L = G["야외·레저"];
  const Lr = RB["야외·레저(업종군)"];
  s.addText(pct(chg(L.loss)), { x: 9.0, y: 1.95, w: 3.7, h: 1.1, fontSize: 64, bold: true, color: HEX.primary, margin: 0,
                                isTextBox: true });
  s.addText([{ text: "야외·레저", options: { bold: true, breakLine: true } },
             { text: "비 10mm+ 날 매출 변화", options: { breakLine: true } },
             { text: `95% 구간 ${ci(L.lo, L.hi)}`, options: { color: HEX.muted, fontSize: 12 } }],
            { x: 9.0, y: 3.05, w: 3.75, h: 0.95, fontSize: 14, color: HEX.ink, margin: 0, isTextBox: true });
  s.addText([
    { text: "매출 절반을 차지하는 외식·생활소매보다 6~8배 큰 감소", options: { bullet: true, breakLine: true } },
    { text: "숙박·여행은 당일 감소가 불확실하고, 손실은 비 온 뒤에 드러남 (다음 장)", options: { bullet: true } },
  ], { x: 9.0, y: 4.15, w: 3.75, h: 1.6, fontSize: 14, color: HEX.ink, margin: 0, paraSpaceAfter: 8, valign: "top",
       isTextBox: true });
  footnote(s, `쓴 컬럼: 날짜·업종·결제금액·고객 거주지 (부록 A)\n` +
              `기온을 연속값으로 통제해도 야외·레저 ${pct(Lr["기온연속_변화"])} (p<0.001)`, 5.75, 1.0);
  s.addNotes(`업종군 12개를 비교한 결과입니다. 비가 10mm 넘게 오는 날 야외·레저 매출은 40% 줄어 다른 업종보다 압도적으로 큽니다. ` +
    `95% 신뢰구간도 ${ci(L.lo, L.hi)}로 확실합니다. 춘천 매출의 절반을 차지하는 외식과 생활소매는 5~7% 정도 줄어듭니다. ` +
    `비 오는 날이 여름에 몰려 있어 기온을 더 촘촘히 통제해 봤는데, 그래도 야외·레저는 ${pct(Lr["기온연속_변화"])}로 뚜렷합니다. ` +
    `숙박·여행은 당일 ${pct(chg(G["숙박·여행"].loss))}로 통계적으로는 불확실한데, 다음 장에서 보듯 비 온 뒤 며칠에 걸쳐 손실이 커집니다. ` +
    `분석에는 날짜, 업종, 결제금액 컬럼을 썼고, 고객 거주지는 데이터2에서 가져왔습니다. 자세한 선택 이유는 부록에 있습니다.`);
}

// ---------------------------------------------------------------- 2. 회복
{
  const s = pres.addSlide({ masterName: "CONTENT", sectionTitle: SEC });
  s.addText("인사이트 2 · 레저·숙박은 비 온 뒤 회복하지 못한다", { placeholder: "title" });
  s.addText("비 온 당일과 3일 뒤까지의 누적 매출 변화 비교 · 레저는 당일에, 숙박은 며칠에 걸쳐 감소 · 생활소매는 회복",
            { placeholder: "body" });
  const names = ["야외·레저", "숙박·여행", "외식", "생활소매"];
  caption(s, "비 10mm+ 날 매출 변화: 당일 vs 3일 뒤까지 누적", 0.6, 1.75, 7.9);
  s.addChart(pres.charts.BAR, [
    { name: "비 온 당일", labels: names, values: names.map((n) => chg(G[n].day0)) },
    { name: "3일 뒤까지 누적", labels: names, values: names.map((n) => chg(G[n].cum)) },
  ], { x: 0.5, y: 2.1, w: 8.0, h: 4.7, barDir: "col", barGrouping: "clustered", valAxisMinVal: -0.5, valAxisMaxVal: 0.05,
       valAxisMajorUnit: 0.1, chartColors: [HEX.light, HEX.primary], showValue: true, dataLabelPosition: "outEnd",
       showLegend: true, legendPos: "t", legendFontFace: "+mn-lt", legendFontSize: 12, legendColor: HEX.ink,
       barGapWidthPct: 60, catAxisLabelPos: "high", ...AXIS, dataLabelFormatCode: "+0.0%;-0.0%;0%",
       objectName: "recovery chart" });
  const arrow = (n) => `${pct(chg(G[n].day0), 1)} → ${pct(chg(G[n].cum), 1)}`;
  card3(s, 9.0, 1.95, 3.75, 1.2, "야외·레저", arrow("야외·레저"), "잃은 손님이 돌아오지 않음", HEX.primary, "recovery card 1");
  card3(s, 9.0, 3.3, 3.75, 1.2, "숙박·여행", arrow("숙박·여행"), "비 온 뒤에도 손실이 커짐", HEX.primary, "recovery card 2");
  card3(s, 9.0, 4.65, 3.75, 1.2, "생활소매", arrow("생활소매"), "1~3일 안에 반등해 손실을 메움", HEX.upText, "recovery card 3");
  const ci2 = (lo, hi) => ci(lo, hi).replace(" ~ ", "~");
  footnote(s, `누적 95% 구간: 레저 ${ci2(G["야외·레저"].cum_lo, G["야외·레저"].cum_hi)}, ` +
              `숙박 ${ci2(G["숙박·여행"].cum_lo, G["숙박·여행"].cum_hi)}\n` +
              `생활소매 1~3일 뒤 반등 p = ${D.retail_rebound_p.toFixed(2)}`);
  s.addNotes("비 온 뒤 회복을 본 장입니다. 파란 막대는 비 온 당일, 주황 막대는 그 뒤 사흘까지 더한 누적 변화입니다. " +
    `생활소매는 당일 5% 줄지만 그 뒤 1~3일 사이 매출이 반등해 누적으로는 0에 가깝습니다. 반등은 통계적으로 유의합니다(p = ${D.retail_rebound_p.toFixed(2)}). ` +
    "손님이 장보기를 하루이틀 미룬 것으로 해석할 수 있습니다. " +
    "야외·레저는 당일 40% 빠진 뒤 그대로입니다. 비 때문에 취소한 골프나 나들이는 다시 오지 않는다는 뜻입니다. " +
    "숙박·여행은 당일보다 그 뒤가 더 나빠 누적 38% 감소입니다. 비 예보로 이어지는 예약 취소로 보입니다. " +
    "그래서 레저와 숙박은 손실이 사라지는 업종, 즉 지원이 필요한 업종입니다.");
}

// ---------------------------------------------------------------- 3. 세부 업종 + 고객 거주지
{
  const s = pres.addSlide({ masterName: "CONTENT", sectionTitle: SEC });
  s.addText("인사이트 2 · 피해는 외지 관광객이 찾는 업종에 집중", { placeholder: "title" });
  s.addText("외지 관광객이 많은 골프장·레저타운·교통은 크게 감소 · 주민 시설은 변화 없음 · 비 오면 사우나 등 실내 시설로 이동",
            { placeholder: "body" });
  const subs = D.sub.filter((r) => LABEL[r.name]).sort((a, b) => b.loss - a.loss);
  const col = (r) => (r.p < 0.05 ? (r.loss > 0 ? HEX.primary : HEX.up) : HEX.neutral);
  const o = (n) => pct(S[n].outsider).replace("+", "");
  const g = S["실내/실외골프장"], sa = S["싸우나/목욕탕"];
  // 차트 하나만: 업종 이름 옆에 외지 고객 비중을 붙여 거주지 정보를 차트 안에 담음
  const lab = (r) => `${LABEL[r.name]}  (외지 ${o(r.name)})`;
  caption(s, "레저·숙박 세부 업종별 비 10mm+ 날 매출 변화 (괄호: 외지 고객 비중)", 1.4, 1.8, 10.5);
  s.addText([{ text: "■ ", options: { color: HEX.primary } }, { text: "뚜렷한 감소   " },
             { text: "■ ", options: { color: HEX.neutral } }, { text: "차이 불확실   " },
             { text: "■ ", options: { color: HEX.up } }, { text: "뚜렷한 증가" }],
            { x: 1.4, y: 2.15, w: 10.5, h: 0.3, fontSize: 11, color: HEX.muted, margin: 0, isTextBox: true,
              objectName: "color key" });
  s.addChart(pres.charts.BAR, [{ name: "매출 변화", labels: subs.map(lab), values: subs.map((r) => chg(r.loss)) }], {
    x: 1.3, y: 2.5, w: 10.7, h: 4.25, barDir: "bar", catAxisOrientation: "maxMin", valAxisMinVal: -0.7, valAxisMaxVal: 0.3,
    valAxisMajorUnit: 0.1, chartColors: subs.map(col), showValue: true, dataLabelPosition: "outEnd", showLegend: false,
    barGapWidthPct: 45, catAxisLabelPos: "low", ...AXIS, objectName: "subindustry chart" });
  s.addNotes("레저와 숙박을 세부 업종으로 쪼갠 결과입니다. 진한 초록은 뚜렷하게 줄어든 업종, 연한 회색은 차이가 불확실한 업종, 라임은 뚜렷하게 늘어난 업종이고, 괄호 안은 외지 고객 비중입니다. " +
    "골프장은 58%, 고속버스·철도는 47%, 레저타운·놀이동산은 45% 줄었습니다. 세 업종 모두 외지 고객 비중이 80% 안팎입니다. " +
    `같은 골프장 안에서도 강원 고객은 ${pct(chg(g["강원_피해율"]))}, 외지 고객은 ${pct(chg(g["외지_피해율"]))}로 외지 관광객이 더 크게 빠집니다. ` +
    "반대로 헬스장과 스포츠시설처럼 주민이 쓰는 곳은 영향이 없습니다. " +
    `사우나는 오히려 ${pct(chg(sa.loss)).replace("+", "")} 늘었고, 외지 고객은 ${pct(chg(sa["외지_피해율"]))} 늘었습니다. ` +
    "비 오는 날 더 선선해서 늘어난 것 아니냐는 질문에 대비해 기온을 촘촘히 통제해 봤는데, 그래도 18% 증가로 유의합니다. " +
    "비가 오면 관광객이 아예 안 오는 게 아니라 실내로 옮겨 간다는 신호이고, 이것이 정책 제안의 실마리입니다. " +
    "참고로 강원 고객은 강원도 거주자 전체(춘천 밖 포함)입니다. 호텔·콘도도 21% 줄었지만 결제가 들쭉날쭉해 통계적으로는 불확실하고, 숙박은 앱 선결제가 데이터에서 빠지는 한계가 있습니다.");
}

// ---------------------------------------------------------------- 부록 A. 컬럼 선택
pres.addSection({ title: "부록" });
{
  const s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "부록" });
  s.addText("부록 A · 사용 컬럼과 선택 이유", { placeholder: "title" });
  s.addText("인사이트 2 분석에 쓴 컬럼, 비 피해율 정의, 통제 변수", { placeholder: "body" });
  const hdr = (t) => ({ text: t, options: { bold: true, color: "FFFFFF", fill: { color: HEX.primary } } });
  const rows = [
    [hdr("컬럼"), hdr("의미"), hdr("이 분석에서 쓴 이유")],
    ["TA_YMD", "결제일", "일별 기상 관측과 날짜로 1:1 연결"],
    ["MCT_RY_CD", "가맹점 업종", "업종군 12개, 레저·숙박 세부 업종 9개를 직접 비교"],
    ["TS_AT", "결제 금액", "피해를 매출 금액으로 보기 위해 사용"],
    ["CLN_SGG_CD", "고객 거주 시도 (데이터2)", "외지 관광객과 강원 고객을 나눠 누가 빠지는지 확인"],
    ["일강수량 · 기온", "기상청 ASOS 춘천", "비 10mm+ 여부, 기온 효과 통제"],
  ];
  s.addTable(rows, { x: 0.6, y: 1.85, w: 7.7, colW: [2.0, 2.2, 3.5], fontSize: 13, color: HEX.ink,
    border: { type: "solid", pt: 0.75, color: HEX.grid }, rowH: 0.62, valign: "middle", margin: 0.08,
    objectName: "column table" });
  s.addText("법인 결제와 비상권 업종 13개는 제외 (전처리 장 참고)", { x: 0.6, y: 5.75, w: 7.7, h: 0.35, fontSize: 12,
    color: HEX.muted, margin: 0, isTextBox: true });
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: 8.8, y: 1.85, w: 3.95, h: 4.25, rectRadius: 0.1,
    fill: { color: HEX.tint }, line: { color: HEX.tint }, objectName: "definition card" });
  [["비 피해율", "비 10mm+ 온 날의 매출 변화 (비 안 온 날 대비)"],
   ["같이 통제", "같은 주 · 요일 · 공휴일(추석 연휴) · 폭염. 강건성 확인으로 기온 연속값 통제도 함께"],
   ["회복", "비 온 뒤 1~3일 효과까지 더한 누적 변화"]].forEach(([h, b], i) => {
    const y = 2.1 + i * 1.3;
    s.addShape(pres.shapes.OVAL, { x: 9.05, y, w: 0.5, h: 0.5, fill: { color: HEX.primary }, line: { color: HEX.primary },
                                   objectName: `step ${i + 1}` });
    s.addText(String(i + 1), { x: 9.05, y, w: 0.5, h: 0.5, fontSize: 16, bold: true, color: "FFFFFF", align: "center",
                               valign: "middle", margin: 0, isTextBox: true });
    s.addText([{ text: h, options: { bold: true, fontSize: 15, breakLine: true } }, { text: b, options: { fontSize: 13 } }],
              { x: 9.75, y: y - 0.05, w: 2.85, h: 1.2, color: HEX.ink, valign: "top", margin: 0, isTextBox: true });
  });
  s.addNotes("분석에 쓴 컬럼과 이유입니다. 질문이 나오면 이 장을 보여 주세요.");
}

pres.writeFile({ fileName: OUT }).then(async (f) => {
  if (APPLY_THEME) {
    const { applyTheme } = require(APPLY_THEME);
    await applyTheme(OUT, THEME);
  }
  console.log("wrote", f);
});
