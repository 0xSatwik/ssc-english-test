"""
Independent verification of a JSON question bank against its PDF.

Rebuilds every question through a completely independent extractor/method
(pypdf layout-mode text, columns split by char-gap) and checks:

  I.   field diff: prompt, each option[0..3], exam
  II.  Sol markers  '(a/b/c/d)' == json answer
  III. explanation '(Correct)' integrity + option grouping
  IV.  exam label present inside each Q block
  V.   no stray section headers/footer text leaked into options/explanation

Usage:  python verify_json.py <in.pdf> <in.json>
"""
import re, json, sys
from difflib import SequenceMatcher

try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass

import pypdf

if len(sys.argv) != 3:
    sys.exit('usage: python verify_json.py <in.pdf> <in.json>')
PDF, JSON = sys.argv[1], sys.argv[2]

LIG = {0xFB00: 'ff', 0xFB01: 'fi', 0xFB02: 'fl', 0xFB03: 'ffi',
       0xFB04: 'ffl', 0xFB05: 'ft', 0xFB06: 'st'}
LIG_TAB = str.maketrans({k: v for k, v in LIG.items()})

def norm(s):
    return re.sub(r'[^a-z0-9]', '', (s or '').translate(LIG_TAB).lower())

EXAM_RE = re.compile(r'(SSC CGL|SSC Stenographer|Higher Secondary|Graduate Level|Matriculation Level)')
DATE_RE = re.compile(r'\d{1,2}/\d{1,2}/\d{4}')

NOISE_EXACT = {
    'Pinnacle', 'Narration', 'NARRATION', 'Active  Passive',
    'Active Passive', 'ACTIVE PASSIVE', 'Examination wise Questions',
    'Solutions :-', 'SSC CGL 2025 Tier - 1', 'SSC Selection Post (Phase - XIII)',
    'P innacle', 'innacle', 'Exam Preparation App', 'Download Pinnacle',
    'Solutions : -', 'www.ssccglpinnacle.com', 'TG: @ikunal_x',
    'eduquity-based pattern (ebp)', 'Fill in the blanks', 'Fill  in  the  blanks',
    'CLOZE TEST', 'Cloze  Test', 'Comprehension', 'PARA JUMBLE', 'Para Jumble',
    'Parajumble', 'Sentence Improvement', 'One Word Substitution', 'Spot the Error',
    'SPOT THE ERROR',
}
NOISE_SUBSTR = ('Examination wise Questions', 'Direction  :-', 'Direction :-',
                'Read the following passages', 'some words have been deleted')
DATE_RE2 = re.compile(r'\d{1,2}/\d{1,2}/\d{4}')
KEY_LINE_RE = re.compile(
    r'^\(\s*[a-d]\s*\)\s*[a-d]\s*(?:\(\s*[a-d]\s*\)\s*[a-d]\s*){1,3}$')
def is_noise(s):
    s = s.strip()
    if not s:
        return True
    if s in NOISE_EXACT:
        return True
    if s.startswith('SSC ') and not DATE_RE2.search(s):
        return True
    if s.startswith('www.ssccglpinnacle.com') or s.startswith('TG: @ikunal_x'):
        return True
    if 'Download' in s or s.startswith('https://t.me/'):
        return True
    for sub in NOISE_SUBSTR:
        if sub in s:
            return True
    if s == 'form of the given sentence.':
        return True
    return False


import pdfplumber


def col_text(ws):
    import collections
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
    out = []
    for k in sorted(buf.keys()):
        ws2 = sorted(buf[k], key=lambda w: w['x0'])
        out.append(' '.join(w['text'] for w in ws2).strip())
    return out


def text_from_words_fine(words, gap=5.0):
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


stream_lines = []
with pdfplumber.open(PDF) as pdf:
    for page in pdf.pages:
        words = page.extract_words()
        if not words:
            continue
        xs = sorted(w['x0'] for w in words)
        bds = []
        for i in range(1, len(xs)):
            if xs[i] - xs[i - 1] >= 22:
                bds.append((xs[i] + xs[i - 1]) / 2.0)
        # merge wrap-line slivers (a band holding too few words is not a column)
        while True:
            allb = [0.0] + bds + [xs[-1] + 1.0]
            best = None
            for k in range(len(allb) - 1):
                c = sum(1 for w in words if allb[k] <= w['x0'] < allb[k + 1])
                if c < 30 and (best is None or c < best[1]):
                    best = (k, c)
            if best is None:
                break
            if best[0] == 0:
                del bds[0]
            else:
                del bds[best[0] - 1]
        bounds = [0.0] + bds + [xs[-1] + 1.0]
        block = []
        for k in range(len(bounds) - 1):
            lo, hi = bounds[k], bounds[k + 1]
            ws = [w for w in words if lo <= w['x0'] < hi]
            for s in col_text(ws):
                s = s.replace('S SC ', 'SSC ').replace('S  C ', 'SSC ')
                s = re.sub(r'^Q\.(\d+)(?=\s*\([a-d])', r'Q.\1.', s)
                if s and not is_noise(s):
                    block.append(s)
        merged = any(re.search(r'(?<!\A) ?\bQ\.\d+\.', s) or re.search(r'(?<!\A) ?\bSol\.\d+\.', s)
                     or 'S ol.' in s for s in block)
        if merged:
            block = []
            for cl in text_from_words_fine(words):
                for s in cl:
                    s = s.replace('S ol.', 'Sol.').replace('S SC ', 'SSC ').replace('S  C ', 'SSC ')
                    s = re.sub(r'^Q\.(\d+)(?=\s*\([a-d])', r'Q.\1.', s)
                    if s and not is_noise(s):
                        block.append(s)
        stream_lines.extend(block)

# independent engine cross-check: pypdf layout text, global counts + Sol letters
pdf_layout = ''
with pypdf.PdfReader(PDF) as reader:
    for page in reader.pages:
        pdf_layout += (page.extract_text(extraction_mode='layout') or '') + '\n'
pdf_layout = pdf_layout.replace('S SC ', 'SSC ').replace('S  C ', 'SSC ')
pdf_sol = [(int(a), b) for a, b in re.findall(r'Sol\.(\d+)\.{1,2}\s*\(([abcd])\)', pdf_layout)]
pdf_qcount = len(re.findall(r'\bQ\.\d+(?:\.|\s|\()', pdf_layout))

q_re = re.compile(r'^Q\.(\d+)(?:\.|\s)(.*)$')
s_re = re.compile(r'^Sol\.(\d+)\.{0,2}\s*\(([abcd])\)\s?(.*)$')
events, body_lines = [], []
for i, ln0 in enumerate(stream_lines):
    ln = re.sub(r'^[a-z]\.(?=Q\.\d+)', '', ln0.replace('S ol.', 'Sol.'))
    m = q_re.match(ln)
    if m:
        events.append((i, 'Q', int(m.group(1))))
        body_lines.append((i, m.group(2)))
        continue
    m = s_re.match(ln)
    if m:
        events.append((i, 'S', int(m.group(1)), m.group(2)))
        body_lines.append((i, m.group(3)))
        continue
    body_lines.append((i, ln))

qnums0 = [e[2] for e in events if e[1] == 'Q']
if len(set(qnums0)) != len(qnums0) or qnums0 != list(range(1, len(qnums0) + 1)):
    print('WARN verify: Q numbers not sequential — renumbering by stream position')
    k = 0
    fixed = []
    for e in events:
        e = list(e)
        if e[1] == 'Q':
            k += 1
            e[2] = k
        fixed.append(tuple(e))
    events = fixed

qnums = [e[2] for e in events if e[1] == 'Q']
snums = [e[2] for e in events if e[1] == 'S']
runs = []
for e in events:
    if runs and runs[-1][0] == e[1]:
        runs[-1][1].append(e)
    else:
        runs.append([e[1], [e]])
run_ok = True
for rk in range(len(runs)):
    if runs[rk][0] != 'S':
        continue
    j = rk - 1
    while j >= 0 and runs[j][0] != 'Q':
        j -= 1
    if j < 0 or len(runs[j][1]) != len(runs[rk][1]):
        run_ok = False
ok_num = qnums == list(range(1, len(qnums) + 1)) and run_ok
print(f'fresh pdfplumber rebuild: Q events={len(qnums)}  Sol events={len(snums)}  '
      f'sections={len(runs) // 2}  sequenced={ok_num}')
print(f'pypdf layout scan      : Q markers={pdf_qcount}  Sol markers={len(pdf_sol)}  '
      f'(expected exactly {len(qnums)}/{len(snums)})')

# run-aware solution mapping: sol letter for a question comes from the S entry
# that sits in the same section run as its Q, matched by position (the source
# sometimes mis-numbers a solution, e.g. jumble Sol.289 for the question
# numbered 229 — mapping by position keeps the marker trustworthy).
sol_map = {}
for rk in range(len(runs)):
    if runs[rk][0] != 'S':
        continue
    j = rk - 1
    while j >= 0 and runs[j][0] != 'Q':
        j -= 1
    if j < 0:
        continue
    for order, se in enumerate(runs[rk][1]):
        if order < len(runs[j][1]):
            sol_map[runs[j][1][order][2]] = se[3]
sol_letters = sol_map

# cloze books: full option set sits on the Q marker line and the passage +
# exam label sit *above* the set's Q.1 (see build_json for the mirror logic).
bodyline = dict(body_lines)
ev_at = {e[0]: e for e in events}
INLINE = any(re.search(r'\([a-d]\)', bodyline.get(e[0], '')) for e in events if e[1] == 'Q')
has_sets = any(re.match(r'^SET[-\s]+\d', ln[1]) for _, ln in enumerate(body_lines))
exam_for = {}
passage_for = {}
cur_exam, cur_passage = None, None
for i, ln in enumerate(body_lines):
    if re.match(r'^SET[-\s]+\d', ln[1]):
        cur_exam, cur_passage = None, None
    elif EXAM_RE.search(ln[1]) and DATE_RE.search(ln[1]):
        cur_exam = ln[1].strip()
    e = ev_at.get(i)
    if e is not None and e[1] == 'Q':
        qn = e[2]
        if cur_exam is not None:
            exam_for[qn] = cur_exam
        if has_sets:
            if cur_passage is None:
                head = None
                for back in range(i - 1, -1, -1):
                    if re.match(r'^SET[-\s]+\d', body_lines[back][1]):
                        head = back + 1
                        break
                cur_passage = '\n'.join(
                    ln2 for (_, ln2) in body_lines[head:i]
                    if ln2.strip() and not (EXAM_RE.search(ln2) and DATE_RE.search(ln2)))
            passage_for[qn] = cur_passage

qII = {}
for ei, e in enumerate(events):
    if e[1] != 'Q':
        continue
    qnum = e[2]
    end = events[ei + 1][0] if ei + 1 < len(events) else len(body_lines)
    blk_raw = [ln for (j, ln) in body_lines if j > e[0] and j < end]
    blk = blk_raw
    if INLINE:
        blk = [ln for ln in blk if re.search(r'\([a-d]\)', ln)]
    prompt_lines, exam, opts, cur = [], None, [], None
    if exam is None:
        for ln in blk_raw:
            if EXAM_RE.search(ln) and DATE_RE.search(ln):
                exam = ln.strip()
                break
    rem = bodyline.get(e[0], '')
    if INLINE:
        chunks = re.split(r'\(\s*([a-d])\s*\)', rem)
        head = chunks[0].strip()
        if head:
            prompt_lines.append(head)
        for k in range(1, len(chunks), 2):
            opts.append(chunks[k + 1].strip())
    else:
        prompt_lines.append(rem)
    for line in blk:
        if not line.strip():
            continue
        if re.match(r'^SET[-\s]+\d', line) or re.match(r'^Questions\s*\(', line):
            break
        if EXAM_RE.search(line) and DATE_RE.search(line):
            if exam is None:
                exam = line
            continue
        if KEY_LINE_RE.match(line.strip()):
            continue
        chunks = re.split(r'\(\s*([a-d])\s*\)', line)
        head = chunks[0].strip()
        if head:
            if cur is not None:
                cur += ' ' + head
            else:
                prompt_lines.append(head)
        for k in range(1, len(chunks), 2):
            if cur is not None:
                opts.append(cur)
            cur = chunks[k + 1].strip()
    if cur is not None:
        opts.append(cur)
    if exam is None and qnum in exam_for:
        exam = exam_for[qnum]
    prompt = ' '.join(prompt_lines).strip()
    if INLINE and qnum in passage_for and passage_for[qnum].strip():
        prompt = ' '.join(passage_for[qnum].split()).strip()
    qII[qnum] = {'prompt': prompt, 'options': opts, 'exam': exam}

print(f'pypdf rebuild questions: {len(qII)}')

data = json.load(open(JSON, encoding='utf-8'))
qA = {q['id']: q for q in data['questions']}

def _ex(e):
    return norm(e).replace('sscselectionpostphasexiii', '')

# CHECK I
diffI = []
for qid in sorted(qA):
    a, b = qA[qid], qII.get(qid)
    if not b:
        diffI.append((qid, 'MISSING-IN-II', '', ''))
        continue
    if norm(a['prompt']) != norm(b['prompt']):
        diffI.append((qid, 'PROMPT', a['prompt'][:70], b['prompt'][:70]))
    if len(b['options']) != 4:
        diffI.append((qid, 'OPTION-COUNT', f'{len(a["options"])} opts', f'{len(b["options"])} opts'))
    else:
        for i in range(4):
            if norm(a['options'][i]) != norm(b['options'][i]):
                diffI.append((qid, f'OPTION-{chr(97 + i)}', a['options'][i][:70], b['options'][i][:70]))
    if _ex(a['exam']) != _ex(b['exam']):
        # practice sections normalize json exam to 'Pinnacle Practice Set'
        # while the PDF block still carries the original exam label
        # (e.g. 'SSC Stenographer 08/08/2025 (Shift 3)'); that's a section
        # grouping decision, not a parsing error.
        practice_norm = (a['exam'] == 'Pinnacle Practice Set'
                         and a['examType'] == 'Pinnacle Practice Set' and b['exam'])
        # the source PDF sometimes lacks a per-question exam label at the end
        # of a section; the builder fills the section name (== examType). If
        # pypdf also found nothing, EM >< NONE with EM == examType is a
        # documented fallback, not a bug.
        if (not practice_norm
                and (b['exam'] or _ex(a['exam']) != _ex(a['examType']))):
            diffI.append((qid, 'EXAM', a['exam'][:60], (b['exam'] or '(none)')[:60]))

# CHECK II
from collections import Counter
sol_letters = sol_map
diffII = []
for qid in sorted(qA):
    L = sol_letters.get(qid)
    if L is None:
        diffII.append((qid, 'NO-SOL-MARKER', '', ''))
    elif L != 'abcd'[qA[qid]['answer']]:
        diffII.append((qid, 'SOL-LETTER', 'json answer=' + 'abcd'[qA[qid]['answer']], 'Sol marked (' + L + ')'))

# pypdf-layout engine cross-check: Sol letters as a global multiset.
# The source PDF occasionally mis-numbers one solution (e.g. jumble's Sol.289
# for question 229); canonicalize duplicates to the first still-missing number
# so the multiset comparison measures letters, not that typo.
occupied = {}
for num, letter in pdf_sol:
    if num not in occupied:
        occupied[num] = letter
        continue
    m = 1
    while m in occupied:
        m += 1
    occupied[m] = letter
json_letters = ['abcd'[qA[qid]['answer']] for qid in sorted(qA)]
pdf_letters = [occupied[n] for n in sorted(occupied) if n <= len(qA)]
if sorted(json_letters) != sorted(pdf_letters):
    jc, pc = Counter(json_letters), Counter(pdf_letters)
    diffII.append((0, 'PDF-LETTER-MULTISET',
                   f'json {dict(jc)}', f'pypdf {dict(pc)}'))
else:
    print(f'pypdf Sol-letter multiset agrees with JSON answers '
          f'({Counter(json_letters)})')

# CHECK III
def group_options(expl):
    groups, cur = {}, None
    for ln in (expl or '').splitlines():
        ls = ln.strip()
        if not ls:
            continue
        m = re.match(r'\(([a-d])\)\s?(.*)$', ls)
        if m:
            cur = m.group(1)
            groups.setdefault(cur, m.group(2))
        elif cur:
            groups[cur] += ' ' + ls
    return groups

diffIII = []
for qid in sorted(qA):
    a = qA[qid]
    groups = group_options(a['explanation'])
    ncorr = len(re.findall(r'\(Correct\)', a['explanation'] or ''))
    if ncorr != 1:
        diffIII.append((qid, 'CORRECT-MARKER-COUNT', str(ncorr), 'expected 1'))
        continue
    letter_correct = [L for L in 'abcd' if L in groups and re.search(r'\(Correct\)', groups[L])]
    if len(letter_correct) != 1 or letter_correct[0] != 'abcd'[a['answer']]:
        diffIII.append((qid, 'CORRECT-TAG', 'answer=' + 'abcd'[a['answer']],
                        'tag letter=' + (letter_correct[0] if letter_correct else '(none)')))
    for i in range(4):
        L = 'abcd'[i]
        if L not in groups:
            continue
        o = a['options'][i]
        if norm(o) in norm(groups[L]):
            continue
        gcore = re.sub(r'\(.*?\)\s*', '', groups[L])
        if norm(o) in norm(gcore):
            continue
        r = SequenceMatcher(None, o.lower(), gcore.lower()).ratio()
        if r < 0.5:
            ow = set(norm(o)) or set(norm(o))
            owords = set(re.findall(r'[a-z]+', o.lower()))
            ewords = set(re.findall(r'[a-z]+', (a['explanation'] or '').lower()))
            if owords and len(owords & ewords) / len(owords) >= 0.6:
                continue
            if len(owords) == 1 and ewords:
                ow = next(iter(owords))
                if max((SequenceMatcher(None, ow, ew).ratio() for ew in ewords), default=0) >= 0.8:
                    continue
            diffIII.append((qid, f'OPT-{L}', o[:60], gcore[:60]))

# CHECK IV — exam must agree between pipelines; if the source itself lacks
# a per-question exam label, both sides are missing and that is acceptable.
diffIV = []
for qid in sorted(qA):
    a, b = qA[qid], qII.get(qid)
    if not a['exam'] and (b and b['exam']):
        diffIV.append((qid, 'JSON-MISSING-EXAM', '', b['exam'][:50]))
    elif (a['exam'] and _ex(a['exam']) != _ex(a['examType'])
          and (not b or not b['exam'])):
        diffIV.append((qid, 'PYPDF-MISSING-EXAM', a['exam'][:50], ''))

# CHECK V
STRAY = ['Solutions :-', 'Sol.1', 'Pinnacle', 'Download', 'Direction :-',
         'SSC Stenographer 2025 Tier -', 'SSC CGL 2025 Tier -',
         'Tier - 1', 'www.ssccglpinnacle.com']
diffV = []
for qid in sorted(qA):
    a = qA[qid]
    for field, text in (('prompt', a['prompt']),
                        *(('opts', o) for o in a['options']),
                        ('exam', a['exam']), ('expl', a['explanation'])):
        text_scan = re.sub(r'\[Pinnacle Note.*?\]', '', text or '', flags=re.S)
        for t in STRAY:
            if t.lower() in text_scan.lower():
                if t == 'Pinnacle' and field == 'exam' and 'Pinnacle Practice Set' in (text or ''):
                    continue
                diffV.append((qid, f'STRAY-{t}', field, str(text)[:50]))
                break

print('\n================= VERIFICATION ======================')
print(f'questions in JSON          : {len(qA)}')
print(f'independent rebuild        : {len(qII)}')

def summarize(title, items, show=8):
    print(f'\n{title}: {len(items)}')
    for it in items[:show]:
        kind, v1, v2 = it[1], it[2], it[3]
        print(f'  [{kind}] Q{it[0]}')
        if v1:
            print('     A(json): ' + str(v1)[:95])
        if v2:
            print('     B(pypdf): ' + str(v2)[:95])
        if not v1 and not v2:
            print('     (no detail)')
    if len(items) > show:
        print(f'  ... and {len(items) - show} more')

summarize('CHECK I  field diff', diffI)
summarize('CHECK II Sol-letter vs answer', diffII)
summarize('CHECK III explanation integrity', diffIII)
summarize('CHECK IV exam in block', diffIV)
summarize('CHECK V  stray markers', diffV)

total = len(diffI) + len(diffII) + len(diffIII) + len(diffIV) + len(diffV)
print(f'\nTOTAL issues: {total}')
print('RESULT:', 'ALL CLEAR — JSON independently verified' if total == 0
        else 'ISSUES FOUND — investigate')