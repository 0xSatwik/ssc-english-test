import sys, pdfplumber, collections
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
with pdfplumber.open(r'pdfs\fill in the blanks.pdf') as pdf:
    for pi in (5, 6):
        ws = pdf.pages[pi].extract_words()
        xs = sorted(w['x0'] for w in ws)
        bounds = [0]
        for i in range(1, len(xs)):
            if xs[i] - xs[i - 1] >= 18:
                bounds.append(round((xs[i] + xs[i - 1]) / 2))
        bounds.append(10 ** 9)
        for k in range(len(bounds) - 1):
            c = [w for w in ws if bounds[k] <= w['x0'] < bounds[k + 1]]
            buf = collections.OrderedDict()
            for w in sorted(c, key=lambda w: (round(w['top'] / 2.5), w['x0'])):
                key = round(w['top'] / 2.5)
                nk = None
                for kk in list(buf):
                    if abs(kk - key) <= 1:
                        nk = kk
                        break
                if nk is None:
                    buf[key] = [w]
                else:
                    buf[nk].append(w)
            print('==== PAGE %d COL %d x[%d,%d]' % (pi, k, bounds[k], bounds[k + 1] if bounds[k + 1] < 10 ** 9 else 999))
            for key in sorted(buf):
                l = ' '.join(w['text'] for w in sorted(buf[key], key=lambda w: w['x0'])).strip()
                print('   %-6d %s' % (key, l[:115]))