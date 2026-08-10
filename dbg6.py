import sys, pdfplumber, re
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
with pdfplumber.open(r'pdfs\fill in the blanks.pdf') as pdf:
    # find page containing Q.265
    for pi in range(len(pdf.pages)):
        words = pdf.pages[pi].extract_words()
        for w in words:
            if w['text'] == 'Q.265.':
                print('Q.265 on page', pi)
                t = pdf.pages[pi].extract_text() or ''
                for ln in t.splitlines():
                    if re.search(r'SSC|date|exam|Exam', ln, re.I):
                        print('  |', ln.strip()[:100])
                break
    # scan ALL pages for date/exam tokens counts
    tok = {}
    for pi in range(len(pdf.pages)):
        t = pdf.pages[pi].extract_text() or ''
        for m in re.finditer(r'SSC [A-Za-z]+ \d{1,2}/\d{1,2}/\d{4}', t):
            pass
    print('pages:', len(pdf.pages))