"""Embed out/data.json into web/template.html -> index.html"""
import sys
tpl, data, out = sys.argv[1:4]
t = open(tpl, encoding='utf-8').read(); d = open(data, encoding='utf-8').read()
assert '</script' not in d.lower()
open(out, 'w', encoding='utf-8').write(t.replace('/*DATA*/', d))
