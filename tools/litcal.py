"""Roman liturgical calendar (Hungary): which day of the liturgical year a civil date is.

key(d)   -> a name for the day's readings that repeats in every year with the same cycle, e.g.
            "evkozi-30-2-II" (30th week of Ordinary Time, Tuesday, weekday year II),
            "evkozi-31-vas-A" (31st Sunday, year A), "advent-1-3", "dec-17", "fix-11-01" ...
label(d) -> Hungarian name of the day, e.g. "30. évközi hét kedd", "Évközi 31. vasárnap".

Moveable solemnities have their own keys (szentharomsag-A, punkosd-A ...); fixed-date feasts
are stored by the fetcher under "fix-MM-DD" (see tools/fetch_readings.py). Hungarian practice:
Epiphany on 6 January; Ascension and Corpus Christi (Úrnapja) on the following Sunday
(Easter + 42, Easter + 63). Day names follow igenaptár's wording.
"""
from datetime import date, timedelta

DAYS = ['hétfő', 'kedd', 'szerda', 'csütörtök', 'péntek', 'szombat', 'vasárnap']


def easter(y):
    a, b, c = y % 19, y // 100, y % 100
    d, e = b // 4, b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = c // 4, c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month = (h + l - 7 * m + 114) // 31
    return date(y, month, (h + l - 7 * m + 114) % 31 + 1)


def advent1(y):
    xmas = date(y, 12, 25)
    last_sunday = xmas - timedelta(days=(xmas.weekday() + 1) % 7 or 7)   # Sunday before Christmas
    return last_sunday - timedelta(weeks=3)


def baptism(y):
    """Baptism of the Lord: the Sunday after 6 January."""
    jan6 = date(y, 1, 6)
    return jan6 + timedelta(days=6 - jan6.weekday() or 7)


def sunday_cycle(d):
    start = d.year if d >= advent1(d.year) else d.year - 1
    return 'ABC'[start % 3]


def _day(d):
    """(key, label) of the date."""
    y, wd = d.year, d.weekday()            # wd: 0 = Monday ... 6 = Sunday
    sun = wd == 6
    c = sunday_cycle(d)
    w1 = 'I' if y % 2 else 'II'
    E = easter(y)
    a1 = advent1(y)

    # Advent
    if a1 <= d < date(y, 12, 25):
        w = (d - a1).days // 7 + 1
        if sun:
            return f'advent-{w}-vas-{c}', f'Advent {w}. vasárnapja'
        if d.day >= 17 and d.month == 12:
            return f'dec-{d.day}', f'Adventi köznapok – december {d.day}.'
        return f'advent-{w}-{wd + 1}', f'{w}. adventi hét {DAYS[wd]}'

    # Christmas season: 25 December - Baptism of the Lord
    bap = baptism(y)
    if d >= date(y, 12, 25) or d <= bap:
        if d == bap:
            return f'urunk-megkeresztelkedese-{c}', 'Urunk megkeresztelkedése'
        if d.month == 12 and (sun and d.day > 25 or d.day == 30 and date(y, 12, 25).weekday() == 6):
            return f'szent-csalad-{c}', 'A Szent Család: Jézus, Mária és József'
        if sun and d.month == 1 and 2 <= d.day <= 5:
            return 'karacsony-2-vas', 'Karácsony 2. vasárnapja'
        return f'fix-{d.month:02d}-{d.day:02d}', f'Karácsonyi idő – {d.month}. hó {d.day}.'

    ash = E - timedelta(days=46)
    pent = E + timedelta(days=49)
    # Ordinary Time before Lent
    if d < ash:
        w = (d - bap).days // 7 + 1
        if sun:
            return f'evkozi-{w}-vas-{c}', f'Évközi {w}. vasárnap'
        return f'evkozi-{w}-{wd + 1}-{w1}', f'{w}. évközi hét {DAYS[wd]}'
    # Lent and Holy Week
    if d < E:
        if d < ash + timedelta(days=4):
            return f'hamvazo-{wd + 1}', 'Hamvazószerda' if wd == 2 else f'{DAYS[wd].capitalize()} hamvazószerda után'
        if d >= E - timedelta(days=7):
            if sun:
                return f'viragvasarnap-{c}', 'Virágvasárnap'
            return f'nagyhet-{wd + 1}', 'Nagy' + DAYS[wd]
        w = (d - (ash + timedelta(days=4))).days // 7 + 1
        if sun:
            return f'nagybojt-{w}-vas-{c}', f'Nagyböjt {w}. vasárnapja'
        return f'nagybojt-{w}-{wd + 1}', f'{w}. nagyböjti hét {DAYS[wd]}'
    # Easter season
    if d <= pent:
        if d == pent:
            return f'punkosd-{c}', 'Pünkösdvasárnap'
        if d == E + timedelta(days=42):
            return f'mennybemenetel-{c}', 'Urunk mennybemenetele'
        w = (d - E).days // 7 + 1
        if sun:
            return (f'husvet-1-vas', 'Húsvétvasárnap') if w == 1 else (f'husvet-{w}-vas-{c}', f'Húsvét {w}. vasárnapja')
        if w == 1:
            return f'husvet-1-{wd + 1}', 'Húsvéthétfő' if wd == 0 else f'{DAYS[wd].capitalize()} húsvét nyolcadában'
        return f'husvet-{w}-{wd + 1}', f'Húsvét {w}. hét {DAYS[wd]}'
    # Ordinary Time after Pentecost
    if d == pent + timedelta(days=7):
        return f'szentharomsag-{c}', 'Szentháromság vasárnapja'
    if d == pent + timedelta(days=14):
        return f'urnapja-{c}', 'Krisztus Szent Teste és Vére, Úrnapja'
    if d == pent + timedelta(days=19):
        return f'jezus-szive-{c}', 'Jézus Szentséges Szíve'
    w = 34 - ((a1 - d).days - 1) // 7
    if sun:
        return (f'krisztus-kiraly-{c}', 'Krisztus a Világmindenség Királya') if w == 34 else (f'evkozi-{w}-vas-{c}', f'Évközi {w}. vasárnap')
    return f'evkozi-{w}-{wd + 1}-{w1}', f'{w}. évközi hét {DAYS[wd]}'


def key(d):
    return _day(d)[0]


def label(d):
    return _day(d)[1]


def is_special(k):
    """Keys of moveable celebrations (not a plain weekday/Sunday of a season)."""
    return k.split('-')[0] in {'urunk', 'szent', 'karacsony', 'punkosd', 'mennybemenetel', 'szentharomsag', 'urnapja',
                               'jezus', 'krisztus', 'viragvasarnap', 'hamvazo', 'nagyhet'} or k == 'husvet-1-vas'
