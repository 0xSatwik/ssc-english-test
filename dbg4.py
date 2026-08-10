import sys, pdfplumber, re
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
with pdfplumber.open(r'pdfs\fill in the blanks.pdf') as pdf:
    for pi in range(len(pdf.pages)):
        ws = pdf.pages[pi].extract_words()
        marks = [w for w in ws if re.fullmatch(r'Q\.\d+\.', w['text'])]
        for w in marks:
            num = int(w['text'][2:-1])
            if 90 <= num <= 170:
                print('page %d  Q.%d  x0=%.1f top=%.1f' % (pi, num, w['x0'], w['top']))