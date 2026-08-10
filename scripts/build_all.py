"""
Regenerate every chapter bank from its PDF into public/subjects/,
verify each independently, and write public/manifest.json for the site.

Usage:  python build_all.py
"""
import json, subprocess, sys, os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

SUBJECTS = [
    {
        'pdf': 'pdfs/narration.pdf',
        'file': 'public/subjects/narration.json',
        'title': 'Narration - Direct & Indirect Speech (238 Questions)',
        'topic': 'Direct / Indirect Speech (Narration)',
        'total': 238,
        'meta': {
            'icon': '💬', 'subtitle': 'Direct & Indirect Speech',
            'color': '#3b82f6', 'tag': '12/09 - 14/10 2025', 'order': 1,
        },
    },
    {
        'pdf': 'pdfs/voice.pdf',
        'file': 'public/subjects/voice.json',
        'title': 'Voice - Active & Passive Voice (250 Questions)',
        'topic': 'Active / Passive Voice',
        'total': 250,
        'meta': {
            'icon': '🗣️', 'subtitle': 'Active ↔ Passive conversion',
            'color': '#8b5cf6', 'tag': '12/09 - 19/09 2025', 'order': 2,
        },
    },
]

def run(cmd):
    print('$', ' '.join(cmd))
    r = subprocess.run(cmd, cwd=ROOT)
    if r.returncode != 0:
        sys.exit(f'command failed: {" ".join(cmd)}')

manifest = {'siteTitle': 'SSC English Practice Lab', 'subjects': []}

for s in SUBJECTS:
    stem = 'build_' + os.path.splitext(os.path.basename(s['pdf']))[0] + '.txt'
    txt = stem
    run([sys.executable, 'scripts/build_text.py', s['pdf'], txt])
    run([sys.executable, 'scripts/build_json.py', txt, s['file'],
         '--title', s['title'], '--topic', s['topic'], '--total', str(s['total'])])
    run([sys.executable, 'scripts/verify_json.py', s['pdf'], s['file']])

    with open(os.path.join(ROOT, s['file']), encoding='utf-8') as f:
        bank = json.load(f)
    with open(os.path.join(ROOT, txt), encoding='utf-8') as f:
        n_lines = f.read().count('\n')

    manifest['subjects'].append({
        'id': os.path.splitext(os.path.basename(s['pdf']))[0],
        'title': bank['meta']['title'],
        'topic': bank['meta']['topic'],
        'file': 'subjects/' + os.path.basename(s['file']),
        'total': len(bank['questions']),
        'exams': sorted({q['examType'] for q in bank['questions']}),
        **s['meta'],
    })
    if os.path.exists(os.path.join(ROOT, txt)):
        os.remove(os.path.join(ROOT, txt))

with open(os.path.join(ROOT, 'public/manifest.json'), 'w', encoding='utf-8') as f:
    json.dump(manifest, f, ensure_ascii=False, indent=2)
print('manifest.json written:', len(manifest['subjects']), 'subjects')