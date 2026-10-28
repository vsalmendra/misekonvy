#!/usr/bin/env python3
"""Fetch readings from igenaptár into src/cycle/<key>.json, stored by LITURGICAL day.

    python3 tools/fetch_readings.py 2025-11-30 2026-11-28     # a range (inclusive)
    python3 tools/fetch_readings.py 2026-11-08                # one day
    python3 tools/fetch_readings.py --keep 2023-12-03 2025-11-29   # earlier years, fill gaps only

The key comes from tools/litcal.py ("evkozi-30-2-II" = 30th week of Ordinary Time, Tuesday,
weekday year II; "evkozi-31-vas-A"; "advent-1-3"; ...), so the readings serve every later year
with the same cycle. Feasts and solemnities on fixed dates (igenaptár marks them "– Ü" / "– FÜ")
are stored as "fix-MM-DD" instead. igenaptár serves the current liturgical year at its root and the
earlier ones under /<year>/ (/2024/ = Advent 2023 - Nov 2024, /2025/ = Advent 2024 - Nov 2025).
They are shown when a day has no Mass file yet (the Order of Mass with the day's readings).
Existing files are overwritten; check `git diff src/cycle` before committing.
Fields as in a Mass file: reading1, psalm, reading2, alleluia (lent: true = verse before the
gospel), gospel; plus day (igenaptár's name), source_date, rank.
"""
import html, json, re, sys, urllib.request
from datetime import date as Date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'src' / 'cycle'
sys.path.insert(0, str(Path(__file__).resolve().parent))
import litcal  # noqa: E402
URL = 'https://igenaptar.katolikus.hu/nap/index.php?holnap={}'
# Earlier liturgical years stay online under /<year of their end>/, e.g. /2024/ = Advent 2023 - Nov 2024.
URL_YEAR = 'https://igenaptar.katolikus.hu/{}/nap/index.php?holnap={}'


def clean(s):
    """igenaptár HTML fragment -> plain text with \\n for line breaks; singing aids removed."""
    s = re.sub(r'(?i)<br\s*/?>', '\n', s)
    s = re.sub(r'<[^>]+>', '', s)
    s = html.unescape(s).replace('\r', '').replace('\t', ' ')
    s = re.sub(r'[  ]+', ' ', s)
    return '\n'.join(l.strip() for l in s.split('\n')).strip()


def bold(s):
    m = re.findall(r'<b>(.*?)</b>', s, re.S)
    return clean(m[-1]) if m else ''


def italic(s):
    """The summary line (first italic that is not an editorial note)."""
    for m in re.finditer(r'<i>(.*?)</i>', s, re.S):
        t = clean(m.group(1))
        if t and not NOTE.match(t) and 'forma' not in t:
            return t
    return ''


NOTE = re.compile(r'^(Vagy:?|Hosszabb forma:?|Rövidebb forma.*|Vagy rövidebb forma.*)$')


def strip_notes(text):
    """Drop the editorial lines igenaptár puts before a text ("Vagy:", "Hosszabb forma:")."""
    return '\n'.join(l for l in text.split('\n') if not NOTE.match(l.strip()))


def strip_tone(s):
    s = re.sub(r'\s*\(([^()]*?)\s*[–-]\s*[^()]*tónus\.?\)\s*$', r' \1', s)        # "(Zsolt 117,6a – 6. tónus.)"
    s = re.sub(r'\s*\((?:\d+[a-z]*\.?\s*vers\.?\s*-?\s*)?[^()]*tónus\.?\)\s*$', '', s)  # "(2. tónus.)"
    s = re.sub(r'\s*[–-]\s*[\w .]*tónus\.?\s*$', '', s)                               # "– 1 D2. tónus."
    s = re.sub(r'\s*\d+[a-z]*\.?\s*tónus\.?\s*$', '', s)                                # "6. tónus."
    return s.strip()


def reading(block):
    """OLVASMÁNY / SZENTLECKE block: label, sub, summary, text, cite. Long form kept; '*' removed."""
    body = re.sub(r'(?is)<i>\s*(Hosszabb forma:?|Vagy rövidebb forma.*?)\s*</i>', '', block)
    summary = italic(body)
    body = re.sub(r'(?is)<i>.*?</i>', '', body)
    cite = re.sub(r'\s*röv(?:idebb|\.)?:.*$', '', bold(body)).strip()
    text = strip_notes(clean(re.sub(r'<b>[^<]*</b>\s*$', '', body.strip())))
    lines = [l for l in text.split('\n') if l]
    head = lines.pop(0)
    m = re.match(r'(OLVASMÁNY|SZENTLECKE)\s+(.*)', head)
    if not m:
        raise ValueError(f'reading header? {head!r}')
    label = m.group(1).capitalize()
    sub = m.group(2).strip().rstrip('.')
    end = next((i for i, l in enumerate(lines) if l.startswith('Ez az Isten igéje')), len(lines))
    paras = [re.sub(r'\s*\*\s*$', '', l).replace(' * ', ' ').strip() for l in lines[:end]]
    return {'label': label, 'sub': sub, 'summary': summary, 'text': '\n\n'.join(p for p in paras if p), 'cite': cite}


def psalm(block):
    cite = bold(block)
    body = re.sub(r'<b>[^<]*</b>\s*$', '', block.strip())
    body = re.sub(r'</?u/?>', '', body)
    lines = [l for l in clean(body).split('\n') if l][1:]          # drop "VÁLASZOS ZSOLTÁR"
    resp, verses, cur = None, [], None
    for l in lines:
        if l.startswith('Válasz:'):
            r = l[len('Válasz:'):]
            r = re.sub(r'\s*(\(?Vö\.[^)]*\)?|\(\s*\d+[a-z]?\.?\s*tónus\.?\)|\d+[a-z]*\.?\s*vers\.?)\s*$', '', r)
            r = re.sub(r'\s*(Vö\.)?\s*\d+[a-z]*\.?\s*vers\.?\s*$', '', r)
            r = re.sub(r'\s*\([^()]*(?:tónus|vers)[^()]*\)\s*$', '', r)
            r = strip_tone(r).replace(' * ', ' ').replace('*', '').strip()
            # trailing reference of the response ("… trónomon. Jel 3,21", "… Jel4,8b.")
            ref = r'(?:Vö\.\s*)?\d?\s?[A-ZÁÉ][a-zé]{1,4}\.?\s?\d[\w,.;-]*'
            resp = re.sub(rf'([.!?])\s+{ref}(?:\s*(?:és|,)\s*{ref})*\.?$', r'\1', r).strip()
        elif re.match(r'(Hívek|H):', l):
            cur = None
        else:
            l = re.sub(r'^(Előénekes|E):\s*', '', l)
            parts = [x.strip() for x in l.split('*')]
            if cur is None or re.match(r'^(Előénekes|E):', l):
                cur = []
                verses.append(cur)
            cur.extend(parts)
    if not resp or not verses:
        raise ValueError('psalm not understood')
    return {'cite': cite, 'response': resp, 'verses': ['\n'.join(v) for v in verses]}


def verse_line(block, word):
    """ALLELUJA or EVANGÉLIUM ELŐTTI VERS: text + cite (the trailing scripture reference)."""
    t = clean(block)
    t = t.split('\n', 1)[1] if '\n' in t else ''
    t = strip_tone(' '.join(t.split()))
    t = re.sub(r'\s*[†*]\s*', ' ', t).strip()
    m = re.match(r'^(.*?[.!?”:])\s+((?:Vö\.\s*)?(?:\d\s?)?[A-ZÁÉÓÖŐÚÜŰ][a-zéáíóöőúüű]*\.?\s*\d[^ ]*(?:\s*(?:és|\.|,)\s*\d[^ ]*)*)\s*$', t)
    if not m:                                   # no scripture reference given (e.g. O-antiphons)
        return {'text': t, 'cite': ''}
    return {'text': m.group(1), 'cite': m.group(2).replace(' és ', '.').strip().rstrip('.')}


def gospel(block):
    summary = italic(block)
    body = re.sub(r'(?is)<i>.*?</i>', '', block)
    cite = re.sub(r'\s*röv(?:idebb|\.)?:.*$', '', bold(body)).strip()
    text = strip_notes(clean(re.sub(r'<b>[^<]*</b>\s*$', '', body.strip())))
    lines = [l for l in text.split('\n') if l]
    head = lines.pop(0)
    m = re.match(r'†?\s*EVANGÉLIUM\s+(.*?)\s+könyvéből', head, re.I)
    if not m:
        raise ValueError(f'gospel header? {head!r}')
    end = next((i for i, l in enumerate(lines) if l.startswith('Ezek az evangélium igéi')), len(lines))
    paras = [re.sub(r'\s*\*\s*$', '', l).replace(' * ', ' ').strip() for l in lines[:end]]
    return {'book': m.group(1), 'summary': summary, 'text': '\n\n'.join(p for p in paras if p), 'cite': cite}


def parse(page):
    day = (re.search(r'</p>\s*<b>(.*?)</b>', page, re.S) or               # current year's page
           re.search(r'<b>[\d-]+</b>(?:\s*<br>)*\s*<b>(.*?)</b>', page, re.S))   # archived years
    out = {'day': clean(day.group(1)) if day else ''}
    readings = []
    for block in re.findall(r'(?is)<p align="justify">(.*?)</p>', page):
        first = (strip_notes(clean(block)).strip().split('\n', 1) or [''])[0]
        if re.match(r'(OLVASMÁNY|SZENTLECKE)', first):
            readings.append(reading(block))
        elif first.startswith('VÁLASZOS ZSOLTÁR') and 'psalm' not in out:
            out['psalm'] = psalm(block)
        elif first.startswith('ALLELUJA') and 'alleluia' not in out:
            out['alleluia'] = verse_line(block, 'ALLELUJA')
        elif first.startswith('EVANGÉLIUM ELŐTTI VERS') and 'alleluia' not in out:
            out['alleluia'] = {**verse_line(block, 'EVANGÉLIUM ELŐTTI VERS'), 'lent': True}
        elif re.match(r'†?\s*EVANGÉLIUM', first) and 'gospel' not in out:
            out['gospel'] = gospel(block)
    if not readings or 'gospel' not in out:
        raise ValueError('no readings found')
    out['reading1'] = readings[0]
    if len(readings) > 1:
        out['reading2'] = readings[1]
    return out


def fetch(d):
    """The day's page: the current liturgical year at the root, earlier ones under /<year>/."""
    lit_year = d.year + 1 if d >= litcal.advent1(d.year) else d.year
    for url in (URL.format(d.isoformat()), URL_YEAR.format(lit_year, d.isoformat())):
        try:
            with urllib.request.urlopen(url, timeout=30) as r:
                page = r.read().decode('utf-8', 'replace')
        except OSError:          # the root answers 500 for dates outside the current year
            continue
        if 'SZENTLECKE' in page or 'OLVASMÁNY' in page:
            return page
    raise ValueError('no page for this date')


def main(argv):
    keep = '--keep' in argv            # do not overwrite readings already stored for a liturgical day
    argv = [a for a in argv if a != '--keep']
    if not argv:
        sys.exit(__doc__)
    a = Date.fromisoformat(argv[0])
    b = Date.fromisoformat(argv[1]) if len(argv) > 1 else a
    OUT.mkdir(parents=True, exist_ok=True)
    bad, mism = [], []
    d = a
    while d <= b:
        try:
            data = parse(fetch(d))
            rank = re.search(r'[–-]\s*(FÜ|Ü)\b', data['day'])
            key = litcal.key(d)
            if rank and not litcal.is_special(key):
                key = f'fix-{d.month:02d}-{d.day:02d}'
            if keep and (OUT / f'{key}.json').exists():
                d += timedelta(days=1)
                continue
            data = {'key': key, 'source_date': d.isoformat(), 'rank': rank.group(1) if rank else '', **data}
            (OUT / f'{key}.json').write_text(json.dumps(data, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
            print(f'{d}  {key:28} {data["day"][:45]:45} | {litcal.label(d)}')
            if not rank and norm(data['day']) != norm(litcal.label(d)) and not key.startswith(('fix-', 'dec-')):
                mism.append(f'{d}: igenaptár "{data["day"]}" / litcal "{litcal.label(d)}"')
        except Exception as e:  # report and go on; a day without readings shows the placeholders
            bad.append(f'{d}: {e}')
        d += timedelta(days=1)
    if mism:
        print('\nDay names differ (check the calendar):\n  ' + '\n  '.join(mism))
    if bad:
        print('\nNot fetched:\n  ' + '\n  '.join(bad))


def norm(s):
    return re.sub(r'[^a-záéíóöőúüű0-9]', '', s.lower())


if __name__ == '__main__':
    main(sys.argv[1:])
