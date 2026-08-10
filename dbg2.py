import sys, pdfplumber
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
with pdfplumber.open(r'pdfs\fill in the blanks.pdf') as pdf:
    for pi in (6, 7, 8):
        ws = pdf.pages[pi].extract_words()
        xs = sorted(w['x0'] for w in ws)
        gaps = []
        for i in range(1, len(xs)):
            if xs[i] - xs[i - 1] >= 18:
                gaps.append((round(xs[i - 1]), round(xs[i])))
        print('PAGE', pi, 'gaps>=18:', gaps)
        # cluster words into columns using the boundary gaps
        bounds = [0]
        for i in range(1, len(xs)):
            if xs[i] - xs[i - 1] >= 18:
                bounds.append(round((xs[i] + xs[i - 1]) / 2))
        bounds.append(10 ** 9)
        cols = [[] for _ in range(len(bounds) - 1)]
        for w in ws:
            for k in range(len(bounds) - 1):
                if bounds[k] <= w['x0'] < bounds[k + 1]:
                    cols[k].append(w)
                    break
        for k, c in enumerate(cols):
            tops = sorted(round(x['top'] / 2.5) for x in c)
            span = (tops[0], tops[-1])
            print('  col%d x[%d,%d] lines~%d..%d' % (k, bounds[k], bounds[k + 1] if bounds[k + 1] < 10 ** 9 else 999, span[0], span[1]))
        # per col, first 2 and last 2 words (by top,x0)
        for k, c in enumerate(cols):
            cs = sorted(c, key=lambda w: (round(w['top'] / 2.5), w['x0']))
            top_lines = {}
            for w in cs:
                top_lines.setdefault(round(w['top'] / 2.5), []).append(w)
            keys = sorted(top_lines)
            print('  col%d first:%r' % (k, [' '.join(w['text'] for w in top_lines[keys[0]])[:60]]))
            print('  col%d last :%r' % (k, [' '.join(w['text'] for w in top_lines[keys[-1]])[:60]]))