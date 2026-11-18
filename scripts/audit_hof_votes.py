"""Read-only HOF ballot audit, using cached wiki text and listing unmatched names.

python scripts/audit_hof_votes.py CACHE_DIRECTORY OUTPUT_JSON
"""
import json
from pathlib import Path
import sys
import time
import requests
from awards import DATA
from hof_votes import parse_ballot, norm, BALLOT_PAGE


def main():
    cache, output = Path(sys.argv[1]), Path(sys.argv[2])
    votes = json.loads((DATA / 'hof_votes.json').read_text(encoding='utf-8'))['players']
    people = json.loads((DATA / 'awards.json').read_text(encoding='utf-8'))['people']
    years = sorted({v['year'] for v in votes.values() if v['method'] == 'BBWAA'})
    result = {'years': years, 'errors': [], 'skipped': [], 'mismatch': [], 'unmatched': [], 'candidates': {}}
    session = requests.Session()
    for year in years:
        try:
            path = cache / f'ballot-{year}.txt'
            if path.exists():
                text = path.read_text(encoding='utf-8')
            else:
                response = session.get('https://en.wikipedia.org/w/api.php', params={
                    'action': 'parse', 'page': BALLOT_PAGE.format(year=year), 'prop': 'wikitext',
                    'format': 'json', 'formatversion': 2}, timeout=30,
                    headers={'User-Agent': 'bbaddanet-portfolio/1.0'})
                response.raise_for_status()
                text = response.json()['parse']['wikitext']
                path.write_text(text, encoding='utf-8')
                time.sleep(1.5)
            parsed = parse_ballot(text)
            for pid, old in votes.items():
                if old['method'] != 'BBWAA' or old['year'] != year:
                    continue
                name = people[pid][0]
                new = parsed.get(norm(name))
                if new is None:
                    result['unmatched'].append({'id': pid, 'name': name, 'old': old})
                    result['candidates'][year] = parsed
                elif any(old[k] != new[k] for k in ('votes', 'ballot')):
                    result['mismatch'].append({'id': pid, 'name': name, 'old': old, 'parsed': new})
            print(year, len(parsed), flush=True)
        except Exception as exc:
            result['errors'].append({'year': year, 'error': str(exc)})
            if isinstance(exc, requests.HTTPError) and exc.response.status_code == 429:
                result['skipped'] = [y for y in years if y > year]
                output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
                print('Rate limited; remaining years skipped. Resume after the source permits requests.', flush=True)
                break
            time.sleep(1.5)
        output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')


if __name__ == '__main__':
    main()
