"""Create a dependency-free XLSX viewing copy; retain original CSV values."""
import csv
import json
from pathlib import Path
from xml.sax.saxutils import escape
from zipfile import ZipFile, ZIP_DEFLATED
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'data' / 'weather'
NS = 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'
LABELS = {
    'station_id': '관측소번호', 'station_name': '관측소명', 'station_type': '관측유형',
    'MCT_SGG_CD': '지역명', 'datetime_kst': '관측일시(한국시간)', 'TA_YMD': '기준일자',
    'TIME_GB': '시간대', 'is_boundary_extra': '경계 보조자료 여부(1=보조)',
    'temperature_c': '기온(℃)', 'relative_humidity_pct': '상대습도(%)',
    'wind_speed_ms': '풍속(m/s)', 'precipitation_reported_mm': '원본 기록 강수량(mm)',
    'temperature_mean_c': '평균기온(℃)', 'temperature_min_c': '최저기온(℃)',
    'temperature_max_c': '최고기온(℃)', 'wind_speed_mean_ms': '평균풍속(m/s)',
    'wind_gust_max_ms': '최대순간풍속(m/s)', 'relative_humidity_mean_pct': '평균상대습도(%)',
    'frequency': '자료주기', 'missing_time_kst': '누락일시(한국시간)',
    'STN_ID': '관측소번호', 'STN_NM': '관측소명', 'TM': '관측일시(한국시간)',
}
TEXT_FIELDS = {'station_id', 'station_name', 'station_type', 'MCT_SGG_CD', 'datetime_kst',
               'TA_YMD', 'TIME_GB', 'frequency', 'missing_time_kst', 'STN_ID', 'STN_NM', 'TM'}


def column(index):
    result = ''
    while index:
        index, remainder = divmod(index - 1, 26)
        result = chr(65 + remainder) + result
    return result


def worksheet(rows, fields=None, labels=None):
    labels = labels or LABELS
    if fields is not None:
        content = [[labels.get(f, f) for f in fields]] + rows
    else:
        content = rows
    count = max(map(len, content))
    parts = [f'<worksheet xmlns="{NS}"><sheetViews><sheetView workbookViewId="0">'
             '<pane ySplit="1" topLeftCell="A2" activePane="bottomLeft" state="frozen"/>'
             '</sheetView></sheetViews><cols>']
    for i in range(1, count + 1):
        width = 29 if fields and fields[i-1] in ('datetime_kst', 'TM', 'missing_time_kst') else 23
        if fields is None:
            width = 24 if i == 1 else 110
        parts.append(f'<col min="{i}" max="{i}" width="{width}" customWidth="1"/>')
    parts.append('</cols><sheetData>')
    for r, values in enumerate(content, 1):
        parts.append(f'<row r="{r}">')
        for c, value in enumerate(values, 1):
            address = f'{column(c)}{r}'
            style = ' s="1"' if r == 1 else ''
            # Explicit text typing prevents date/code reinterpretation in Excel.
            numeric = fields is not None and r > 1 and fields[c-1] not in TEXT_FIELDS and not fields[c-1].endswith('_HRMT')
            if value == '':
                parts.append(f'<c r="{address}"/>')
            elif numeric:
                float(value)  # Reject accidental non-numeric strings.
                parts.append(f'<c r="{address}"><v>{escape(value)}</v></c>')
            else:
                parts.append(f'<c r="{address}" t="inlineStr"{style}><is><t xml:space="preserve">{escape(value)}</t></is></c>')
        parts.append('</row>')
    parts.append('</sheetData>')
    if fields:
        parts.append(f'<autoFilter ref="A1:{column(count)}{len(content)}"/>')
    parts.append('</worksheet>')
    return ''.join(parts)


def main():
    note = [
        ['항목', '설명'],
        ['내용', '강남·춘천의 2025년 7~12월 기상청 공개 관측자료. CSV와 동일한 값을 담은 엑셀 열람용 사본입니다.'],
        ['한글·열 구분', '이 파일은 XLSX이므로 인코딩이나 구분자를 선택하지 않고 엑셀에서 바로 열 수 있습니다.'],
        ['시간별기상', '기온, 상대습도, 풍속, 원본 기록 강수량. 관측일시는 한국시간입니다.'],
        ['일별기상', '기상청 공식 일 집계값. 강남 일자료에는 평균습도 항목이 제공되지 않습니다.'],
        ['빈칸', '원본의 미표기·결측을 보존했습니다. 강수 빈칸을 일괄 0으로 바꾸지 않았습니다.'],
        ['강남 관측 공백', '9월 10일 09시~11일 17시 시간자료 33개 시각 누락. 9월 11일 일자료 누락, 10일 일부 항목 빈칸.'],
        ['송파 보완자료', '9월 9~13일 인근 송파 관측값입니다. 강남값을 자동 대체하지 않았습니다.'],
        ['경계 보조자료', '2026년 1월 1일 00시 관측값은 강수 집계 경계 처리를 위한 보조행입니다.'],
        ['시간대', '관측시각 기준 시간대입니다. 누적 강수량은 관측 구간 종료시각을 고려해 집계해야 합니다.'],
        ['원본과 출처', '같은 폴더의 README.md, source_manifest.json, raw/ 및 QUALITY_REPORT.md를 확인하세요.'],
        ['통신 원본 CSV', 'UTF-8 인코딩, 구분자는 | (세로 막대)입니다. 소지역코드 BLOCK_CD는 텍스트로 읽어야 합니다.'],
        ['카드 원본 TXT', 'CP949(한국어 Windows) 인코딩, 구분자는 탭입니다. 카드 데이터2는 엑셀 한 시트의 행 한도를 넘습니다.'],
    ]
    sheets = [('안내', worksheet(note))]
    sources = [('시간별기상', DATA / 'weather_hourly.csv'),
               ('일별기상', DATA / 'weather_daily.csv'),
               ('누락시각', DATA / 'missing_timestamps.csv'),
               ('송파시간별', DATA / 'supplement/kma_aws_403_hourly_20250909_20250913.csv'),
               ('송파일별', DATA / 'supplement/kma_aws_403_daily_20250909_20250913.csv')]
    expected_rows = {}
    for name, path in sources:
        with path.open(encoding='utf-8-sig', newline='') as f:
            reader = csv.reader(f)
            fields = next(reader)
            rows = list(reader)
        labels = dict(LABELS)
        if name.startswith('송파'):
            kind = 'hourly' if name == '송파시간별' else 'daily'
            labels.update(json.loads((DATA / f'observations/kma_400_{kind}_columns.json').read_text(encoding='utf-8')))
        sheets.append((name, worksheet(rows, fields, labels)))
        expected_rows[name] = len(rows)
    destination = DATA / '기상데이터_엑셀용.xlsx'
    with ZipFile(destination, 'w', compression=ZIP_DEFLATED) as z:
        types = '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/><Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>'
        workbook = f'<workbook xmlns="{NS}" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets>'
        rels = '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        for i, (name, text) in enumerate(sheets, 1):
            z.writestr(f'xl/worksheets/sheet{i}.xml', text)
            types += f'<Override PartName="/xl/worksheets/sheet{i}.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
            workbook += f'<sheet name="{name}" sheetId="{i}" r:id="rId{i}"/>'
            rels += f'<Relationship Id="rId{i}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet{i}.xml"/>'
        rels += '<Relationship Id="styles" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/></Relationships>'
        z.writestr('[Content_Types].xml', types + '</Types>')
        z.writestr('xl/workbook.xml', workbook + '</sheets></workbook>')
        z.writestr('xl/_rels/workbook.xml.rels', rels)
        z.writestr('_rels/.rels', '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>')
        z.writestr('xl/styles.xml', f'<styleSheet xmlns="{NS}"><fonts count="2"><font><sz val="11"/><name val="맑은 고딕"/></font><font><b/><sz val="11"/><name val="맑은 고딕"/></font></fonts><fills count="3"><fill><patternFill patternType="none"/></fill><fill><patternFill patternType="gray125"/></fill><fill><patternFill patternType="solid"><fgColor rgb="FFDCEAF7"/><bgColor indexed="64"/></patternFill></fill></fills><borders count="1"><border/></borders><cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs><cellXfs count="2"><xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/><xf numFmtId="0" fontId="1" fillId="2" borderId="0" xfId="0" applyFont="1" applyFill="1"/></cellXfs><cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles></styleSheet>')
    with ZipFile(destination) as z:
        assert z.testzip() is None
        for path in z.namelist():
            ET.fromstring(z.read(path))
        for i, (name, _) in enumerate(sheets, 1):
            if name in expected_rows:
                tree = ET.fromstring(z.read(f'xl/worksheets/sheet{i}.xml'))
                assert len(tree.findall(f'{{{NS}}}sheetData/{{{NS}}}row')) - 1 == expected_rows[name]
    print(destination)
    print(json.dumps(expected_rows, ensure_ascii=False))


if __name__ == '__main__':
    main()
