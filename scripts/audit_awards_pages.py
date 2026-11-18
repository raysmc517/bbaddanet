"""Fetch independent official award history tables for the read-only audit.

Usage: python scripts/audit_awards_pages.py --out PATH
Uses only requests and the standard library; source HTML stays in temp storage.
"""
import argparse
from html.parser import HTMLParser
import json
from pathlib import Path
import time
import requests


class Tables(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tables = []
        self.table = None
        self.row = None
        self.cell = None
        self.links = []

    def handle_starttag(self, tag, attrs):
        if tag == 'table':
            self.table = []
        elif tag == 'tr' and self.table is not None:
            self.row = []
        elif tag in ('th', 'td') and self.row is not None:
            self.cell = []
            self.links = []
        elif tag == 'a' and self.cell is not None:
            self.links.append(dict(attrs).get('href', ''))

    def handle_data(self, data):
        if self.cell is not None:
            self.cell.append(data)

    def handle_endtag(self, tag):
        if tag in ('th', 'td') and self.cell is not None:
            self.row.append({'text': ' '.join(''.join(self.cell).split()), 'links': self.links})
            self.cell = None
        elif tag == 'tr' and self.row is not None:
            self.table.append(self.row)
            self.row = None
        elif tag == 'table' and self.table is not None:
            self.tables.append(self.table)
            self.table = None


PAGES = {
    'mvp': 'most-valuable-player', 'cy': 'cy-young', 'roy': 'rookie-of-the-year',
    'postseason': 'postseason',
    'asmvp': 'all-star', 'allmlb': 'all-mlb', 'gg': 'gold-glove',
    'pg': 'platinum-glove', 'ss': 'silver-slugger', 'haa': 'hank-aaron',
    'rel': 'reliever-of-the-year', 'cpoy': 'comeback-player',
    'clemente': 'roberto-clemente', 'moy': 'manager-of-the-year',
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', required=True)
    args = parser.parse_args()
    output = Path(args.out)
    output.parent.mkdir(parents=True, exist_ok=True)
    result = {}
    for key, slug in PAGES.items():
        url = 'https://www.mlb.com/awards/' + slug
        path = output.parent / (key + '.html')
        try:
            if path.exists():
                html = path.read_text(encoding='utf-8')
            else:
                response = requests.get(url, timeout=45)
                response.raise_for_status()
                html = response.text
                path.write_text(html, encoding='utf-8')
                time.sleep(1)
            table_parser = Tables()
            table_parser.feed(html)
            result[key] = {'url': url, 'tables': table_parser.tables}
            print(key, [len(t) for t in table_parser.tables], flush=True)
        except Exception as exc:
            result[key] = {'url': url, 'error': str(exc)}
            print(key, str(exc), flush=True)
        output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')


if __name__ == '__main__':
    main()
