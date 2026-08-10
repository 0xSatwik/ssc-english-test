import sys, re
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
lines = [l.rstrip('\n') for l in open('build_fitb.txt', encoding='utf-8')]

def dump(start, end, label):
    print('==== %s (lines %d..%d) ====' % (label, start, end))
    for i in range(start, min(end, len(lines))):
        print('%5d: %r' % (i, lines[i][:120]))

qnums = {}
for i, l in enumerate(lines):
    m = re.match(r'^Q\.(\d+)\.', l)
    if m:
        qnums[int(m.group(1))] = i

# region around Q.98 (between Q.97 and Q.99)
dump(qnums[91] - 1, qnums[99] + 3, 'between Q.91 and Q.99')
# region between Q.118 and Q.120
dump(qnums[118] - 1, qnums[120] + 2, 'between Q.118 and Q.120')
# region between Q.128 and Q.136
dump(qnums[128] - 1, qnums[136] + 2, 'between Q.128 and Q.136')