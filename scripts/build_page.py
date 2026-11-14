"""Embed out/data.json (plus out/controls.json, if present) into web/template.html -> index.html
usage: build_page.py TEMPLATE DATA_JSON OUT_HTML [CONTROLS_JSON]"""
import sys, json
tpl, data, out = sys.argv[1:4]
d = json.load(open(data, encoding='utf-8'))
if len(sys.argv) > 4: d['controls'] = json.load(open(sys.argv[4], encoding='utf-8'))
s = json.dumps(d, ensure_ascii=False)
assert '</script' not in s.lower()
open(out, 'w', encoding='utf-8').write(open(tpl, encoding='utf-8').read().replace('/*DATA*/', s))
