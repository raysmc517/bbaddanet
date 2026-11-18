"""Read-only awards audit. python scripts/audit_awards.py --out PATH

Caches source responses in the system temp directory; never changes site data.
Remove the cache or use --refresh to check newer source responses.
"""
import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import html
import json
from pathlib import Path
import re
import tempfile
import time

import requests

from awards import AWARDS, DATA, assemble


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', required=True)
    parser.add_argument('--refresh', action='store_true')
    args = parser.parse_args()
    cache = Path(tempfile.gettempdir()) / 'bbaddanet-awards-audit'
    cache.mkdir(exist_ok=True)
    session = requests.Session()

    def get(url):
        path = cache / (hashlib.sha256(url.encode()).hexdigest() + '.json')
        if path.exists() and not args.refresh:
            return json.loads(path.read_text(encoding='utf-8'))['body']
        response = session.get(url, timeout=60, headers={'User-Agent': 'bbaddanet-portfolio/1.0'})
        response.raise_for_status()
        result = {'url': url, 'fetched': datetime.now(timezone.utc).isoformat(), 'body': response.text}
        path.write_text(json.dumps(result, ensure_ascii=False), encoding='utf-8')
        time.sleep(0.6)
        return response.text

    local = json.loads((DATA / 'awards.json').read_text(encoding='utf-8'))
    votes = json.loads((DATA / 'hof_votes.json').read_text(encoding='utf-8'))['players']
    result = {'checked': datetime.now(timezone.utc).isoformat(), 'local_updated': local['updated'],
              'cache': str(cache), 'sources': {}, 'errors': [], 'raw_rejected': [], 'raw_duplicates': []}
    collected = {}
    for key, label, sources in AWARDS:
        for aid, league in sources:
            url = f'https://statsapi.mlb.com/api/v1/awards/{aid}/recipients?sportId=1&hydrate=team'
            try:
                raw = json.loads(get(url))['awards']
                items = []
                for row in raw:
                    p = row.get('player') or {}
                    if not p.get('id') or not str(row.get('season', '')).isdigit():
                        result['raw_rejected'].append({'award': aid, 'row': row})
                        continue
                    team = row.get('team') or {}
                    pos = p.get('primaryPosition', {}).get('abbreviation', '')
                    items.append(dict(season=int(row['season']), id=p['id'], name=p.get('nameFirstLast', ''),
                                      pos='' if pos == 'X' else pos, team=team.get('abbreviation', ''), teamId=team.get('id')))
                counts = Counter((i['season'], i['id']) for i in items)
                result['raw_duplicates'] += [{'award': aid, 'year': y, 'id': pid, 'count': n}
                                             for (y, pid), n in counts.items() if n > 1]
                collected[aid] = items
                result['sources'][aid] = {'url': url, 'raw': len(raw), 'valid': len(items)}
                print(aid, len(raw), flush=True)
            except Exception as exc:
                result['errors'].append({'source': url, 'error': str(exc)})
    people, rows = assemble(collected, lambda pid: (DATA / 'players' / f'{pid}.json').exists())
    def mark(r):
        return tuple(r[:4])
    old = {mark(r): r for r in local['rows']}
    new = {mark(r): r for r in rows}
    result['missing_from_local'] = [r for k, r in new.items() if k not in old]
    complete_keys = {key for key, _, sources in AWARDS if all(aid in collected for aid, _ in sources)}
    result['api_comparison_complete'] = len(complete_keys) == len(AWARDS)
    result['local_only'] = [r for k, r in old.items() if k not in new and r[0] in complete_keys]
    result['changed_team'] = [{'local': old[k], 'remote': r} for k, r in new.items() if k in old and r[4:] != old[k][4:]]
    result['changed_people'] = [{'id': k, 'local': local['people'].get(k), 'remote': v}
                                for k, v in people.items() if local['people'].get(k) != v]
    result['duplicate_local'] = [list(k) + [n] for k, n in Counter(mark(r) for r in local['rows']).items() if n > 1]
    result['broken_references'] = [r for r in local['rows'] if str(r[3]) not in local['people']]
    result['page_flag_mismatch'] = [{'id': k, 'person': v} for k, v in local['people'].items()
                                    if bool(v[2]) != (DATA / 'players' / f'{k}.json').exists()]
    available_positions = {}
    for items in collected.values():
        for item in items:
            if item['pos']:
                available_positions.setdefault(str(item['id']), set()).add(item['pos'])
    result['overwritten_positions'] = [
        {'id': pid, 'name': person[0], 'available': sorted(available_positions[pid])}
        for pid, person in local['people'].items() if not person[1] and pid in available_positions]
    overwritten_ids = {p['id'] for p in result['overwritten_positions']}
    result['overwritten_position_rows'] = sum(str(r[3]) in overwritten_ids for r in local['rows'])
    result['hof_year_mismatch'] = [{'row': r, 'name': local['people'][str(r[3])][0], 'vote': votes[str(r[3])]}
                                   for r in local['rows'] if r[0] == 'hof' and str(r[3]) in votes and r[1] != votes[str(r[3])]['year']]
    result['hof_without_votes'] = [{'row': r, 'name': local['people'][str(r[3])][0]}
                                   for r in local['rows'] if r[0] == 'hof' and str(r[3]) not in votes]
    result['summary'] = []
    for key, label, sources in AWARDS:
        subset = [r for r in local['rows'] if r[0] == key]
        years = Counter(r[1] for r in subset)
        result['summary'].append({'key': key, 'label': label, 'rows': len(subset), 'years': dict(sorted(years.items())),
                                  'blank_team': sum(not r[4] for r in subset), 'blank_position': sum(not local['people'][str(r[3])][1] for r in subset)})
    # Save additional independent sources for inspection; do not reuse the production matcher as proof of identity.
    for name, url in {
        'catalog': 'https://statsapi.mlb.com/api/v1/awards',
        'hof_official': 'https://baseballhall.org/hall-of-fame/hall-of-famers-by-election-method',
        'hof_members': 'https://en.wikipedia.org/w/api.php?action=parse&page=List_of_members_of_the_National_Baseball_Hall_of_Fame&prop=wikitext&format=json&formatversion=2',
    }.items():
        try:
            body = get(url)
            dest = cache / (name + '.txt')
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(body, encoding='utf-8')
            result[name] = str(dest)
        except Exception as exc:
            result['errors'].append({'source': url, 'error': str(exc)})
    if 'hof_official' in result:
        from hof_votes import norm
        # Reviewed aliases from the official profiles; audit only, no ID writes.
        aliases = {'petealexander': 'groveralexander', 'goosegossage': 'richgossage',
                   'trisspeaker': 'tristramspeaker', 'charlesbender': 'chiefbender',
                   'charlescomiskey': 'charliecomiskey', 'banjohnson': 'byronjohnson',
                   'cumberlandposey': 'cumposey'}
        official = []
        source = Path(result['hof_official']).read_text(encoding='utf-8')
        for href, block in re.findall(r'<a href="(/hall-of-famers/[^\"]+)"[^>]*>(.*?)</a>', source, re.S):
            name = re.search(r'<h3[^>]*>(.*?)</h3>', block, re.S)
            year = re.search(r'<span class="number">(\d{4})</span>', block)
            if name and year:
                official.append({'name': html.unescape(name[1]), 'year': int(year[1]),
                                 'url': 'https://baseballhall.org' + href})
        result['hof_official_count'] = len(official)
        result['hof_missing_official'] = []
        result['hof_official_year_mismatch'] = []
        for member in official:
            n = norm(member['name'])
            hits = [r for r in local['rows'] if r[0] == 'hof'
                    and norm(local['people'][str(r[3])][0]) == aliases.get(n, n)]
            if not hits:
                result['hof_missing_official'].append(member)
            elif len(hits) != 1 or hits[0][1] != member['year']:
                result['hof_official_year_mismatch'].append({'official': member, 'local': hits})
    output = Path(args.out)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print('Saved', output, flush=True)


if __name__ == '__main__':
    main()
