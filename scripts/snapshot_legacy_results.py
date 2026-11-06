# coding: utf-8
"""Generate a pre-change snapshot of the 6 legacy sequence searches.

Run this BEFORE implementing the DB, using the untouched code, so the test
suite can later prove the legacy results did not change.
"""
import json
import os
import sys

sys.path.insert(0, os.getcwd())
import main  # noqa: E402

LEGACY = {
    '0': 'Bm,G,D,A',
    '1': 'C,G,Am,F',
    '2': 'Em,G',
    '3': 'C,A7,Dm,G7',
    '4': 'Gm,F',
    '5': 'C,C7,F,Fm',
}


def fetch_all(client, query):
    ids = []
    page = 1
    while True:
        resp = client.get('/similares?%s&pagina=%d' % (query, page))
        data = json.loads(resp.data.decode('utf-8'))
        ids.extend(m['id_unico_musica'] for m in data)
        if len(data) < main.TAM_PAGINA:
            break
        page += 1
    return ids


def main_run():
    client = main.app.test_client()
    out = {}
    for seq_id, chords in LEGACY.items():
        ids = fetch_all(client, 'sequencia=' + chords)
        out[seq_id] = {
            'chords': chords.split(','),
            'count': len(ids),
            'ids': sorted(ids),
        }
        print('seq %s %-12s -> %d songs' % (seq_id, chords, len(ids)))
    path = os.path.join('tests', 'fixtures', 'legacy_similar_ids.json')
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=2, sort_keys=True)
    print('wrote', path)


if __name__ == '__main__':
    main_run()
