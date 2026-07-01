from pathlib import Path
text = Path('desktop/src/renderer/index.html').read_text(encoding='utf-8')
needles = [
    'Ù…ÙˆØ¸Ù ØºÙŠØ± Ù…Ø¹Ø±ÙˆÙ',
    'ØªÙ… Ø­ÙØ¸ Ø§Ù„Ø±Ø³Ø§Ù„Ø© Ù…Ø­Ù„ÙŠØ§Ù‹ ÙˆØ³ÙŠØªÙ… Ø¥Ø±Ø³Ø§Ù„Ù‡Ø§ Ø¹Ù†Ø¯ Ø¹ÙˆØ¯Ø© Ø§Ù„Ø§ØªØµØ§Ù„.'
]
for needle in needles:
    print(f'{needle} => {text.count(needle)}')
