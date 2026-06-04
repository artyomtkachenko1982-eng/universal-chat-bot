"""Универсальный скрипт: fetcht текст страницы turbinist.ru по URL"""
import urllib.request, re, html, sys

url = sys.argv[1] if len(sys.argv) > 1 else 'https://www.turbinist.ru/'
data = urllib.request.urlopen(url, timeout=15).read().decode('utf-8', errors='replace')

# Ищем контент
text = data
for cls in ['turbo-static-text', 'full-article-content', 'story-full-text']:
    m = re.search(rf'<div[^>]*class="[^"]*{cls}[^"]*"[^>]*>', data, re.DOTALL)
    if m:
        start = m.end()
        end = data.find('</div>', start)
        end2 = data.find('</div>', end + 1) if end > 0 else -1
        text = data[start:end2] if end2 > start else data[start:start+20000]
        break

# Чистка
for tag in ['br', 'p', 'li', 'tr', 'th', 'td', 'div', 'h1', 'h2', 'h3', 'h4']:
    text = re.sub(rf'<{tag}\s*/?>', '\n', text)
    text = re.sub(rf'</{tag}>', '\n', text)
text = re.sub(r'<[^>]+>', '', text)
text = html.unescape(text)
text = re.sub(r'\n{3,}', '\n\n', text)
text = re.sub(r'[ \t]+', ' ', text)
text = re.sub(r'\n[ \t]+', '\n', text)

print(text.strip())
