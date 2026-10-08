"""Offline integrity, coverage and physical-range checks for downloaded weather."""
from collections import Counter, defaultdict
import csv
import datetime as dt
import gzip
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'data' / 'weather'


def read_csv(path):
    with path.open(encoding='utf-8-sig', newline='') as f:
        return list(csv.DictReader(f))


def main():
    manifest = json.loads((OUT / 'source_manifest.json').read_text(encoding='utf-8'))
    for item in manifest:
        raw = gzip.decompress((OUT / item['raw_file']).read_bytes())
        assert hashlib.sha256(raw).hexdigest() == item['sha256_uncompressed'], item['raw_file']
    hourly = read_csv(OUT / 'weather_hourly.csv')
    daily = read_csv(OUT / 'weather_daily.csv')
    issues = []
    counts = Counter()
    blanks = Counter()
    seen = set()
    for label, rows in [('hourly', hourly), ('daily', daily)]:
        for row in rows:
            stamp = row['datetime_kst'] if label == 'hourly' else row['TA_YMD']
            key = (label, row['station_id'], stamp)
            assert key not in seen, key
            seen.add(key)
            assert row['MCT_SGG_CD'] == {'400': '서울 강남구', '101': '강원 춘천시'}[row['station_id']]
            counts[(label, row['station_id'])] += 1
            if label == 'hourly':
                timestamp = dt.datetime.fromisoformat(stamp)
                assert timestamp.utcoffset() == dt.timedelta(hours=9)
                assert timestamp.strftime('%Y%m%d') == row['TA_YMD']
                assert row['TIME_GB'] == f'{timestamp.hour // 6 * 6:02d}_{timestamp.hour // 6 * 6 + 5:02d}'
                bounds = {'temperature_c': (-60, 60), 'relative_humidity_pct': (0, 100),
                          'wind_speed_ms': (0, 100), 'precipitation_reported_mm': (0, 2000)}
            else:
                bounds = {'temperature_mean_c': (-60, 60), 'temperature_min_c': (-60, 60),
                          'temperature_max_c': (-60, 60), 'wind_speed_mean_ms': (0, 100),
                          'wind_gust_max_ms': (0, 150), 'precipitation_reported_mm': (0, 2000)}
                if all(row[f'temperature_{s}_c'] for s in ['min', 'mean', 'max']):
                    assert float(row['temperature_min_c']) <= float(row['temperature_mean_c']) <= float(row['temperature_max_c']), key
            for field, (low, high) in bounds.items():
                value = row[field]
                if value == '':
                    blanks[(label, row['station_id'], field)] += 1
                elif not low <= float(value) <= high:
                    issues.append({'key': key, 'field': field, 'value': value})
    coverage = json.loads((OUT / 'validation.json').read_text(encoding='utf-8'))
    missing = [{'station_id': k.split('_')[0], 'frequency': k.split('_')[1], 'missing_time_kst': t}
               for k, v in coverage.items() for t in v['missing_timestamps']]
    with (OUT / 'missing_timestamps.csv').open('w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=['station_id', 'frequency', 'missing_time_kst'])
        writer.writeheader()
        writer.writerows(missing)
    audit = {'raw_files_hash_verified': len(manifest), 'hourly_rows': len(hourly),
             'daily_rows': len(daily), 'duplicate_keys': 0, 'physical_range_issues': issues,
             'missing_timestamp_count': len(missing),
             'blank_common_fields': {'_'.join(k): v for k, v in blanks.items()}}
    (OUT / 'integrity_audit.json').write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding='utf-8')
    lines = ['# 수집·검증 결과', '',
             '| 지점·자료 | 예상 행 | 수집 행 | 누락 시각 수 | 중복 |',
             '|---|---:|---:|---:|---:|']
    for key, values in coverage.items():
        lines.append(f'| {key} | {values["expected_rows"]} | {values["actual_rows"]} | {len(values["missing_timestamps"])} | {values["duplicate_timestamps"]} |')
    lines.extend(['', '시간자료 예상 행 수에는 2026-01-01 00:00 경계 보조자료가 지점별 한 행 포함된다.',
                  '', f'원본 응답 {len(manifest)}개를 SHA-256으로 검증했다. 날짜·시간대·지역 결합 키 검증을 통과했다.',
                  f'설정한 넓은 물리 범위를 벗어난 주요 변수 값: {len(issues)}건.',
                  '', '## 누락 시각', ''])
    grouped = defaultdict(list)
    for row in missing:
        grouped[(row['station_id'], row['frequency'])].append(row['missing_time_kst'])
    for (station, frequency), times in grouped.items():
        lines.append(f'- {station} {frequency}: {len(times)}개. 첫 누락 {min(times)}, 마지막 누락 {max(times)}. 전체 목록은 `missing_timestamps.csv`.')
    lines.extend(['', '## 해석', '',
                  '- 위의 누락 시각 수는 행 자체가 없는 경우다. 개별 항목의 빈칸 개수는 `validation.json`과 `integrity_audit.json`에 별도로 기록했다.',
                  '- ASOS 강수·적설 등의 빈칸에는 현상 없음 표기가 섞일 수 있다. 일괄 결측 또는 0으로 판정하지 않았다.',
                  '- 기본 파일에는 보간값이나 인근 관측소 대체값을 넣지 않았다.',
                  '- 송파 403의 9월 9~13일 자료(다음날 00시 경계 포함)는 강남 누락 구간의 보완 가능성을 검토하기 위한 별도 `supplement/` 자료다.',
                  '- 다운로드 무결성·키·값 범위 검증은 기상청의 QC 판정이나 관측소 대표성 검증을 대신하지 않는다.', ''])
    (OUT / 'QUALITY_REPORT.md').write_text('\n'.join(lines), encoding='utf-8')
    print(json.dumps(audit, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
