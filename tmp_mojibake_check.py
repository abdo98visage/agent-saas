from pathlib import Path
import re
text = Path('desktop/src/renderer/index.html').read_text(encoding='utf-8')
patterns = sorted(set(re.findall(r'[ØÙÂ][^<>\r\n"\']*', text)))
shown = 0
for s in patterns:
    try:
        fixed = s.encode('latin1').decode('utf-8')
    except Exception:
        continue
    if fixed != s:
        print('BAD:', s)
        print('FIX:', fixed)
        print('---')
        shown += 1
        if shown >= 60:
            break
