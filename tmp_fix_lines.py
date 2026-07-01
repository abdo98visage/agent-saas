from pathlib import Path
p = Path('desktop/src/renderer/index.html')
text = p.read_text(encoding='utf-8')
lines = text.splitlines(keepends=True)
changed = 0
for i, line in enumerate(lines):
    if any(ch in line for ch in ('Ø', 'Ù', 'Â')):
        try:
            fixed = line.encode('latin1').decode('utf-8')
        except Exception:
            continue
        if fixed != line:
            lines[i] = fixed
            changed += 1
new_text = ''.join(lines)
p.write_text(new_text, encoding='utf-8')
print('changed_lines', changed)
print('remaining_bad_markers', sum(new_text.count(ch) for ch in ('Ø','Ù','Â')))
