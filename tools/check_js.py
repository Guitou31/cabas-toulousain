"""Controle grossier de syntaxe du <script> embarque : equilibre des {} [] ()
en tenant compte des chaines, commentaires et regex litterales."""
import re, sys

path = sys.argv[1]
html = open(path, encoding='utf-8').read()
m = re.search(r'<script>\n(.*)\n</script>', html, re.S)
if not m:
    print('SCRIPT INTROUVABLE'); sys.exit(1)
js = m.group(1)

REGEX_PRECEDERS = set('(,=:[!&|?{;%*/+-<>^~')
stack = []
i, n = 0, len(js)
line = 1
last_sig = ';'  # dernier caractere significatif
PAIRS = {')': '(', ']': '[', '}': '{'}
errors = []

while i < n:
    c = js[i]
    if c == '\n':
        line += 1; i += 1; continue
    if c in ' \t\r':
        i += 1; continue
    # commentaires
    if c == '/' and i+1 < n and js[i+1] == '/':
        while i < n and js[i] != '\n': i += 1
        continue
    if c == '/' and i+1 < n and js[i+1] == '*':
        i += 2
        while i+1 < n and not (js[i] == '*' and js[i+1] == '/'):
            if js[i] == '\n': line += 1
            i += 1
        i += 2; continue
    # chaines
    if c in ('"', "'"):
        q = c; i += 1
        while i < n:
            if js[i] == '\\': i += 2; continue
            if js[i] == q: break
            if js[i] == '\n': errors.append('ligne %d : chaine non fermee' % line); break
            i += 1
        i += 1; last_sig = '"'; continue
    # regex litterale ?
    if c == '/':
        if last_sig in REGEX_PRECEDERS or last_sig == ';' or last_sig == '\0' or (last_sig.isalpha() and False):
            i += 1; in_class = False
            while i < n:
                if js[i] == '\\': i += 2; continue
                if js[i] == '[': in_class = True
                elif js[i] == ']': in_class = False
                elif js[i] == '/' and not in_class: break
                elif js[i] == '\n': errors.append('ligne %d : regex non fermee' % line); break
                i += 1
            i += 1
            while i < n and js[i].isalpha(): i += 1  # flags
            last_sig = '"'; continue
        else:
            last_sig = '/'; i += 1; continue
    if c in '([{':
        stack.append((c, line))
    elif c in ')]}':
        if not stack:
            errors.append('ligne %d : %s fermante sans ouvrante' % (line, c))
        else:
            o, ol = stack.pop()
            if o != PAIRS[c]:
                errors.append('ligne %d : %s ferme %s ouvert ligne %d' % (line, c, o, ol))
    # mots-cles return/typeof avant regex : traiter fin de mot
    if c.isalnum() or c in '_$':
        j = i
        while j < n and (js[j].isalnum() or js[j] in '_$'): j += 1
        word = js[i:j]
        last_sig = ';' if word in ('return','typeof','in','of','new','delete','void','case','do','else') else 'a'
        i = j; continue
    last_sig = c
    i += 1

for o, ol in stack:
    errors.append('%s ouvert ligne %d jamais ferme' % (o, ol))

if errors:
    print('ERREURS :')
    for e in errors[:20]: print(' -', e)
    sys.exit(1)
print('OK : delimiteurs equilibres (%d lignes de script)' % js.count('\n'))
