"""Compare saved official history tables to site rows; candidates require review.

python scripts/compare_award_pages.py PATH_TO_PAGES_JSON OUTPUT_JSON
Name normalization is only for audit candidates, never for changing player IDs.
"""
from collections import Counter
import json
from pathlib import Path
import re
import sys
import unicodedata
from awards import DATA


def norm(s):
    s = re.sub(r'\s+(?:Jr\.?|Sr\.?)$', '', s, flags=re.I)
    n = re.sub('[^a-z]', '', unicodedata.normalize('NFKD', s).encode('ascii', 'ignore').decode().lower())
    # Reviewed display-name differences and two typos in MLB's history tables.
    return {'mikesoroka': 'michaelsoroka', 'deegordon': 'deestrangegordon',
            'douglasdecinces': 'dougdecinces', 'ezquieltovar': 'ezequieltovar',
            'luizarraez': 'luisarraez'}.get(n, n)


def main():
    pages = json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))
    local = json.loads((DATA / 'awards.json').read_text(encoding='utf-8'))
    official = []
    for key, page in pages.items():
        for ti, table in enumerate(page.get('tables', [])):
            # Separate BBWAA awards added in 2026 are outside the ALREL/NLREL series.
            if key == 'rel' and ti >= 2:
                continue
            if not table:
                continue
            headers = [c['text'].lower() for c in table[0]]
            if 'year' not in headers or not ('player' in headers or 'manager' in headers):
                continue
            yi = headers.index('year')
            ni = headers.index('player') if 'player' in headers else headers.index('manager')
            ki = key
            if key == 'postseason':
                ki = 'wsmvp' if ti == 0 else 'lcsmvp'
            if key == 'allmlb':
                ki = 'allmlb1' if ti % 2 == 0 else 'allmlb2'
            for row in table[1:]:
                if len(row) <= max(yi, ni) or not row[yi]['text'].isdigit() or not row[ni]['text']:
                    continue
                official.append({'key': ki, 'year': int(row[yi]['text']), 'name': row[ni]['text'],
                                 'cells': [c['text'] for c in row], 'table': ti, 'url': page['url']})
    def mark(r):
        return r['key'], r['year'], norm(r['name'])
    own = [{'key': r[0], 'year': r[1], 'name': local['people'][str(r[3])][0], 'row': r} for r in local['rows']]
    om, lm = {mark(r): r for r in official}, {mark(r): r for r in own}
    covered = {r['key'] for r in official}
    team_ids = {'Anaheim': [108], 'California': [108], 'LA Angels': [108], 'Arizona': [109],
                'Atlanta': [144], 'Braves': [144], 'Bsn. Braves': [144], 'Baltimore': [110],
                'Boston': [111, 144], 'Brooklyn': [119], 'Chi Cubs': [112], 'Chi White Sox': [145],
                'White Sox': [145], 'Chicago': [112, 145], 'Cincinnati': [113], 'Cleveland': [114],
                'Colorado': [115], 'Detroit': [116], 'Florida': [146], 'Miami': [146], 'Houston': [117],
                'Kansas City': [118, 133], 'LA Dodgers': [119], 'Los Angeles': [108, 119],
                'Milwaukee': [144, 158], 'Minnesota': [142], 'Montreal': [120], 'NY Giants': [137],
                'NY Mets': [121], 'NY Yankees': [147], 'New York': [121, 137, 147], 'Oakland': [133],
                'Athletics': [133], 'Phi. Athletics': [133], 'Philadelphia': [133, 143], 'Phillies': [143],
                'Pittsburgh': [134], 'San Diego': [135], 'San Francisco': [137], 'Seattle': [136],
                'St. Louis': [110, 138], 'StL Browns': [110], 'Tampa Bay': [139], 'Texas': [140],
                'Toronto': [141], 'Washington': [120, 140, 142]}
    team_mismatch, unresolved_team = [], []
    for r in official:
        target = lm.get(mark(r))
        if not target:
            continue
        team = r['cells'][3] if r['key'].startswith('allmlb') else r['cells'][2]
        options = []
        for part in team.split('/'):
            options += team_ids.get(re.sub(r' \([AN]L\)$', '', part), [])
        if not options:
            unresolved_team.append(r)
        elif target['row'][5] not in options:
            team_mismatch.append({'official': r, 'local': target})
    result = {'official_rows': len(official), 'official_unique': len(om), 'covered': sorted(covered),
              'team_mismatch': team_mismatch, 'unresolved_team': unresolved_team,
              'official_only': [r for k, r in om.items() if k not in lm],
              'local_only': [r for k, r in lm.items() if k[0] in covered and k not in om],
              'official_multiple': [{'key': list(k), 'count': n, 'rows': [r for r in official if mark(r) == k]}
                                    for k, n in Counter(mark(r) for r in official).items() if n > 1]}
    Path(sys.argv[2]).write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print('Official only', len(result['official_only']), 'Local only', len(result['local_only']))
    for category in ('official_only', 'local_only'):
        for r in result[category]:
            print(category, r['key'], r['year'], r['name'])


if __name__ == '__main__':
    main()
