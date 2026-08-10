import sys, pdfplumber
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
with pdfplumber.open(r'pdfs\fill in the blanks.pdf') as pdf:
    for pi in range(0, 14):
        t = pdf.pages[pi].extract_text() or ''
        for ln in t.splitlines():
            if 'Solutions' in ln or 'OLUTIONS' in ln:
                print('page', pi, '|', ln.strip()[:80])
    # Also: how many 'Solutions :-' total
    total = 0
    for pi in range(len(pdf.pages)):
        t = pdf.pages[pi].extract_text() or ''
        total += t.count('Solutions :-')
    print('total "Solutions :-" occurrences:', total)