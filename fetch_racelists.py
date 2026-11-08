#!/usr/bin/env python3
"""Fetch official Toda race-card HTML; do not confuse missing cards with valid data."""
import argparse
import datetime as dt
import json
import os
import pathlib
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from zoneinfo import ZoneInfo

BASE = 'https://www.boatrace.jp/owpc/pc/race/racelist'
TZ = ZoneInfo('Asia/Tokyo')

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--date', help='YYYYMMDD; default: tomorrow in Japan')
    args = parser.parse_args()
    target = args.date or (dt.datetime.now(TZ).date() + dt.timedelta(days=1)).strftime('%Y%m%d')
    if not re.fullmatch(r'20\d{6}', target):
        raise SystemExit('Invalid date: use YYYYMMDD')
    dest = pathlib.Path('data') / target
    dest.mkdir(parents=True, exist_ok=True)
    summary = {'date': target, 'venue': '02', 'source': BASE, 'retrieved_at': dt.datetime.now(TZ).isoformat(), 'races': []}
    valid = 0
    for race in range(1, 13):
        params = urllib.parse.urlencode({'rno': race, 'jcd': '02', 'hd': target})
        url = f'{BASE}?{params}'
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (compatible; TodaRacePredictor/0.1; personal research)', 'Accept-Language': 'ja,en;q=0.8'})
        item = {'race': race, 'url': url}
        try:
            with urllib.request.urlopen(req, timeout=20) as response:
                raw = response.read()
                item['http_status'] = response.status
                item['bytes'] = len(raw)
                html = raw.decode('utf-8', errors='replace')
                # This is a download validation, not a claim that all six entries were parsed.
                if len(raw) < 5000 or '<table' not in html.lower():
                    item['status'] = 'unverified_html'
                else:
                    (dest / f'race_{race:02d}.html').write_bytes(raw)
                    item['status'] = 'html_saved_unparsed'
                    valid += 1
        except urllib.error.HTTPError as e:
            item['status'] = 'http_error'
            item['http_status'] = e.code
        except Exception as e:
            item['status'] = 'fetch_error'
            item['error'] = str(e)[:250]
        summary['races'].append(item)
        print(f"{race:02d}R: {item['status']}" , flush=True)
        time.sleep(1)
    (dest / 'manifest.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'Saved HTML for {valid}/12 races; raw HTML is NOT prediction-ready.', flush=True)
    if valid != 12:
        raise SystemExit(f'Incomplete: {valid}/12. Check published schedule, HTTP status, and page structure.')

if __name__ == '__main__':
    main()
