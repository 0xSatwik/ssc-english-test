"""
Clean text stream -> JSON question bank.

Usage:  python build_json.py <in.txt> <out.json> --title "..." --topic "..." \
                             --total <n>
"""
import re, json, sys
from collections import Counter

args = sys.argv[1:]
if len(args) < 2:
    sys.exit('usage: python build_json.py <in.txt> <out.json> --title ... --total n')

IN_TXT, OUT_JSON = args[0], args[1]
opts = dict(zip(args[2::2], args[3::2]))
TITLE = opts.get('--title', 'Question Bank')
TOPIC = opts.get('--topic', '')
TOTAL = int(opts.get('--total', 0))

lines = open(IN_TXT, encoding='utf-8').read().splitlines()
lines = [ln.replace('S SC ', 'SSC ').replace('S  C ', 'SSC ') for ln in lines]

q_re = re.compile(r'^Q\.(\d+)\.\s?(.*)$')
s_re = re.compile(r'^Sol\.(\d+)\.\s?\(([abcd])\)\s?(.*)$')
exam_re = re.compile(r'(SSC CGL|SSC Stenographer|Higher Secondary|Graduate Level|Matriculation Level)[^\n]*?(Shift[^\n]*)?\s*\d{1,2}/\d{1,2}/\d{4}[^\n]*')
date_re = re.compile(r'(\d{1,2})/(\d{1,2})/(\d{4})')
opt_re = re.compile(r'^\(([abcd])\)\s?(.*)$')

NOISE_EXACT = {
    'Pinnacle', 'Narration', 'NARRATION', 'Active  Passive', 'Active Passive',
    'ACTIVE PASSIVE', 'Examination wise Questions', 'Examination  wise  Questions',
    'Solutions :-', 'SOLUTIONS :-', 'P innacle', 'innacle', 'Fill in the blanks',
    'Fill  in  the  blanks', 'CLOZE TEST', 'Cloze  Test', 'Comprehension',
    'PARA JUMBLE', 'Para Jumble', 'Parajumble', 'Exam Preparation App',
    'Exam  Preparation  App', 'Download Pinnacle', 'Solutions : -',
    'www.ssccglpinnacle.com', 'TG: @ikunal_x', 'eduquity-based pattern (ebp)',
}
NOISE_SUBSTR = ('Examination wise Questions', 'Direction  :-', 'Direction :-',
                'Read the following passages', 'some words have been deleted')
RANGE_RE = re.compile(r'Questions\s*\((\d+)\s*to\s*(\d+)\)')
DATE_RE = re.compile(r'\d{1,2}/\d{1,2}/\d{4}')


def is_noise(s):
    s = s.strip()
    if not s:
        return True
    if s in NOISE_EXACT:
        return True
    if s.startswith('SSC ') and not DATE_RE.search(s):
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


def clean_text(s):
    return s.replace('\u30fc', '-').replace('\uff0d', '-').replace('\u2192', '-') \
            .replace('\u2794', '-').replace('\u27a1', '-').replace('\u279c', '-')

events = []
for i, ln in enumerate(lines):
    m = q_re.match(ln)
    if m:
        events.append([i, 'Q', int(m.group(1)), m.group(2)])
        continue
    m = s_re.match(ln)
    if m:
        events.append([i, 'S', int(m.group(1)), m.group(2), m.group(3)])
        continue

qnums = [e[2] for e in events if e[1] == 'Q']
snums = [e[2] for e in events if e[1] == 'S']
if TOTAL:
    assert qnums == list(range(1, TOTAL + 1)), 'Q numbering broken'
else:
    assert qnums == list(range(1, len(qnums) + 1)), 'Q numbers not sequential'

# cloze / comprehension books print the set's exam label + passage *above* the
# questions. Track the pending exam for every book so per-question blocks that
# sit after a SET header can fall back to it; passage is cloze-only.
INLINE = any(re.search(r'\([a-d]\)', e[3]) for e in events if e[1] == 'Q')
has_sets = any(re.match(r'^SET[-\s]+\d', ln) or ln.startswith('SET-')
               for ln in lines)
exam_for = {}
passage_for = {}
set_of = {}
cur_exam, cur_passage = None, None
cur_set = 0
for i, ln in enumerate(lines):
    if ln.startswith('SET-') or re.match(r'^SET[-\s]+\d', ln) \
            or re.match(r'^Questions\s*\(', ln):
        if re.match(r'^SET[-\s]+\d', ln) or ln.startswith('SET-'):
            cur_exam, cur_passage, cur_set = None, None, cur_set + 1
    elif exam_re.search(ln) and DATE_RE.search(ln):
        cur_exam = ln.strip()
    m = q_re.match(ln)
    if m:
        qn = int(m.group(1))
        set_of[qn] = cur_set
        if cur_exam is not None:
            exam_for[qn] = cur_exam
        if INLINE and cur_passage is None:
            head = 0
            for back in range(i - 1, -1, -1):
                if re.match(r'^SET[-\s]+\d', lines[back]) or lines[back].startswith('SET-'):
                    head = back + 1
                    break
            cur_passage = '\n'.join(
                ln2 for ln2 in lines[head:i]
                if ln2.strip() and not (exam_re.search(ln2) and DATE_RE.search(ln2)))
        elif has_sets and cur_passage is None:
            head = 0
            for back in range(i - 1, -1, -1):
                if re.match(r'^SET[-\s]+\d', lines[back]) or lines[back].startswith('SET-'):
                    head = back + 1
                    break
            cur_passage = '\n'.join(
                ln2 for ln2 in lines[head:i]
                if ln2.strip() and not (exam_re.search(ln2) and DATE_RE.search(ln2))
                and not is_noise(ln2))
        if INLINE or has_sets:
            passage_for[qn] = cur_passage

runs = []
for e in events:
    if runs and runs[-1][0] == e[1]:
        runs[-1][1].append(e)
    else:
        runs.append([e[1], [e]])
for rk in range(len(runs)):
    if runs[rk][0] != 'S':
        continue
    j = rk - 1
    while j >= 0 and runs[j][0] != 'Q':
        j -= 1
    assert j >= 0 and len(runs[j][1]) == len(runs[rk][1]), \
        f'Sol run {rk} length mismatch vs preceding Q run'
print('Q seq ok:', len(qnums), 'questions,', len(snums), 'solutions,',
      len(runs) // 2, 'question/solution sections')

questions = []
missing_exam = []
last_exam_type = 'SSC CGL 2025 (Tier-1)'
practice_ranges = [tuple(map(int, m.groups()))
                   for m in (RANGE_RE.search(ln) for ln in lines) if m]
is_practice = lambda qnum: any(a <= qnum <= b for a, b in practice_ranges)

for eidx, e in enumerate(events):
    if e[1] != 'Q':
        continue
    nxt = events[eidx + 1][0] if eidx + 1 < len(events) else len(lines)
    body = lines[e[0] + 1:nxt]
    if INLINE:
        body = [ln for ln in body if re.search(r'\([a-d]\)', ln)]
    qnum = e[2]
    prompt_lines = []
    opts = []
    if INLINE:
        chunks = re.split(r'\(([a-d])\)', e[3])
        head = chunks[0].strip()
        if head:
            prompt_lines.append(head)
        for k in range(1, len(chunks), 2):
            opts.append(chunks[k + 1].strip())
    else:
        prompt_lines.append(e[3])
    exam = None
    exam_head = []
    for line in body:
        if re.match(r'^SET[-\s]+\d', line) or re.match(r'^Questions\s*\(', line):
            break
        exam_head.append(line)
    for i, line in enumerate(exam_head):
        m = exam_re.search(line)
        if m:
            exam = m.group(0).strip()
            rest = line[m.end():].strip()
            body = body[:i] + ([rest] if rest else []) + body[i + 1:]
            break
    if exam is None:
        exam = exam_for.get(qnum)
    if exam is None:
        missing_exam.append(qnum)
        exam = last_exam_type

    cur = None
    for line in body:
        if not line.strip():
            continue
        if re.match(r'^SET[-\s]+\d', line) or re.match(r'^Questions\s*\(', line):
            break
        if is_noise(line):
            continue
        chunks = re.split(r'\(([a-d])\)', line)
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

    prompt = clean_text(' '.join(' '.join(prompt_lines).split()).strip())
    if INLINE and qnum in passage_for and passage_for[qnum].strip():
        prompt = clean_text(' '.join(passage_for[qnum].split()).strip())
    passage = ''
    if not INLINE:
        p = passage_for.get(qnum)
        if p:
            p = clean_text(' '.join(p.split()).strip())
            if p and p != prompt:
                passage = p
    if len(opts) != 4:
        print(f'WARN Q{qnum}: {len(opts)} options -> {opts}')
        continue
    dm = date_re.search(exam)
    year = dm.group(3) if dm else '2025'
    if is_practice(qnum):
        exam_type, exam_full = 'Pinnacle Practice Set', 'Pinnacle Practice Set'
    elif exam.startswith('SSC CGL'):
        exam_type, exam_full = 'SSC CGL 2025 (Tier-1)', exam
    elif exam.startswith('SSC Stenographer'):
        exam_type, exam_full = 'SSC Stenographer 2025 (Tier-1)', exam
    elif exam.startswith('Higher Secondary') or exam.startswith('Graduate Level') or exam.startswith('Matriculation Level'):
        exam_type, exam_full = 'SSC Selection Post (Phase-XIII) 2025', 'SSC Selection Post (Phase-XIII) - ' + exam
    else:
        exam_type, exam_full = exam, exam
    last_exam_type = exam_type
    questions.append({
        'id': qnum, 'prompt': prompt,
        'options': [clean_text(o.strip()) for o in opts],
        'exam': clean_text(exam_full), 'examType': exam_type, 'year': year,
        'setId': set_of.get(qnum, 0),
        'passage': passage,
        'answer': None, 'explanation': None,
    })

sols = {}
for rk in range(len(runs)):
    if runs[rk][0] != 'S':
        continue
    j = rk - 1
    while j >= 0 and runs[j][0] != 'Q':
        j -= 1
    if j < 0:
        continue
    qevents = runs[j][1]
    for order, se in enumerate(runs[rk][1]):
        if order >= len(qevents):
            break
        qnum = qevents[order][2]
        letter = se[3]
        ei = events.index(se)
        nxt = events[ei + 1][0] if ei + 1 < len(events) else len(lines)
        body = lines[se[0] + 1:nxt]
        expl_lines = ['(' + letter + ') ' + clean_text(se[4]).strip()]
        for line in body:
            s = line.strip()
            if not s:
                continue
            if is_noise(s):
                continue
            if s in ('SSC Selection Post (Phase - XIII)', 'SSC Selection Post (Phase - XIII) 2025',
                     'SSC CGL 2025 Tier - I', 'SSC CGL 2025 Tier - 1', 'SSC Stenographer 2025 Tier - 1'):
                continue
            expl_lines.append(clean_text(s))
        sols[qnum] = {'letter': letter, 'explanation': '\n'.join(expl_lines)}

alphabet = 'abcd'
mismatch = 0
norm = lambda x: re.sub(r'[\s\u2018\u2019\u201c\u201d\ufffd\u2013\u2014\u2010\u2212.\uff0d\u30fc\uff0c(,)・\-;\u00a0\u2192\u2794\u27a1\u279c\u300a\u300b]', '', x).replace("'", '').replace('"', '').lower()
for q in questions:
    sol = sols[q['id']]
    q['answer'] = alphabet.index(sol['letter'])
    q['explanation'] = sol['explanation']
    if norm(q['options'][q['answer']]) not in norm(sol['explanation']):
        mismatch += 1
        print(f'CHECK Q{q["id"]} letter={sol["letter"]}: correct option not found in explanation.')
    # normalize: guarantee the answer option is tagged (Correct) once
    if '(Correct)' not in q['explanation']:
        ans_letter = sol['letter']
        lines = q['explanation'].splitlines()
        cur, tagged = None, False
        opt_start = re.compile(r'^\s*\(([a-d])\)\s?(.*)$')
        for i, ln in enumerate(lines):
            m = opt_start.match(ln)
            if m:
                if cur == ans_letter and not tagged:
                    lines[i - 1] = lines[i - 1] + ' (Correct)'
                    tagged = True
                cur = m.group(1)
        if cur == ans_letter and not tagged:
            lines[-1] = lines[-1] + ' (Correct)'
        q['explanation'] = '\n'.join(lines)

print('missing exam:', missing_exam)
print('questions:', len(questions))
print('answer-vs-explanation mismatches:', mismatch)
print('examType distribution:', dict(Counter([q['examType'] for q in questions])))

meta = {
    'title': TITLE,
    'subject': 'English',
    'topic': TOPIC,
    'defaultSecondsPerQuestion': 30,
    'source': 'Pinnacle',
    'language': 'English',
    'totalQuestions': len(questions),
}
out = {'meta': meta, 'questions': questions}
with open(OUT_JSON, 'w', encoding='utf-8') as f:
    json.dump(out, f, ensure_ascii=False, indent=2)
print('written', OUT_JSON, len(questions))