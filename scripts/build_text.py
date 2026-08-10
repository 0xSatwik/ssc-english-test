"""
Two-column PDF -> clean Q./Sol. text stream.
Generalized from the narration build; works for any Pinnacle-format
SSC bank (narration, voice, ...).

Usage:  python build_text.py <in.pdf> <out.txt>
"""
import pdfplumber, collections, re, sys

if len(sys.argv) != 3:
    sys.exit('usage: python build_text.py <in.pdf> <out.txt>')

IN_PDF, OUT_TXT = sys.argv[1], sys.argv[2]

NOISE_EXACT = {
    'Pinnacle', 'Narration', 'NARRATION', 'Active  Passive',
    'Active Passive', 'ACTIVE PASSIVE', 'Examination wise Questions',
    'Examination  wise  Questions', 'Solutions :-', 'SOLUTIONS :-',
    'P innacle', 'innacle', 'Fill in the blanks', 'Fill  in  the  blanks',
    'CLOZE TEST', 'Cloze  Test', 'Comprehension', 'PARA JUMBLE',
    'Para Jumble', 'Parajumble',
}
NOISE_PREFIX = (
    'www.ssccglpinnacle.com', 'TG: @ikunal_x', 'Download Pinnacle',
    'Download PINNACLE', 'Direction', 'Direction :-', 'ACTIVE  PASSIVE',
    'ACTIVE PASSIVE', 'SSC CGL 2025 Tier', 'SSC CGL 2025 (Tier-1)',
    'https://t.me/', 'Telegram',
)
NOISE_SUBSTR = ('Examination wise Questions', 'Direction  :-', 'Direction :-',
                'Read the following passages', 'some words have been deleted')
DATE_RE = re.compile(r'\d{1,2}/\d{1,2}/\d{4}')


def is_noise(s):
    s = s.strip()
    if not s:
        return True
    if s in NOISE_EXACT:
        return True
    # page headers like 'SSC CGL 2025 Tier - I' / 'SSC Selection Post (Phase - XIII)'
    # vs real exam labels like 'SSC CGL 12/09/2025 (Shift 1)' / 'SSC Stenographer 06/08/2025'
    if s.startswith('SSC ') and not DATE_RE.search(s):
        return True
    for p in NOISE_PREFIX:
        if s.startswith(p):
            return True
    for sub in NOISE_SUBSTR:
        if sub in s:
            return True
    if s == 'form of the given sentence.':
        return True
    return False


def column_boundaries(words, gap_threshold=22.0, min_words=30):
    """Find x-midpoints of vertical gutters -> column split points.

    Starts from every >=gap_threshold adjacent-word x0 gap, then merges any
    resulting band that holds too few words (a wrap-line sliver, not a real
    column) into the band to its left.
    """
    xs = sorted(w['x0'] for w in words)
    bds = []
    for i in range(1, len(xs)):
        if xs[i] - xs[i - 1] >= gap_threshold:
            bds.append((xs[i] + xs[i - 1]) / 2.0)
    while True:
        allb = [0.0] + bds + [xs[-1] + 1.0]
        best = None
        for k in range(len(allb) - 1):
            c = sum(1 for w in words if allb[k] <= w['x0'] < allb[k + 1])
            if c < min_words and (best is None or c < best[1]):
                best = (k, c)
        if best is None:
            break
        if best[0] == 0:
            del bds[0]
        else:
            del bds[best[0] - 1]
    return [0.0] + bds + [(xs[-1] if xs else 0) + 1.0]


def col_text(ws):
    buf = collections.OrderedDict()
    for w in sorted(ws, key=lambda w: (round(w['top'] / 2.5), w['x0'])):
        k = round(w['top'] / 2.5)
        nk = None
        for kk in list(buf):
            if abs(kk - k) <= 1:
                nk = kk
                break
        if nk is None:
            buf[k] = [w]
        else:
            buf[nk].append(w)
    clines = []
    for k in sorted(buf.keys()):
        ws2 = sorted(buf[k], key=lambda w: w['x0'])
        clines.append(' '.join(w['text'] for w in ws2).strip())
    return clines


def text_from_words(words):
    bounds = column_boundaries(words)
    cols = []
    for k in range(len(bounds) - 1):
        lo, hi = bounds[k], bounds[k + 1]
        ws = [w for w in words if lo <= w['x0'] < hi]
        cols.append(col_text(ws))
    return cols


def text_from_words_fine(words, gap=5.0):
    """Fallback for pages where two columns sit closer than the normal gap
    threshold: split each visual line into fragments at >=gap horizontal
    breaks, cluster fragments into left->right columns by x0, and emit each
    column's fragments in top-then-x order. Preserves logical column order
    even when the print layout staggers column starts."""
    vlines = {}
    for w in words:
        k = round(w['top'] / 2.5)
        nk = None
        for kk in list(vlines):
            if abs(kk - k) <= 1:
                nk = kk
                break
        if nk is None:
            vlines[k] = []
            nk = k
        vlines[nk].append(w)
    frags = []
    for k in sorted(vlines):
        ws2 = sorted(vlines[k], key=lambda w: w['x0'])
        cur = []
        prev = None
        for w in ws2:
            if prev is not None and w['x0'] - prev >= gap:
                if cur:
                    frags.append(cur)
                cur = []
            cur.append(w)
            prev = w['x1']
        if cur:
            frags.append(cur)
    F = sorted(frags, key=lambda f: min(w['x0'] for w in f))
    cols, curc, prevx = [], [], None
    for f in F:
        x0 = min(w['x0'] for w in f)
        if prevx is not None and x0 - prevx >= gap:
            cols.append(curc)
            curc = []
        curc.append(f)
        prevx = max(w['x1'] for w in f)
    if curc:
        cols.append(curc)
    return [col_text([w for f in cl for w in f]) for cl in cols]


def looks_merged(block):
    return any(re.search(r'(?<!\A) ?\bQ\.\d+\.', ln) or re.search(r'(?<!\A) ?\bSol\.\d+\.', ln)
               or ('S ol.' in ln) for ln in block)


stream = []
with pdfplumber.open(IN_PDF) as pdf:
    for pi, p in enumerate(pdf.pages):
        words = p.extract_words()
        cols = text_from_words(words)
        block = []
        for cl in cols:
            for ln in cl:
                ln = re.sub(r'^Q\.(\d+)(?=\s*\([a-d])', r'Q.\1.', ln)
                if is_noise(ln):
                    continue
                block.append(ln)
        if looks_merged(block):
            cols = text_from_words_fine(words)
            block = []
            for cl in cols:
                for ln in cl:
                    ln = ln.replace('S ol.', 'Sol.')
                    ln = re.sub(r'^Q\.(\d+)(?=\s*\([a-d])', r'Q.\1.', ln)
                    if is_noise(ln):
                        continue
                    block.append(ln)
            fine = True
        else:
            fine = False
        stream.append(block)
        print(f'page {pi}: raw cols={[len(c) for c in cols]} kept={len(block)}'
              + ('  [fine pass]' if fine else ''), file=sys.stderr)

with open(OUT_TXT, 'w', encoding='utf-8') as f:
    for pb in stream:
        f.write('\n'.join(pb) + '\n')

all_lines = [ln for pb in stream for ln in pb]
text = '\n'.join(all_lines)
qm = re.findall(r'Q\.(\d+)\.', text)
sm = re.findall(r'Sol\.(\d+)\.', text)
print('total lines:', len(all_lines))
print('Q markers:', len(qm), qm[:3], qm[-3:])
print('Sol markers:', len(sm), sm[:3], sm[-3:])
print('written:', OUT_TXT)
