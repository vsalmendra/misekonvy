#!/usr/bin/env python3
"""Build the app's Mass database from src/ into app/data/.

    python3 tools/build.py

Reads   src/masses/<date>.toml   (one file per Mass, see docs/ASSEMBLY.md)
        src/library/*.toml        (Order of Mass in Hungarian and Latin, Eucharistic prayers, prefaces)
        src/library/commons/*.toml (common Masses, referenced as "@<file>/<formula>[:<key>]")
Writes  app/data/calendar.json    (date -> title list, used by the date picker)
        app/data/masses/<date>.json (header fields + the rendered HTML of the Mass)
and stamps the build (hash of app/) into app/sw.js, app/index.html and app/version.json.
"""
import hashlib, html, json, re, sys, tomllib
from datetime import date as Date, timedelta
from itertools import zip_longest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'tools'))
import litcal  # noqa: E402
SRC, APP = ROOT / 'src', ROOT / 'app'
MONTHS = 'január február március április május június július augusztus szeptember október november december'.split()
DAYS = 'hétfő kedd szerda csütörtök péntek szombat vasárnap'.split()


def load(p):
    with open(p, 'rb') as f:
        return tomllib.load(f)


ORDO = load(SRC / 'library/ordo.toml')
ORDO_LA = load(SRC / 'library/ordo-latin.toml')
EPS = load(SRC / 'library/eucharistic-prayers.toml')
PREFACES = load(SRC / 'library/prefaces.toml')
COMMONS = {p.stem: load(p) for p in (SRC / 'library/commons').glob('*.toml')}
ALWAYS_PREFACES = ['ep2', 'ep4']
NO_LATIN = 'Latinul még nincs feltöltve.'      # the Latin text exists, but is not in the database yet
LA_NONE = 'Nincs latin megfelelője.'           # no Latin text at all (prayer of the faithful, Hungarian-only proper)
NO_HU = '(A magyar szöveg itt még nem érhető el – a lekcionáriumból.)'


class BuildError(Exception):
    pass


def esc(s):
    return html.escape(s.strip(), quote=False)


def lines(s):
    """Prayer / antiphon: one line per verse line."""
    return '<br>'.join(esc(l) for l in s.strip().split('\n'))


def split_paras(s):
    return [x for x in re.split(r'\n\s*\n', (s or '').strip()) if x.strip()]


def paras(s, cls=''):
    """Reading / preface: paragraphs separated by blank lines; single newlines become <br>."""
    c = f' class="{cls}"' if cls else ''
    return '\n'.join(f'<p{c}>{lines(x)}</p>' for x in split_paras(s))


def p(text, cls=''):
    c = f' class="{cls}"' if cls else ''
    return f'<p{c}>{text}</p>'


def resp(text):
    return p(esc(text), 'resp')


def cite(c):
    return p(esc(c), 'cite') if c else ''


# ---------- Latin–Hungarian grid ----------

BLANK = '<p class="bi-l la-blank"></p>'


def bi(la, hu, cls=''):
    """One row: Latin (left) and Hungarian (right); both already HTML. Missing Latin leaves the left cell blank."""
    la_html = f'<p class="bi-l {cls}" lang="la">{la}</p>' if la else BLANK
    return la_html + f'<p class="bi-r {cls}">{hu}</p>'


def noted(block, note):
    """A block (one prayer, reading …) whose Latin is missing: the first blank Latin cell gets a short,
    discreet note (NO_LATIN or LA_NONE), the rest stay blank. The Hungarian text is always there."""
    return block.replace(BLANK, f'<p class="bi-l la-blank la-note">{esc(note)}</p>', 1)


def toc_sub(c):
    """Detail shown next to a heading in the jump list (e.g. the citation of a reading)."""
    return f' data-toc-sub="{html.escape(c)}"' if c else ''


def bi_h3(la, hu, sub=''):
    return f'<h3 class="bi-l">{la}</h3><h3 class="bi-r"{toc_sub(sub)}>{hu}</h3>'


def bi_h2(text):
    return f'<h2 class="part bi-full">{text}</h2>'


def bi_cite(c):
    return f'<p class="cite bi-full">{esc(c)}</p>' if c else ''


def bi_paras(la, hu, cls=''):
    return ''.join(bi(lines(a) if a else '', lines(h) if h else '', cls)
                   for a, h in zip_longest(split_paras(la), split_paras(hu)))


# ---------- options (alternatives inside one slot: buttons, first selected) ----------

def resolve(opt, slot, names):
    """An option is plain text, a table {text, la, cite, label, source, latin_note},
    "@common/N[:key]", or a table with ref = "@common/N[:key]" plus its own label/notes."""
    extra = {}
    if isinstance(opt, dict) and 'ref' in opt:
        extra = {k: v for k, v in opt.items() if k != 'ref'}
        opt = opt['ref']
    if isinstance(opt, str) and opt.startswith('@'):
        m = re.fullmatch(r'@([\w-]+)/([\w-]+)(?::(\w+))?', opt)
        if not m:
            raise BuildError(f'bad reference {opt!r}')
        common, formula, key = m.group(1), m.group(2), m.group(3) or slot
        try:
            f = COMMONS[common][formula]
            opt = {'text': f[key], 'cite': f.get(key + '_cite', ''), 'la': f.get(key + '_la', '')}
        except KeyError:
            raise BuildError(f'{opt!r}: no {key} in {common}/{formula}')
    elif isinstance(opt, str):
        opt = {'text': opt}
    opt = {**opt, **extra}
    opt['text'] = subst(opt['text'], names[0], slot, 'names')
    if opt.get('la'):
        opt['la'] = subst(opt['la'], names[1], slot, 'la_names')
    return opt


def subst(text, pairs, where, key):
    """Put the saint's name in place of "N." (mass file: names = Hungarian, la_names = Latin pairs)."""
    for a, b in pairs:
        text = text.replace(a, b)
    if re.search(r'\bN\.', text):
        raise BuildError(f'{where}: unreplaced "N." in {text[:70]!r} - add it to {key}')
    return text


def opts_of(value, slot, names):
    return [resolve(o, slot, names) for o in (value if isinstance(value, list) else [value])]


def options(opts, render, group=None):
    """Render one slot (Hungarian). Several alternatives get a row of buttons; the first is selected.
    `group` names the alternatives so that the Latin section (variants of the same group) follows them."""
    if len(opts) == 1:
        return render(opts[0])
    btns = ''.join(f'<button type="button" class="alt-btn" aria-pressed="{"true" if i == 0 else "false"}" data-i="{i}">'
                   f'{esc(o.get("label", str(i + 1)))}</button>' for i, o in enumerate(opts))
    panels = '\n'.join(f'<div class="alt" data-i="{i}"{"" if i == 0 else " hidden"}>\n{render(o)}\n</div>'
                       for i, o in enumerate(opts))
    group = f' data-group="{group}"' if group else ''
    return f'<div class="alts"{group}><div class="alt-btns" role="group" aria-label="Választható szövegek">{btns}</div>\n{panels}\n</div>'


def la_missing(o):
    """Note for an option without Latin: its own `latin_note`, LA_NONE for a Hungarian-only text
    (`hu_only = true`), else NO_LATIN (exists, not uploaded yet)."""
    return o.get('latin_note') or (LA_NONE if o.get('hu_only') else NO_LATIN)


def bi_options(group, opts, render):
    """Latin section of a slot: one block per alternative, following the buttons of the Hungarian part."""
    if len(opts) == 1:
        return render(opts[0])
    return variants(group, [(str(i), render(o)) for i, o in enumerate(opts)], '0')


def antiphon(o):
    if o.get('placeholder'):
        return p(PROPER, 'rub')
    return p(lines(o['text']), 'verse') + cite(o.get('cite', ''))


def prayer(intro):
    def r(o):
        if o.get('placeholder'):
            return (p('Könyörögjünk!') if intro else '') + p(PROPER, 'rub') + resp('Ámen.')
        return (p('Könyörögjünk!') if intro else '') + p(lines(o['text']), 'verse') + resp('Ámen.')
    return r


def bi_antiphon(la_title, hu_title, opts, group):
    def r(o):
        if o.get('placeholder'):
            return bi(PROPER_LA, PROPER, 'rub')
        return noted(bi(lines(o.get('la', '')), lines(o['text']), 'verse'), la_missing(o)) + \
            bi_cite(o.get('la_cite') or o.get('cite', ''))
    return bi_h3(la_title, hu_title) + bi_options(group, opts, r)


def bi_prayer(la_title, hu_title, opts, intro, group):
    def r(o):
        if o.get('placeholder'):
            body = bi(PROPER_LA, PROPER, 'rub')
        else:
            body = noted(bi(lines(o.get('la', '')), lines(o['text']), 'verse'), la_missing(o))
        return (bi('Orémus.', 'Könyörögjünk!') if intro else '') + body + bi('Amen.', 'Ámen.', 'resp')
    return bi_h3(la_title, hu_title) + bi_options(group, opts, r)


# ---------- readings ----------

def reading(r):
    out = [f'<h3{toc_sub(r["cite"])}>{esc(r.get("label", "Olvasmány"))}</h3>', p(esc(r['sub']), 'sub')]
    if r.get('summary'):
        out.append(p(esc(r['summary']), 'rub'))
    out += [paras(r['text']) if r.get('text') else p(NO_HU, 'rub'),
            p('Ez az Isten igéje.'), resp('Istennek legyen hála.'), cite(r['cite'])]
    return '\n'.join(out)


def bi_reading(r):
    return (bi_h3('Lectio', esc(r.get('label', 'Olvasmány')), r['cite']) +
            noted(bi(esc(r.get('la_sub', '')), esc(r['sub']), 'rub') + bi_paras(r.get('la'), r.get('text', '')), NO_LATIN) +
            bi('Verbum Dómini.', 'Ez az Isten igéje.') + bi('Deo grátias.', 'Istennek legyen hála.', 'resp') + bi_cite(r['cite']))


def psalm(s):
    if not s.get('response'):
        return '\n'.join([f'<h3{toc_sub(s["cite"])}>Válaszos zsoltár</h3>', cite(s['cite']), p(NO_HU, 'rub')])
    out = [f'<h3{toc_sub(s["cite"])}>Válaszos zsoltár</h3>', cite(s['cite']), resp(s['response'])]
    for v in s['verses']:
        out += [p(lines(v), 'verse'), resp(s['response'])]
    return '\n'.join(out)


def bi_psalm(s):
    la_r = esc(s.get('la_response', ''))
    hu_r = esc(s.get('response', ''))
    out = bi(la_r, hu_r, 'resp')
    for la, hu in zip_longest(s.get('la_verses', []), s.get('verses', [])):
        out += bi(lines(la) if la else '', lines(hu) if hu else '', 'verse') + bi(la_r, hu_r, 'resp')
    return bi_h3('Psalmus responsorius', 'Válaszos zsoltár', s['cite']) + bi_cite(s['cite']) + noted(out, NO_LATIN)


def alleluia(a):
    if a.get('lent'):   # Lent: verse before the gospel, no alleluia
        return '\n'.join(['<h3>Evangélium előtti vers</h3>', p(lines(a['text'])), cite(a['cite'])])
    text = p(lines(a['text'])) if a.get('text') else p(NO_HU, 'rub')
    return '\n'.join(['<h3>Alleluja</h3>', resp('Alleluja, alleluja!'), text, cite(a['cite']), resp('Alleluja!')])


def bi_alleluia(a):
    if a.get('lent'):
        return (bi_h3('Versus ante Evangelium', 'Evangélium előtti vers') +
                noted(bi(lines(a.get('la', '')), lines(a['text'])), NO_LATIN) + bi_cite(a['cite']))
    return (bi_h3('Alleluia', 'Alleluja') + bi('Allelúia, allelúia.', 'Alleluja, alleluja!', 'resp') +
            noted(bi(lines(a.get('la', '')), lines(a.get('text', ''))), NO_LATIN) + bi_cite(a['cite']) + bi('Allelúia.', 'Alleluja!', 'resp'))


def gospel(g):
    out = [f'<h3{toc_sub(g["cite"])}>Evangélium</h3>', p('Az Úr legyen veletek.'), resp('És a te lelkeddel.'),
           p(f'Evangélium {esc(g["book"])} könyvéből.'), resp('Dicsőség neked, Istenünk.')]
    if g.get('summary'):
        out.append(p(esc(g['summary']), 'rub'))
    out += [paras(g['text']) if g.get('text') else p(NO_HU, 'rub'),
            p('Ezek az evangélium igéi.'), resp('Áldunk téged, Krisztus.'), cite(g['cite'])]
    return '\n'.join(out)


def bi_gospel(g):
    book = f'Léctio sancti Evangélii secúndum {esc(g["la_book"])}.' if g.get('la_book') else ''
    return (bi_h3('Evangelium', 'Evangélium', g['cite']) + bi('Dóminus vobíscum.', 'Az Úr legyen veletek.') +
            bi('Et cum spíritu tuo.', 'És a te lelkeddel.', 'resp') +
            noted(bi(book, f'Evangélium {esc(g["book"])} könyvéből.') + bi('Glória tibi, Dómine.', 'Dicsőség neked, Istenünk.', 'resp') +
                  bi_paras(g.get('la'), g.get('text', '')), NO_LATIN) + bi('Verbum Dómini.', 'Ezek az evangélium igéi.') +
            bi('Laus tibi, Christe.', 'Áldunk téged, Krisztus.', 'resp') + bi_cite(g['cite']))


def word(r):
    """The readings of the Liturgy of the Word (one set)."""
    out = [reading(r['reading1']), psalm(r['psalm'])] + ([reading(r['reading2'])] if 'reading2' in r else [])
    return '\n'.join(out + [alleluia(r['alleluia']), gospel(r['gospel'])])


def bi_word(r):
    out = [bi_reading(r['reading1']), bi_psalm(r['psalm'])] + ([bi_reading(r['reading2'])] if 'reading2' in r else [])
    return ''.join(out + [bi_alleluia(r['alleluia']), bi_gospel(r['gospel'])])


def placeholder_readings():
    """Order of Mass alone: the fixed dialogues of the Liturgy of the Word, the readings left to the book."""
    return '\n'.join([
        '<h3>Olvasmány</h3>', p(READING, 'rub'), p('Ez az Isten igéje.'), resp('Istennek legyen hála.'),
        '<h3>Válaszos zsoltár</h3>', p(READING, 'rub'),
        '<h3>Alleluja</h3>', resp('Alleluja, alleluja!'), p(READING, 'rub'), resp('Alleluja!'),
        '<h3>Evangélium</h3>', p('Az Úr legyen veletek.'), resp('És a te lelkeddel.'),
        p('Evangélium Szent N. könyvéből.'), resp('Dicsőség neked, Istenünk.'), p(READING, 'rub'),
        p('Ezek az evangélium igéi.'), resp('Áldunk téged, Krisztus.')])


def bi_placeholder_readings():
    return (bi_h3('Lectio', 'Olvasmány') + bi(READING_LA, READING, 'rub') + bi('Verbum Dómini.', 'Ez az Isten igéje.') +
            bi('Deo grátias.', 'Istennek legyen hála.', 'resp') +
            bi_h3('Psalmus responsorius', 'Válaszos zsoltár') + bi(READING_LA, READING, 'rub') +
            bi_h3('Alleluia', 'Alleluja') + bi('Allelúia, allelúia.', 'Alleluja, alleluja!', 'resp') +
            bi(READING_LA, READING, 'rub') + bi('Allelúia.', 'Alleluja!', 'resp') +
            bi_h3('Evangelium', 'Evangélium') + bi('Dóminus vobíscum.', 'Az Úr legyen veletek.') +
            bi('Et cum spíritu tuo.', 'És a te lelkeddel.', 'resp') +
            bi('Léctio sancti Evangélii secúndum N.', 'Evangélium Szent N. könyvéből.') +
            bi('Glória tibi, Dómine.', 'Dicsőség neked, Istenünk.', 'resp') + bi(READING_LA, READING, 'rub') +
            bi('Verbum Dómini.', 'Ezek az evangélium igéi.') + bi('Laus tibi, Christe.', 'Áldunk téged, Krisztus.', 'resp'))


def faithful(f):
    out = ['<h3>Egyetemes könyörgések</h3>', p(esc(f['intro']))]
    for i, pet in enumerate(f['petitions'], 1):
        if isinstance(pet, dict):
            out.append(p(esc(pet['note']), 'rub'))
            pet = pet['text']
        out += [p(f'{i}. {esc(pet)}'), resp(f['response'])]
    out += [p(esc(f['conclusion'])), resp('Ámen.')]
    return '\n'.join(out)


def bi_faithful(f):
    """Prayer of the faithful: only in Hungarian; the Latin column stays blank with a short note."""
    out = bi('', esc(f['intro']))
    for i, pet in enumerate(f['petitions'], 1):
        if isinstance(pet, dict):
            out += bi('', esc(pet['note']), 'rub')
            pet = pet['text']
        out += bi('', f'{i}. {esc(pet)}') + bi('', esc(f['response']), 'resp')
    out += bi('', esc(f['conclusion'])) + bi('', 'Ámen.', 'resp')
    return bi_h3('Oratio universalis', 'Egyetemes könyörgések') + noted(out, LA_NONE)


# ---------- jump marks inside the Eucharistic prayer ----------
# Points of the prayer listed in the jump list (data-toc on the paragraph; data-toc-la in the Latin section).

def ep_marks(paras):
    """paras: [(class, text)] of a Eucharistic prayer -> {index: (Hungarian label, Latin label)}"""
    marks = {}
    cons = [i for i, (c, _) in enumerate(paras) if 'cons' in (c or '')]
    if cons:
        marks[cons[0] - 1] = ('Alapítási elbeszélés, átváltoztatás', 'Narratio institutionis et consecratio')
    for i, (c, t) in enumerate(paras):
        if t.lstrip().startswith('Íme, hitünk szent titka'):
            marks[i] = ('Hitünk titka', 'Mysterium fidei')
        elif t.lstrip().startswith('Őáltala'):
            marks[i] = ('Záródoxológia', 'Doxologia')
    return marks


def toc_attr(mark):
    return f' data-toc="{mark[0]}" data-toc-la="{mark[1]}"' if mark else ''


def mark_ep_html(h):
    """The Hungarian EP html with jump marks on its paragraphs."""
    paras = re.findall(r'<p(?: class="([^"]*)")?>(.*?)</p>', h, re.S)
    marks, it = ep_marks(paras), iter(range(len(paras)))
    return re.sub(r'<p(?= class="[^"]*">|>)', lambda m: '<p' + toc_attr(marks.get(next(it))), h)


def mark_first(h, hu, la):
    """Jump mark on the first paragraph of a fixed part that has no heading of its own."""
    return re.sub(r'<p(?=[ >])', f'<p data-toc="{hu}" data-toc-la="{la}"', h, count=1)


# ---------- preface / Eucharistic prayer choosers ----------

def chooser(group, label, items, default):
    sel = ''.join(f'<option value="{k}"{" selected" if k == default else ""}>{esc(lab)}</option>' for k, lab, _ in items)
    return (f'<div class="choice"><label for="sel-{group}">{label}</label><select id="sel-{group}" data-sel="{group}">{sel}</select></div>'
            + variants(group, [(k, body) for k, _, body in items], default))


def la_chooser(group, label, items, default):
    """The same choice inside the Latin section (kept in step with the Hungarian dropdown)."""
    sel = ''.join(f'<option value="{k}"{" selected" if k == default else ""}>{esc(lab)}</option>' for k, lab in items)
    return (f'<div class="choice bi-full"><label for="sel-{group}-la">{label}</label>'
            f'<select id="sel-{group}-la" data-sel="{group}">{sel}</select></div>')


def variants(group, items, default):
    """Blocks shown one at a time; the dropdown of the same group (Hungarian part) drives both languages."""
    var = '\n'.join(f'<div class="variant" data-opt="{k}"{"" if k == default else " hidden"}>\n{body}\n</div>' for k, body in items)
    return f'<div class="variants" data-group="{group}" data-default="{default}">\n{var}\n</div>'


def preface_body(k, names):
    pr = PREFACES[k]
    return (p(esc(pr['sub']), 'sub') + '\n' if pr.get('sub') else '') + paras(subst(pr['text'], names[0], k, 'names'))


def bi_preface(k, names):
    pr = PREFACES[k]
    la = subst(pr['la'], names[1], k, 'la_names') if pr.get('la') else ''
    return (bi_h3(esc(pr.get('la_label', '')), esc(pr['label'])) + ORDO_LA['preface_dialogue'] +
            noted(bi_paras(la, subst(pr['text'], names[0], k, 'names')), NO_LATIN))


def bi_ep(k):
    ep = EPS[k]
    hu = re.findall(r'<p(?: class="([^"]*)")?>(.*?)</p>', ep['html'], re.S)
    la = iter(ep.get('la', []))
    marks = ep_marks(hu)
    out = ''
    for i, (cls, body) in enumerate(hu):
        if cls == 'rub':
            out += f'<p class="bi-full rub">{body}</p>'
        else:
            row = bi(esc(next(la, '')), body, cls or '')
            out += row.replace('<p class="bi-r', '<p' + toc_attr(marks.get(i)) + ' class="bi-r', 1)
    return bi_h3(esc(ep.get('la_label', '')), esc(ep['label'])) + noted(out, NO_LATIN)


# ---------- one Mass ----------

def build_mass(path):
    m = load(path)
    d = Date.fromisoformat(m['date'])
    if path.stem != m['date']:
        raise BuildError(f'{path.name}: file name must be the date ({m["date"]})')
    html_out = render(m)
    return {
        'date': m['date'],
        'dateLabel': f'{d.year}. {MONTHS[d.month - 1]} {d.day}. · {DAYS[d.weekday()]}',
        'title': m['title'],
        'rank': m.get('rank', ''),
        'meta': [m.get('day', ''), m.get('mass_type', '')],
        'html': html_out,
    }, html_out.count(NO_LATIN)


# ---------- the Order of Mass alone (shown when a day has no Mass yet) ----------

ORDINARY = {'eucharistic_prayer': 2, 'prefaces': ['ep2']}
PROPER = '(A napi szöveg a misekönyvből.)'
PROPER_LA = '(Textus proprius diei e Missali.)'
READING = '(A napi olvasmány a lekcionáriumból.)'
READING_LA = '(Lectio diei e Lectionario.)'


def proper_slot(m, slot, names):
    """The day's options for a slot, or a placeholder when the Order of Mass is shown alone."""
    if slot in m:
        return opts_of(m[slot], slot, names)
    return [{'text': '', 'la': '', 'placeholder': True}]


def build_ordinary():
    return {'html': render(ORDINARY)}


def build_cycle(first=Date(2026, 10, 1), last=Date(2029, 12, 31)):
    """src/cycle/<key>.json (tools/fetch_readings.py) -> app/data/cycle/<key>.json, and
    app/data/days.json: for every date, the liturgical day's name and the key of its readings.
    The app puts them into the Order of Mass on days without a Mass file."""
    out = APP / 'data' / 'cycle'
    out.mkdir(parents=True, exist_ok=True)
    have, written = {}, set()
    for path in sorted((SRC / 'cycle').glob('*.json')):
        r = json.loads(path.read_text(encoding='utf-8'))
        hu = [reading(r['reading1']), psalm(r['psalm'])] + ([reading(r['reading2'])] if 'reading2' in r else [])
        hu += [alleluia(r['alleluia']), gospel(r['gospel'])]
        # No Latin lectionary text for these days yet: the Hungarian column only, the Latin one blank with a note.
        (out / f'{path.stem}.json').write_text(json.dumps({'html': '\n'.join(hu), 'la_html': bi_word(r)},
                                                          ensure_ascii=False), encoding='utf-8')
        have[path.stem] = r
        written.add(f'{path.stem}.json')
    for stale in out.glob('*.json'):
        if stale.name not in written:
            stale.unlink()
    days, found, d = {}, 0, first
    while d <= last:
        k, lab = litcal.key(d), litcal.label(d)
        fix = have.get(f'fix-{d.month:02d}-{d.day:02d}')
        if fix and not k.startswith('fix-') and (fix.get('rank') == 'FÜ' or (fix.get('rank') == 'Ü' and d.weekday() != 6)):
            k, lab = f'fix-{d.month:02d}-{d.day:02d}', re.sub(r'\s*[–-]\s*F?Ü\s*$', '', fix['day'])
        if k.startswith('fix-') and k in have and lab.startswith('Karácsonyi idő'):
            lab = re.sub(r'\s*[–-]\s*F?Ü\s*$', '', ' '.join(have[k]['day'].split()))
        days[d.isoformat()] = [lab, k if k in have else '']
        found += k in have
        d += timedelta(days=1)
    (APP / 'data' / 'days.json').write_text(json.dumps(days, ensure_ascii=False, separators=(',', ':')), encoding='utf-8')
    print(f'{len(written)} liturgical days of readings; {found} of {len(days)} dates covered ({first} - {last})')


def render(m):
    """HTML of a Mass. Without propers (ORDINARY) the day's texts are replaced by rubric placeholders."""
    names = (m.get('names', []), m.get('la_names', []))
    ep = str(m.get('eucharistic_prayer', 2))
    prefs = m.get('prefaces', [])
    if not prefs:
        raise BuildError('no prefaces')
    pref_keys = prefs + [k for k in ALWAYS_PREFACES if k not in prefs]
    for k in pref_keys:
        if k not in PREFACES:
            raise BuildError(f'unknown preface {k!r}')
    for flag in ('gloria', 'creed'):
        if m.get(flag) and flag not in ORDO:
            raise BuildError(f'{flag} = true, but src/library/ordo.toml has no {flag} yet')
    o = {s: proper_slot(m, s, names) for s in ('entrance', 'collect', 'offertory', 'communion', 'postcommunion')}

    h = []
    h.append('<section id="r1"><h2 class="part">Bevezető szertartás</h2>')
    h.append('<h3>Bevezető ének</h3>' + options(o['entrance'], antiphon, 'alt-entrance'))
    h += [ORDO['greeting'], ORDO['penitential'], ORDO['kyrie']]
    if m.get('gloria'):
        h.append(ORDO['gloria'])
    h.append('<h3>Könyörgés</h3>' + options(o['collect'], prayer(True), 'alt-collect'))
    h.append('</section>')

    h.append('<section id="r2"><h2 class="part">Az Ige liturgiája</h2>')
    sets = m.get('readings') or ([m] if 'reading1' in m else [])
    if sets:
        h.append(options(sets, word, 'lect'))
    else:
        h.append('<div class="day-readings">' + placeholder_readings() + '</div>')
    h.append('<h3>Homília</h3>')
    if m.get('creed'):
        h.append(ORDO['creed'])
    h.append(faithful(m['faithful']) if 'faithful' in m else
             '<h3>Egyetemes könyörgések</h3>' + p('(A napi egyetemes könyörgések.)', 'rub'))
    h.append('</section>')

    h.append('<section id="r3"><h2 class="part">Az Eucharisztia liturgiája</h2>')
    h.append(ORDO['gifts'])
    h.append('<h3>Felajánló könyörgés</h3>' + options(o['offertory'], prayer(False), 'alt-offertory'))
    h.append('<h3>Prefáció</h3>' + ORDO['preface_dialogue'])
    h.append(chooser('pref', 'Prefáció', [(k, PREFACES[k]['label'], preface_body(k, names)) for k in pref_keys], pref_keys[0]))
    h.append(ORDO['sanctus'])
    h.append('<h3>Eucharisztikus ima</h3>')
    h.append(chooser('ep', 'Eucharisztikus ima', [(k, v['label'], mark_ep_html(v['html'])) for k, v in EPS.items()], ep))
    h.append('</section>')

    h.append('<section id="r4"><h2 class="part">A szentáldozás szertartása</h2>')
    h.append(ORDO['communion_rite'])
    h.append('<h3>Áldozási ének</h3>' + options(o['communion'], antiphon, 'alt-communion'))
    h.append('<h3>Áldozás utáni könyörgés</h3>' + options(o['postcommunion'], prayer(True), 'alt-postcommunion'))
    h.append('</section>')
    h.append('<section id="r5"><h2 class="part">Befejező szertartás</h2>\n' +
             mark_first(ORDO['concluding'], 'Áldás és elbocsátás', 'Benedictio et dimissio') + '\n</section>')

    # Latin–Hungarian section (always)
    g = ['<p class="bi-l bi-lab">Latine</p><p class="bi-r bi-lab">Magyarul</p>',
         bi_h2('Ritus initiales · Bevezető szertartás'),
         bi_antiphon('Antiphona ad introitum', 'Bevezető ének', o['entrance'], 'alt-entrance'),
         mark_first(ORDO_LA['greeting'], 'Köszöntés', 'Salutatio'), ORDO_LA['penitential'], ORDO_LA['kyrie']]
    if m.get('gloria'):
        g.append(ORDO_LA['gloria'])
    g.append(bi_prayer('Collecta', 'Könyörgés', o['collect'], True, 'alt-collect'))
    g.append(bi_h2('Liturgia verbi · Az Ige liturgiája'))
    if len(sets) == 1:
        g.append(bi_word(sets[0]))
    elif sets:   # follows the readings buttons of the Hungarian part
        g.append(variants('lect', [(str(i), bi_word(r)) for i, r in enumerate(sets)], '0'))
    else:
        g.append('<div class="day-readings-la">' + bi_placeholder_readings() + '</div>')
    if m.get('creed'):
        g.append(ORDO_LA['creed'])
    g.append(bi_faithful(m['faithful']) if 'faithful' in m else
             bi_h3('Oratio universalis', 'Egyetemes könyörgések') + noted(bi('', '(A napi egyetemes könyörgések.)', 'rub'), LA_NONE))
    g.append(bi_h2('Liturgia eucharistica · Az Eucharisztia liturgiája'))
    g.append(ORDO_LA['gifts'])
    g.append(bi_prayer('Super oblata', 'Felajánló könyörgés', o['offertory'], False, 'alt-offertory'))
    g.append(la_chooser('pref', 'Praefatio · Prefáció', [(k, PREFACES[k].get('la_label') or PREFACES[k]['label']) for k in pref_keys], pref_keys[0]))
    g.append(variants('pref', [(k, bi_preface(k, names)) for k in pref_keys], pref_keys[0]))
    g.append(ORDO_LA['sanctus'])
    g.append(la_chooser('ep', 'Prex eucharistica · Eucharisztikus ima', [(k, v.get('la_label') or v['label']) for k, v in EPS.items()], ep))
    g.append(variants('ep', [(k, bi_ep(k)) for k in EPS], ep))
    g.append(bi_h2('Ritus communionis · A szentáldozás szertartása'))
    g.append(ORDO_LA['communion_rite'])
    g.append(bi_antiphon('Antiphona ad communionem', 'Áldozási ének', o['communion'], 'alt-communion'))
    g.append(bi_prayer('Post communionem', 'Áldozás utáni könyörgés', o['postcommunion'], True, 'alt-postcommunion'))
    g.append(bi_h2('Ritus conclusionis · Befejező szertartás'))
    g.append(mark_first(ORDO_LA['concluding'], 'Áldás és elbocsátás', 'Benedictio et dimissio'))
    back = '<p class="jump"><a class="btn" href="#top">↑ Vissza a magyar szöveghez</a></p>'
    h.append(f'<section id="latin" class="bilingual"><h2 class="part">Latin–magyar szöveg</h2>{back}'
             '<p class="bi-hint">Fektesd el a telefont, vagy húzd oldalra a szöveget: ⇆ latin | magyar</p>'
             f'<div class="bi-grid">{"".join(g)}</div>{back}</section>')
    return '\n'.join(h)


def main():
    out = APP / 'data' / 'masses'
    out.mkdir(parents=True, exist_ok=True)
    cal, errors, written = [], [], set()
    for path in sorted((SRC / 'masses').glob('*.toml')):
        try:
            mass, missing = build_mass(path)
        except (BuildError, KeyError) as e:
            errors.append(f'{path.name}: {e!r}')
            continue
        if missing:
            print(f'  {path.name}: {missing} Latin text(s) missing')
        (out / f'{mass["date"]}.json').write_text(json.dumps(mass, ensure_ascii=False), encoding='utf-8')
        written.add(f'{mass["date"]}.json')
        cal.append({'date': mass['date'], 'title': mass['title']})
    if errors:
        sys.exit('Build failed:\n  ' + '\n  '.join(errors))
    for stale in out.glob('*.json'):
        if stale.name not in written:
            stale.unlink()
    (APP / 'data' / 'ordinary.json').write_text(json.dumps(build_ordinary(), ensure_ascii=False), encoding='utf-8')
    build_cycle()
    (APP / 'data' / 'calendar.json').write_text(json.dumps({'masses': cal}, ensure_ascii=False, indent=1), encoding='utf-8')

    # Build stamp: a hash of every published file. It becomes the service-worker cache name (so installed
    # apps drop their old copy), the <meta name="build"> of index.html (the version the page runs) and
    # app/version.json (the version on the server). The page compares the two and reloads when they differ.
    stamp_re = re.compile(r'<meta name="build" content="[^"]*">')
    digest = hashlib.sha256()
    for f in sorted(APP.rglob('*')):
        if f.is_file() and f.name not in ('sw.js', 'version.json'):
            data = f.read_bytes()
            if f.name == 'index.html':
                data = stamp_re.sub('', data.decode('utf-8')).encode('utf-8')
            digest.update(f.relative_to(APP).as_posix().encode() + data)
    build = digest.hexdigest()[:10]
    index = APP / 'index.html'
    page = index.read_text(encoding='utf-8')
    if not stamp_re.search(page):
        sys.exit('Build failed: app/index.html has no <meta name="build" content="...">')
    index.write_text(stamp_re.sub(f'<meta name="build" content="{build}">', page), encoding='utf-8')
    (APP / 'version.json').write_text(json.dumps({'build': build}) + '\n', encoding='utf-8')
    sw = APP / 'sw.js'
    sw.write_text(re.sub(r"const CACHE = '[^']*';", f"const CACHE = 'szentmise-{build}';",
                         sw.read_text(encoding='utf-8')), encoding='utf-8')
    print(f'{len(cal)} masses: ' + ', '.join(c['date'] for c in cal))


if __name__ == '__main__':
    main()
