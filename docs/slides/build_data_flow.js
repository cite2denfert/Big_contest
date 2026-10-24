// "분석 데이터 구성과 활용 범위" 장의 데이터 결합 도식 (팀 장표 색)
// 실행: NODE_PATH=<pptxgenjs node_modules> node docs/slides/build_data_flow.js
const path = require("path");
const pptxgen = require("pptxgenjs");

const OUT = process.env.PPTX_OUT || path.join(__dirname, "data_flow_diagram.pptx");
const HEX = { primary: "4A6E52", light: "96A89C", tint: "EAF0E3", ink: "192E26", muted: "617069", bg: "F6F9F1" };

const pres = new pptxgen();
pres.layout = "LAYOUT_WIDE";
pres.theme = { headFontFace: "Malgun Gothic", bodyFontFace: "Malgun Gothic" };
const s = pres.addSlide();
s.background = { color: HEX.bg };

const D = 1.3; // 동그라미 지름
const TOP_Y = 3.07, BOT_Y = 5.19; // 중심 y (원래 장표 위치)
const flows = [
  { cx: 8.71, src: "신한카드\n+ 기상 자료", how: "지역·날짜로 결합", out: "매출·기상\n결합 자료" },
  { cx: 10.99, src: "SK 유동인구", how: "성·연령, 시간대, 요일", out: "지역 활동\n특성 설명" },
];

flows.forEach((f, i) => {
  // 입력 자료: 연한 초록 바탕 + 세이지 테두리
  s.addShape(pres.shapes.OVAL, { x: f.cx - D / 2, y: TOP_Y - D / 2, w: D, h: D, fill: { color: HEX.tint },
    line: { color: HEX.light, width: 1.5 }, objectName: `source ${i + 1}` });
  s.addText(f.src, { x: f.cx - D / 2, y: TOP_Y - D / 2, w: D, h: D, fontSize: 12, bold: true, color: HEX.ink,
    align: "center", valign: "middle", margin: 0, isTextBox: true });
  // 결합 방법: 화살표 + 설명
  s.addShape(pres.shapes.LINE, { x: f.cx, y: TOP_Y + D / 2 + 0.08, w: 0, h: BOT_Y - TOP_Y - D - 0.16,
    line: { color: HEX.muted, width: 1.25, endArrowType: "triangle" }, objectName: `arrow ${i + 1}` });
  s.addText(f.how, { x: f.cx + 0.12, y: (TOP_Y + BOT_Y) / 2 - 0.27, w: 1.15, h: 0.55, fontSize: 10, color: HEX.muted,
    align: "left", valign: "middle", margin: 0, isTextBox: true });
  // 결과: 진한 초록
  s.addShape(pres.shapes.OVAL, { x: f.cx - D / 2, y: BOT_Y - D / 2, w: D, h: D, fill: { color: HEX.primary },
    line: { color: HEX.primary }, objectName: `result ${i + 1}` });
  s.addText(f.out, { x: f.cx - D / 2, y: BOT_Y - D / 2, w: D, h: D, fontSize: 12, bold: true, color: "FFFFFF",
    align: "center", valign: "middle", margin: 0, isTextBox: true });
});

pres.writeFile({ fileName: OUT }).then((f) => console.log("wrote", f));
