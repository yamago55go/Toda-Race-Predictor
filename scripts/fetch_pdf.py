#!/usr/bin/env python3
"""Diagnostic PDF downloader for Toda official race cards. No predictions are generated."""
import argparse
import datetime as dt
import io
import json
import pathlib
import re
import sys
from urllib.parse import urljoin
from zoneinfo import ZoneInfo
import requests
from bs4 import BeautifulSoup
import pdfplumber

INDEX = 'https://www.boatrace-toda.jp/race/shusso_list.html'
TZ = ZoneInfo('Asia/Tokyo')

def main():
    p = argparse.ArgumentParser()
    p.add_argument('--date', help='YYYYMMDD, default next day in Japan')
    p.add_argument('--pdf-url', help='Exact PDF URL copied from the official listing, if auto-discovery fails')
    args = p.parse_args()
    day = args.date or (dt.datetime.now(TZ).date() + dt.timedelta(days=1)).strftime('%Y%m%d')
    if not re.fullmatch(r'20\d{6}', day):
        sys.exit('Invalid date, expected YYYYMMDD')
    output = pathlib.Path('data') / day
    output.mkdir(parents=True, exist_ok=True)
    log = {'date': day, 'index': INDEX, 'checked_at': dt.datetime.now(TZ).isoformat(), 'candidates': []}
    headers = {'User-Agent': 'Mozilla/5.0 (compatible; TodaRacePredictor/0.2)', 'Accept-Language': 'ja-JP,ja;q=0.9'}
    try:
        response = requests.get(INDEX, headers=headers, timeout=25)
        log['index_status'] = response.status_code
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')
        links = []
        for a in soup.find_all('a', href=True):
            href = urljoin(response.url, a['href'])
            label = ' '.join(a.stripped_strings)
            parent = a.find_parent('tr')
            context = parent.get_text(' ', strip=True) if parent else label
            if '.pdf' in href.lower() or 'pdf' in label.lower() or '出走表' in label:
                links.append({'url': href, 'label': label[:100], 'context': context[:250]})
        log['candidates'] = links[:80]
        # Do not silently select an unrelated day's PDF. Explicit URL or date match required.
        short = f'{day[4:6]}/{day[6:8]}'
        candidates = [x for x in links if day in (x['url'] + x['context']) or short in x['context']]
        pdf_url = args.pdf_url or (candidates[0]['url'] if len(candidates) == 1 else None)
        if not pdf_url:
            log['status'] = 'needs_pdf_url_or_unambiguous_date_match'
            print('No unique date-matched PDF link found. Inspect manifest.json candidates.', flush=True)
        else:
            log['selected_url'] = pdf_url
            pdf_response = requests.get(pdf_url, headers=headers, timeout=35)
            log['pdf_status'] = pdf_response.status_code
            pdf_response.raise_for_status()
            blob = pdf_response.content
            if not blob.startswith(b'%PDF'):
                raise ValueError('Response is not a PDF (first bytes do not match PDF signature)')
            (output / 'racelist.pdf').write_bytes(blob)
            with pdfplumber.open(io.BytesIO(blob)) as pdf:
                pages = [page.extract_text(layout=False) or '' for page in pdf.pages]
            text = '\n\n--- PAGE ---\n\n'.join(pages)
            (output / 'extracted.txt').write_text(text, encoding='utf-8')
            log['pages'] = len(pages)
            log['text_characters'] = len(text)
            log['status'] = 'pdf_saved_text_extracted' if len(text.strip()) > 300 else 'pdf_saved_text_insufficient'
            print(f"PDF pages={len(pages)}, extracted characters={len(text)}", flush=True)
    except Exception as exc:
        log['status'] = 'error'
        log['error'] = f'{type(exc).__name__}: {exc}'[:500]
        print(log['error'], flush=True)
    finally:
        (output / 'manifest.json').write_text(json.dumps(log, ensure_ascii=False, indent=2), encoding='utf-8')
        print(f"Status: {log['status']}; manifest saved to {output}", flush=True)
    # No silent success if PDF or extract is not available.
    if log['status'] != 'pdf_saved_text_extracted':
        sys.exit(1)

if __name__ == '__main__':
    main()
