# coding: utf-8
"""Research script: compare candidate real-time matching algorithms against
the pre-computed SEQ_FAMOSA tags in data/top/dataset_final.csv.

Replicates main.py parsing exactly (including its quirks) so the ground truth
matches what the running app produces today.
"""
import sys
import unicodedata

CSV = 'data/top/dataset_final.csv'

ARTISTA_ID, MUSICA_ID, ARTISTA, MUSICA, GENERO, POPULARIDADE, TOM, SEQ_FAMOSA, CIFRA = range(9)

SEQUENCIAS = {
    0: ['Bm', 'G', 'D', 'A'],
    1: ['C', 'G', 'Am', 'F'],
    2: ['Em', 'G'],
    3: ['C', 'A7', 'Dm', 'G7'],
    4: ['Gm', 'F'],
    5: ['C', 'C7', 'F', 'Fm'],
}


def limpa_cifra(raw_cifra):
    cifra = []
    for m in raw_cifra:
        if m.strip() != '':
            if '|' in m:
                acorde = m.split('|')[0].split()[0]
                cifra.append(acorde)
            else:
                tokens = [token for token in m.split()]
                cifra += tokens
    return cifra


def norm(chord):
    """Normalization candidate: strip whitespace, unify unicode, lowercase."""
    chord = unicodedata.normalize('NFKC', chord).strip()
    return chord.lower()


class Song:
    __slots__ = ('id_unico', 'cifra', 'acordes', 'acordes_norm', 'seqs', 'genero')

    def __init__(self, row):
        self.id_unico = '%s_%s' % (row[ARTISTA_ID], row[MUSICA_ID])
        self.genero = row[GENERO]
        raw = row[CIFRA]
        self.cifra = limpa_cifra(raw.split(';')) if raw != '' else []
        self.acordes = list(set(self.cifra))
        self.acordes_norm = set(norm(c) for c in self.cifra)
        self.seqs = row[SEQ_FAMOSA].split(';')


def load():
    songs = []
    with open(CSV, encoding='utf-8', errors='replace') as f:
        f.readline()
        for line in f:
            line = line.replace('"', '').replace('NA', '')[:-1]
            row = line.split(',')
            if len(row) < 9:
                continue
            try:
                int(row[POPULARIDADE].replace('.', ''))
            except ValueError:
                continue
            songs.append(Song(row))
    return songs


# ---- candidate algorithms -------------------------------------------------

def match_set(song, seq):
    """All chords present anywhere in the song (order ignored)."""
    return set(seq) <= set(song.acordes)


def match_set_norm(song, seq):
    return set(norm(c) for c in seq) <= song.acordes_norm


def match_ordered_subsequence(song, seq):
    """seq appears in order inside song.cifra, gaps allowed."""
    it = iter(song.cifra)
    return all(any(norm(c) == norm(s) for c in it) for s in seq)


def match_contiguous(song, seq):
    """seq appears as a contiguous run in song.cifra."""
    n = len(seq)
    if n == 0:
        return False
    target = [norm(c) for c in seq]
    cifra = [norm(c) for c in song.cifra]
    for i in range(len(cifra) - n + 1):
        if cifra[i:i + n] == target:
            return True
    return False


def match_ordered_subsequence_dedup(song, seq):
    """collapse consecutive duplicates first, then ordered subsequence."""
    dedup = []
    for c in song.cifra:
        if not dedup or norm(dedup[-1]) != norm(c):
            dedup.append(c)
    it = iter(dedup)
    return all(any(norm(c) == norm(s) for c in it) for s in seq)


def match_contiguous_dedup(song, seq):
    dedup = []
    for c in song.cifra:
        if not dedup or norm(dedup[-1]) != norm(c):
            dedup.append(c)
    n = len(seq)
    if n == 0:
        return False
    target = [norm(c) for c in seq]
    cifra = [norm(c) for c in dedup]
    for i in range(len(cifra) - n + 1):
        if cifra[i:i + n] == target:
            return True
    return False


ALGOS = {
    'set (order ignored)': match_set,
    'set normalized': match_set_norm,
    'ordered subsequence': match_ordered_subsequence,
    'contiguous run': match_contiguous,
    'ordered subseq (dedup)': match_ordered_subsequence_dedup,
    'contiguous run (dedup)': match_contiguous_dedup,
}


def main():
    songs = load()
    print('loaded songs:', len(songs))

    # ground truth per sequence
    truth = {}
    for seq_id in SEQUENCIAS:
        truth[seq_id] = set(s.id_unico for s in songs if str(seq_id) in s.seqs)

    print('\n=== GROUND TRUTH (SEQ_FAMOSA) ===')
    for seq_id, chords in SEQUENCIAS.items():
        print('seq %d %-18s -> %d songs' % (seq_id, ','.join(chords), len(truth[seq_id])))

    print('\n=== ALGORITHM COMPARISON (per sequence) ===')
    for name, fn in ALGOS.items():
        print('\n--- %s ---' % name)
        total_tp = total_fp = total_fn = 0
        for seq_id, chords in SEQUENCIAS.items():
            pred = set(s.id_unico for s in songs if fn(s, chords))
            tp = len(pred & truth[seq_id])
            fp = len(pred - truth[seq_id])
            fnn = len(truth[seq_id] - pred)
            total_tp += tp
            total_fp += fp
            total_fn += fnn
            print('  seq %d: predicted=%-5d TP=%-5d FP=%-5d FN=%-4d' % (seq_id, len(pred), tp, fp, fnn))
        prec = total_tp / (total_tp + total_fp) if total_tp + total_fp else 0
        rec = total_tp / (total_tp + total_fn) if total_tp + total_fn else 0
        print('  TOTAL TP=%d FP=%d FN=%d  precision=%.4f recall=%.4f' % (total_tp, total_fp, total_fn, prec, rec))

    # focus: does set-containment reproduce exactly?
    print('\n=== EXACT MATCH CHECK ===')
    for name, fn in ALGOS.items():
        exact = True
        for seq_id, chords in SEQUENCIAS.items():
            pred = set(s.id_unico for s in songs if fn(s, chords))
            if pred != truth[seq_id]:
                exact = False
        print('  %-26s exact=%s' % (name, exact))

    # sample false positives of set-containment for seq 1 (C,G,Am,F)
    print('\n=== sample set-containment FALSE POSITIVES for seq 1 (C,G,Am,F) ===')
    pred = [s for s in songs if match_set(s, SEQUENCIAS[1])]
    fp = [s for s in pred if s.id_unico not in truth[1]][:5]
    for s in fp:
        print('  %s | cifra=%s' % (s.id_unico, s.cifra[:20]))

    # sample false negatives of set-containment for seq 1
    print('\n=== sample set-containment FALSE NEGATIVES for seq 1 ===')
    fn = [s for s in songs if s.id_unico in truth[1] and not match_set(s, SEQUENCIAS[1])][:5]
    for s in fn:
        print('  %s | cifra=%s | acordes=%s' % (s.id_unico, s.cifra[:20], s.acordes[:20]))

    # how many ground-truth songs even contain all chords?
    print('\n=== ground truth coverage by set-containment ===')
    for seq_id, chords in SEQUENCIAS.items():
        t = [s for s in songs if s.id_unico in truth[seq_id]]
        covered = sum(1 for s in t if match_set(s, chords))
        print('  seq %d: %d/%d truth songs contain all chords' % (seq_id, covered, len(t)))


if __name__ == '__main__':
    main()
