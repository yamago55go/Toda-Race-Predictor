#!/usr/bin/env python3
"""Parse Toda official race-card pdftotext output into validated race CSV.

Usage: python3 scripts/parse_racecard.py data/20261107/extracted.txt --date 20261107
No predictions are generated. Invalid/incomplete races are flagged, never filled in.
"""
import argparse
import csv
import json
import re
from pathlib import Path

HEADER = re.compile(r'戸\s*田\s*([０-９0-9]{1,2})\s*[ＲR]\s*締切\s*(\d{1,2})\s*[:：]\s*(\d{2})')
# A normal upper row begins with boat number, class, registration ID, name, branch, age, ST, win rates.
ENTRY = re.compile(
    r'^\s*([1-6])\s+(A1|A2|B1|B2)\s+(\d{4})\s+(.+?)\s+'
    r'(北海道|青森|岩手|宮城|秋田|山形|福島|茨城|栃木|群馬|埼玉|千葉|東京|神奈川|新潟|富山|石川|福井|山梨|長野|岐阜|静岡|愛知|三重|滋賀|京都|大阪|兵庫|奈良|和歌山|鳥取|島根|岡山|広島|山口|徳島|香川|愛媛|高知|福岡|佐賀|長崎|熊本|大分|宮崎|鹿児島|沖縄)\s+'
    r'(\d{2})\s+(?:(F\d*|L\d*)\s+)?(\d{1,2}|-)\s+'
    r'(\d+\.\d+|-)\s+(\d+\.\d+|-)\s+(\d+\.\d+|-)\b'
)
FIELDS = ['date','race','deadline','boat','class','registration','name','branch','age','f_l','avg_st','national_win_rate','national_2ren','national_3ren','source_line']

def parse(text, date):
    # Exclude prior-day results and footer, which can contain similar-looking rows.
    text = text.split('集計期間 最近6ヶ月')[0]
    text = text.split('2026年11月 6日(金)競走成績')[0]
    rows, issues = [], []
    race = None
    deadline = None
    for lineno, line in enumerate(text.splitlines(), 1):
        header = HEADER.search(line)
        if header:
            race = int(header.group(1).translate(str.maketrans('０１２３４５６７８９','0123456789')))
            deadline = f'{int(header.group(2)):02d}:{header.group(3)}'
            continue
        if race is None:
            continue
        m = ENTRY.match(line)
        if m:
            boat, cls, reg, name, branch, age, fl, st, wr, two, three = m.groups()
            rows.append(dict(zip(FIELDS, [date, race, deadline, int(boat), cls, reg, name.strip(), branch, age, fl or '', st, wr, two, three, lineno])))
        elif re.match(r'^\s*[1-6]\s+(?:A1|A2|B1|B2)\s+', line):
            issues.append({'race':race,'line':lineno,'reason':'unparsed_entry','preview':line[:150]})
    valid = []
    for r in range(1, 13):
        entries = [x for x in rows if x['race'] == r]
        boats = [x['boat'] for x in entries]
        problems = []
        if len(entries) != 6 or sorted(boats) != [1,2,3,4,5,6]:
            problems.append(f'expected boats 1-6 once; parsed {boats}')
        for x in entries:
            if '-' in (x['avg_st'], x['national_win_rate'], x['national_2ren'], x['national_3ren']):
                problems.append(f"boat {x['boat']} missing statistics")
            else:
                try:
                    if not (0 <= float(x['national_win_rate']) <= 10 and 0 <= float(x['national_2ren']) <= 100 and 0 <= float(x['national_3ren']) <= 100):
                        problems.append(f"boat {x['boat']} invalid statistics")
                except ValueError:
                    problems.append(f"boat {x['boat']} invalid numeric format")
        if any(x['race'] == r for x in issues):
            problems.append('one or more unparsed entries')
        valid.append({'race':r,'valid':not problems,'problems':problems})
    return rows, issues, valid

def main():
    p = argparse.ArgumentParser()
    p.add_argument('input', type=Path)
    p.add_argument('--date', required=True, help='YYYYMMDD')
    p.add_argument('--output-dir', type=Path)
    args = p.parse_args()
    if not re.fullmatch(r'20\d{6}', args.date):
        p.error('--date must be YYYYMMDD')
    out = args.output_dir or args.input.parent
    out.mkdir(parents=True, exist_ok=True)
    rows, issues, checks = parse(args.input.read_text(encoding='utf-8'), args.date)
    with (out / 'racecard.csv').open('w', newline='', encoding='utf-8-sig') as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(rows)
    report = {'date':args.date,'parsed_entries':len(rows),'valid_races':[x['race'] for x in checks if x['valid']], 'race_checks':checks,'unparsed_lines':issues}
    (out / 'racecard_validation.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'entries':len(rows),'valid_races':report['valid_races'],'output':str(out)}, ensure_ascii=False))
    # A partial parse is useful for diagnosis, but is not approved for predictions.

if __name__ == '__main__':
    main()
