from pathlib import Path
import re
p = Path('desktop/src/renderer/index.html')
text = p.read_text(encoding='utf-8')
pattern = re.compile(r"[ØÙÂ][^<>\"'`\r\n]*")
changed = 0

def repl(match):
    global changed
    s = match.group(0)
    try:
        fixed = s.encode('latin1').decode('utf-8')
    except Exception:
        return s
    if fixed != s:
        changed += 1
        return fixed
    return s

new_text = pattern.sub(repl, text)
p.write_text(new_text, encoding='utf-8')
print('changed_segments', changed)
print('remaining_bad_markers', sum(new_text.count(ch) for ch in ('Ø','Ù','Â')))
