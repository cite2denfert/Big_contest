"""Download public KMA observations, retaining exact responses and request provenance.

Only unauthenticated public observation/search pages are used. The API and
login-required export endpoints are not called. Python standard library only.
"""
from __future__ import annotations

import argparse
import concurrent.futures
import csv
import datetime as dt
import gzip
import hashlib
import http.client
import json
import re
import time
import threading
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'data' / 'weather'
BASE = 'https://data.kma.go.kr'
CONNECTIONS = threading.local()
STATIONS = {
    '400': {'name': '강남', 'region': '서울 강남구', 'kind': 'AWS', 'group': '181',
            'class': 'SFC02', 'pgm': '56', 'service': 'F00102',
            'page': '/data/grnd/selectAwsRltmList.do'},
    '101': {'name': '춘천', 'region': '강원 춘천시', 'kind': 'ASOS', 'group': '154',
            'class': 'SFC01', 'pgm': '36', 'service': 'F00101',
            'page': '/data/grnd/selectAsosRltmList.do'},
}


def fetch(path, params, target):
    target.parent.mkdir(parents=True, exist_ok=True)
    sidecar = target.with_suffix(target.suffix + '.request.json')
    if target.exists() and sidecar.exists():
        return gzip.decompress(target.read_bytes()).decode('utf-8')
    url = BASE + path
    body = urllib.parse.urlencode(params).encode() if params is not None else None
    for attempt in range(3):
        try:
            headers = {
                'User-Agent': 'BigContestWeatherResearch/1.0',
                'Referer': BASE + '/data/grnd/selectAwsRltmList.do?pgmNo=56',
                'Content-Type': 'application/x-www-form-urlencoded',
            }
            if not hasattr(CONNECTIONS, 'connection'):
                CONNECTIONS.connection = http.client.HTTPSConnection('data.kma.go.kr', timeout=45)
            connection = CONNECTIONS.connection
            connection.request('POST' if body else 'GET', path, body=body, headers=headers)
            response = connection.getresponse()
            raw = response.read()
            if response.status >= 400:
                raise urllib.error.HTTPError(url, response.status, response.reason, response.headers, None)
            metadata = {'url': url, 'method': 'POST' if body else 'GET',
                        'parameters': params, 'status': response.status,
                        'content_type': response.headers.get('Content-Type'),
                        'retrieved_at_utc': dt.datetime.now(dt.timezone.utc).isoformat(),
                        'sha256_uncompressed': hashlib.sha256(raw).hexdigest(),
                        'raw_bytes': len(raw)}
            text = raw.decode('utf-8')
            is_metadata = path.startswith('/tmeta/stn/selectStnDetail.do')
            if 'egovMapList1' not in text and 'selectElementSearchPopup' not in path and not is_metadata:
                raise ValueError('Response does not contain the expected public observation table')
            target.write_bytes(gzip.compress(raw, mtime=0))
            sidecar.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding='utf-8')
            return text
        except urllib.error.HTTPError as exc:
            if exc.code in (401, 403, 429):
                raise RuntimeError(f'Access/rate limit response {exc.code}; stopping, no bypass') from exc
            if attempt == 2:
                raise
        except (urllib.error.URLError, TimeoutError, ValueError, http.client.HTTPException, OSError):
            if attempt == 2:
                raise
        if hasattr(CONNECTIONS, 'connection'):
            CONNECTIONS.connection.close()
            del CONNECTIONS.connection
        time.sleep(2 ** attempt)
    raise RuntimeError('Unreachable')


def catalogue(station, form):
    cfg = STATIONS[station]
    params = {'lrgClssCd': 'SFC', 'mddlClssCd': cfg['class'],
              'dataFormCd': form, 'serviceSe': cfg['service']}
    text = fetch('/cmmn/selectElementSearchPopup.do', params,
                 OUT / 'raw' / 'catalogue' / f'{cfg["kind"]}_{form}.html.gz')
    return [v.split('|') for v in re.findall(r'value:"(0\|[^"]+)"', text)]


def parameters(station, form, start, end, elements):
    cfg = STATIONS[station]
    return {'pgmNo': cfg['pgm'], 'menuNo': '33', 'lrgClssCd': 'SFC',
            'mddlClssCd': cfg['class'], 'dataFormCd': form,
            'serviceSe': cfg['service'], 'startDt': start.strftime('%Y%m%d'),
            'endDt': end.strftime('%Y%m%d'), 'startHh': start.strftime('%H'),
            'endHh': end.strftime('%H'), 'stnIds': f'{cfg["group"]}_{station}',
            'elementCds': ','.join(e[2] for e in elements),
            'elementGroupSns': ','.join(dict.fromkeys(e[3] for e in elements)),
            'firstLoading': 'N', 'pageIndex': '1',
            'pageRowCount': '24' if form == 'F00502' else '31',
            'startYear': str(start.year), 'endYear': str(end.year)}


def parse(text):
    match = re.search(r"var egovMapList1 = '(.*?)';", text, re.S)
    if not match:
        raise ValueError('No observation data variable in response')
    rows = json.loads(match.group(1)) if match.group(1) else []
    eng = re.search(r"var engHeaderArr = '(.*?)'", text).group(1).split(',')
    kor = re.search(r"var korHeaderArr = '(.*?)'", text).group(1).split(',')
    return rows, dict(zip(eng, kor))


def query(station, form, start, end, elements):
    label = 'hourly' if form == 'F00502' else 'daily'
    target = OUT / 'raw' / label / station / f'{start:%Y%m%d%H}_{end:%Y%m%d%H}.html.gz'
    text = fetch(STATIONS[station]['page'], parameters(station, form, start, end, elements), target)
    rows, columns = parse(text)
    for row in rows:
        when = dt.datetime.fromisoformat(row['TM'])
        if str(row['STN_ID']) != station or not start <= when <= end:
            raise ValueError(f'Unexpected station or time: {row}')
    return rows, columns


def write_csv(path, rows, fields):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w', encoding='utf-8-sig', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(rows)


def write_manifest():
    manifest = []
    for path in sorted((OUT / 'raw').rglob('*.request.json')):
        entry = json.loads(path.read_text(encoding='utf-8'))
        entry['raw_file'] = str(path.relative_to(OUT)).removesuffix('.request.json').replace('\\', '/')
        manifest.append(entry)
    (OUT / 'source_manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')


def supplement():
    # Nearby observations are retained separately; never silently impute Gangnam.
    STATIONS['403'] = {**STATIONS['400'], 'name': '송파', 'region': '서울 송파구'}
    for station in ['400', '101', '403']:
        path = f'/tmeta/stn/selectStnDetail.do?isSelectStn=Y&pgmNo=82&stdStnNo={station}'
        fetch(path, None, OUT / 'raw' / 'metadata' / f'station_{station}.html.gz')
    results = {}
    for form in ['F00502', 'F00501']:
        elements = catalogue('403', form)
        cursor = dt.datetime(2025, 9, 9)
        end_all = dt.datetime(2025, 9, 14) if form == 'F00502' else dt.datetime(2025, 9, 13)
        step = dt.timedelta(hours=1) if form == 'F00502' else dt.timedelta(days=1)
        rows = []
        while cursor <= end_all:
            end = min(cursor + 9 * step, end_all)
            part, columns = query('403', form, cursor, end, elements)
            rows.extend(part)
            cursor = end + step
            time.sleep(0.2)
        label = 'hourly' if form == 'F00502' else 'daily'
        write_csv(OUT / 'supplement' / f'kma_aws_403_{label}_20250909_20250913.csv',
                  rows, ['STN_ID', 'STN_NM', 'TM'] + list(columns))
        expected = int((end_all - dt.datetime(2025, 9, 9)) / step) + 1
        results[label] = {'expected': expected, 'actual': len(rows),
                          'first': rows[0]['TM'] if rows else None,
                          'last': rows[-1]['TM'] if rows else None}
    write_manifest()
    (OUT / 'supplement' / 'validation.json').write_text(json.dumps(results, indent=2), encoding='utf-8')
    print('Supplement:', json.dumps(results), flush=True)


def download():
    start = dt.datetime(2025, 7, 1)
    # Extra midnight supports the precipitation interval ending 2026-01-01 00:00.
    limits = {'F00502': dt.datetime(2026, 1, 1), 'F00501': dt.datetime(2025, 12, 31)}
    jobs = []
    for station in STATIONS:
        for form in ['F00502', 'F00501']:
            elements = catalogue(station, form)
            step = dt.timedelta(hours=1) if form == 'F00502' else dt.timedelta(days=1)
            cursor = start
            while cursor <= limits[form]:
                end = min(cursor + 9 * step, limits[form])
                jobs.append((station, form, cursor, end, elements))
                cursor = end + step
    # The public table returns at most ten observations per query. Request no
    # more than ten times, preserving normal public-query limits and modest load.
    all_rows = {(s, f): [] for s in STATIONS for f in limits}
    schemas = {}

    def work(job):
        result = query(*job)
        time.sleep(0.2)
        return job[:2], result

    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        futures = [pool.submit(work, job) for job in jobs]
        try:
            for done, future in enumerate(concurrent.futures.as_completed(futures), 1):
                key, (rows, columns) = future.result()
                all_rows[key].extend(rows)
                schemas[key] = columns
                progress = {'completed_requests': done, 'total_requests': len(jobs),
                            'records': {f'{s}_{f}': len(r) for (s, f), r in all_rows.items()}}
                (OUT / 'download_progress.json').write_text(json.dumps(progress, indent=2), encoding='utf-8')
                if done % 40 == 0 or done == len(jobs):
                    print(json.dumps(progress), flush=True)
        except BaseException:
            for future in futures:
                future.cancel()
            raise

    validation = {}
    hourly = []
    daily = []
    for (station, form), rows in all_rows.items():
        rows.sort(key=lambda r: r['TM'])
        cfg = STATIONS[station]
        label = 'hourly' if form == 'F00502' else 'daily'
        columns = schemas[(station, form)]
        write_csv(OUT / 'observations' / f'kma_{cfg["kind"].lower()}_{station}_{label}.csv',
                  rows, ['STN_ID', 'STN_NM', 'TM'] + list(columns))
        (OUT / 'observations' / f'kma_{station}_{label}_columns.json').write_text(
            json.dumps(columns, ensure_ascii=False, indent=2), encoding='utf-8')
        step = dt.timedelta(hours=1) if label == 'hourly' else dt.timedelta(days=1)
        expected = set()
        cursor = start
        while cursor <= limits[form]:
            expected.add(cursor)
            cursor += step
        actual = [dt.datetime.fromisoformat(row['TM']) for row in rows]
        validation[f'{station}_{label}'] = {
            'expected_rows': len(expected), 'actual_rows': len(rows),
            'duplicate_timestamps': len(actual) - len(set(actual)),
            'missing_timestamps': [str(t) for t in sorted(expected - set(actual))],
            'blank_values': {field: sum(r.get(field) in (None, '') for r in rows) for field in columns},
        }
        if len(actual) != len(set(actual)) or set(actual) - expected:
            raise ValueError(f'Duplicate or unexpected time in {station} {label}')
        for row in rows:
            base = {'station_id': station, 'station_name': cfg['name'],
                    'station_type': cfg['kind'], 'MCT_SGG_CD': cfg['region']}
            if label == 'hourly':
                when = dt.datetime.fromisoformat(row['TM'])
                base.update({'datetime_kst': when.isoformat() + '+09:00',
                             'TA_YMD': when.strftime('%Y%m%d'),
                             'TIME_GB': f'{when.hour // 6 * 6:02d}_{when.hour // 6 * 6 + 5:02d}',
                             'is_boundary_extra': int(when == limits['F00502'])})
                mapping = ({'temperature_c': 'RTM_TA', 'relative_humidity_pct': 'RTM_RHM',
                            'wind_speed_ms': 'RTM_MI10_AVG_WS', 'precipitation_reported_mm': 'HR1_RN'}
                           if station == '400' else
                           {'temperature_c': 'TA', 'relative_humidity_pct': 'HM',
                            'wind_speed_ms': 'WS', 'precipitation_reported_mm': 'RN'})
                base.update({new: row.get(old) for new, old in mapping.items()})
                hourly.append(base)
            else:
                base['TA_YMD'] = row['TM'].replace('-', '')
                mapping = {'temperature_mean_c': 'AVG_TA', 'temperature_min_c': 'MIN_TA',
                           'temperature_max_c': 'MAX_TA', 'precipitation_reported_mm': 'SUM_RN',
                           'wind_speed_mean_ms': 'AVG_WS', 'wind_gust_max_ms': 'MAX_INS_WS',
                           'relative_humidity_mean_pct': 'AVG_RHM'}
                base.update({new: row.get(old) for new, old in mapping.items()})
                daily.append(base)
    write_csv(OUT / 'weather_hourly.csv', hourly, list(hourly[0]))
    write_csv(OUT / 'weather_daily.csv', daily, list(daily[0]))
    (OUT / 'validation.json').write_text(json.dumps(validation, ensure_ascii=False, indent=2), encoding='utf-8')
    write_manifest()
    print('Download complete. Validation:', json.dumps(validation, ensure_ascii=False), flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--probe', action='store_true')
    parser.add_argument('--download', action='store_true')
    parser.add_argument('--supplement', action='store_true')
    args = parser.parse_args()
    if args.probe:
        for station in STATIONS:
            for form in ['F00502', 'F00501']:
                elements = catalogue(station, form)
                print(station, form, elements, flush=True)
                start = dt.datetime(2025, 7, 1)
                end = start + (dt.timedelta(hours=23) if form == 'F00502' else dt.timedelta(days=9))
                rows, columns = query(station, form, start, end, elements)
                print(json.dumps({'count': len(rows), 'columns': columns,
                                  'first': rows[:1], 'last': rows[-1:]}, ensure_ascii=False), flush=True)
    if args.download:
        download()
    if args.supplement:
        supplement()


if __name__ == '__main__':
    main()
