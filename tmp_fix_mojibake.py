from pathlib import Path
import re

p = Path('desktop/src/renderer/index.html')
text = p.read_text(encoding='utf-8')
pattern = re.compile(r"[ØÙÂ][^<>\"'`\r\n]*")

def looks_fixed(s: str) -> bool:
    return any('\u0600' <= ch <= '\u06FF' for ch in s) or '…' in s or '•' in s

def repl(match):
    s = match.group(0)
    try:
        fixed = s.encode('latin1').decode('utf-8')
    except Exception:
        return s
    return fixed if fixed != s and looks_fixed(fixed) else s

new_text = pattern.sub(repl, text)
p.write_text(new_text, encoding='utf-8')
print('changed', text != new_text)
print('remaining_mojibake_chars', new_text.count('Ù') + new_text.count('Ø') + new_text.count('Â'))
