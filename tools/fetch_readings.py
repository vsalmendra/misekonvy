#!/usr/bin/env python3
"""Fetch the day's readings from igenaptár into src/readings/<date>.json.

    python3 tools/fetch_readings.py 2026-10-27 2026-12-31     # a range (inclusive)
    python3 tools/fetch_readings.py 2026-11-08                # one day

They are shown when a day has no Mass file yet (the app then shows the Order of Mass with these
readings). Days with a Mass file use the readings written in that file, not these.
Existing files are overwritten; check the output (`git diff src/readings`) before committing.
Uses the same field names as a Mass file: reading1, psalm, reading2, alleluia (or verse before the
gospel in Lent), gospel; plus "day" (igenaptár's name of the day).
"""
import html, json, re, sys, urllib.request
from datetime import date as Date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'src' / 'readings'
URL = 'https://igenaptar.katolikus.hu/nap/index.php?holnap={}'


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
    day = re.search(r'</p>\s*<b>(.*?)</b>', page, re.S)
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


def main(argv):
    if not argv:
        sys.exit(__doc__)
    a = Date.fromisoformat(argv[0])
    b = Date.fromisoformat(argv[1]) if len(argv) > 1 else a
    OUT.mkdir(parents=True, exist_ok=True)
    bad = []
    d = a
    while d <= b:
        try:
            with urllib.request.urlopen(URL.format(d.isoformat()), timeout=30) as r:
                page = r.read().decode('utf-8', 'replace')
            data = parse(page)
            (OUT / f'{d.isoformat()}.json').write_text(json.dumps(data, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
            print(f'{d}  {data["day"]}  {data["reading1"]["cite"]} | {data.get("reading2", {}).get("cite", "-")} | {data["gospel"]["cite"]}')
        except Exception as e:  # report and go on; a day without readings shows the placeholders
            bad.append(f'{d}: {e}')
        d += timedelta(days=1)
    if bad:
        print('\nNot fetched:\n  ' + '\n  '.join(bad))


if __name__ == '__main__':
    main(sys.argv[1:])
