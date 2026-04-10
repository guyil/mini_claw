import re, json
from html.parser import HTMLParser

URL_RE = re.compile(r'https?://[^\s\]|)]+')

class SimpleTextHTMLParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.texts = []
    def handle_data(self, data):
        s = data.strip()
        if s:
            self.texts.append(s)

def extract_mapping_from_text(text):
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    pairs = []
    for i, line in enumerate(lines):
        urls = URL_RE.findall(line)
        if urls:
            url = urls[0]
            cat = line.replace(url, '').strip(' -|:\t')
            if not cat and i > 0:
                cat = lines[i-1]
            pairs.append({"category": cat, "bsr_url": url})
    dedup = []
    seen = set()
    for p in pairs:
        key = (p['category'], p['bsr_url'])
        if key not in seen:
            seen.add(key)
            dedup.append(p)
    return dedup

if __name__ == '__main__':
    import sys
    raw = sys.stdin.read()
    if '<html' in raw.lower():
        parser = SimpleTextHTMLParser()
        parser.feed(raw)
        raw = '\n'.join(parser.texts)
    print(json.dumps(extract_mapping_from_text(raw), ensure_ascii=False, indent=2))
