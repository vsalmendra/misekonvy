#!/usr/bin/env python3
"""Build the app's Mass database from src/ into app/data/.

    python3 tools/build.py

Reads   src/masses/<date>.toml   (one file per Mass, see docs/ASSEMBLY.md)
        src/library/*.toml        (Order of Mass, Eucharistic prayers, prefaces)
        src/library/commons/*.toml (common Masses, referenced as "@<file>/<formula>[:<key>]")
Writes  app/data/calendar.json    (date -> title list, used by the date picker)
        app/data/masses/<date>.json (header fields + the rendered HTML of the Mass)
and stamps a new cache name into app/sw.js.
"""
import hashlib, html, json, re, sys, tomllib
from datetime import date as Date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC, APP = ROOT / 'src', ROOT / 'app'
MONTHS = 'január február március április május június július augusztus szeptember október november december'.split()
DAYS = 'hétfő kedd szerda csütörtök péntek szombat vasárnap'.split()


def load(p):
    with open(p, 'rb') as f:
        return tomllib.load(f)


ORDO = load(SRC / 'library/ordo.toml')
EPS = load(SRC / 'library/eucharistic-prayers.toml')
PREFACES = load(SRC / 'library/prefaces.toml')
COMMONS = {p.stem: load(p) for p in (SRC / 'library/commons').glob('*.toml')}
ALWAYS_PREFACES = ['ep2', 'ep4']


class BuildError(Exception):
    pass


def esc(s):
    return html.escape(s.strip(), quote=False)


def lines(s):
    """Prayer / antiphon: one line per verse line."""
    return '<br>'.join(esc(l) for l in s.strip().split('\n'))


def paras(s, cls=''):
    """Reading / preface: paragraphs separated by blank lines; single newlines become <br>."""
    c = f' class="{cls}"' if cls else ''
    return '\n'.join(f'<p{c}>{lines(p)}</p>' for p in re.split(r'\n\s*\n', s.strip()) if p.strip())


def p(text, cls=''):
    c = f' class="{cls}"' if cls else ''
    return f'<p{c}>{text}</p>'


def resp(text):
    return p(esc(text), 'resp')


def cite(c):
    return p(esc(c), 'cite') if c else ''


# ---------- options ("1 | 2 | 3" buttons) ----------

def resolve(opt, slot, names):
    """An option is plain text, a table {text, cite, label, source}, or "@common/N[:key]"."""
    if isinstance(opt, str) and opt.startswith('@'):
        m = re.fullmatch(r'@([\w-]+)/(\w+)(?::(\w+))?', opt)
        if not m:
            raise BuildError(f'bad reference {opt!r}')
        common, formula, key = m.group(1), m.group(2), m.group(3) or slot
        try:
            f = COMMONS[common][formula]
            opt = {'text': f[key], 'cite': f.get(key + '_cite', '')}
        except KeyError:
            raise BuildError(f'{opt!r}: no {key} in {common}/{formula}')
    elif isinstance(opt, str):
        opt = {'text': opt}
    opt = dict(opt)
    for a, b in names:
        opt['text'] = opt['text'].replace(a, b)
    if re.search(r'\bN\.', opt['text']):
        raise BuildError(f'{slot}: unreplaced "N." in {opt["text"][:60]!r} - add it to [names]')
    return opt


def options(value, slot, names, render):
    """Render one slot. Alternatives (e.g. two communion antiphons) get a row of buttons; the first is selected."""
    opts = value if isinstance(value, list) else [value]
    opts = [resolve(o, slot, names) for o in opts]
    if len(opts) == 1:
        return render(opts[0])
    btns = ''.join(f'<button type="button" class="alt-btn" aria-pressed="{"true" if i == 0 else "false"}" data-i="{i}">'
                   f'{esc(o.get("label", str(i + 1)))}</button>' for i, o in enumerate(opts))
    panels = '\n'.join(f'<div class="alt" data-i="{i}"{"" if i == 0 else " hidden"}>\n{render(o)}\n</div>'
                       for i, o in enumerate(opts))
    return f'<div class="alts"><div class="alt-btns" role="group" aria-label="Választható szövegek">{btns}</div>\n{panels}\n</div>'


def antiphon(o):
    return p(lines(o['text']), 'verse') + cite(o.get('cite', ''))


def prayer(intro):
    def r(o):
        return (p('Könyörögjünk!') if intro else '') + p(lines(o['text']), 'verse') + resp('Ámen.')
    return r


# ---------- readings ----------

def reading(r):
    out = [f'<h3>{esc(r.get("label", "Olvasmány"))}</h3>', p(esc(r['sub']), 'sub')]
    if r.get('summary'):
        out.append(p(esc(r['summary']), 'rub'))
    out += [paras(r['text']), p('Ez az Isten igéje.'), resp('Istennek legyen hála.'), cite(r['cite'])]
    return '\n'.join(out)


def psalm(s):
    out = ['<h3>Válaszos zsoltár</h3>', cite(s['cite']), resp(s['response'])]
    for v in s['verses']:
        out += [p(lines(v), 'verse'), resp(s['response'])]
    return '\n'.join(out)


def alleluia(a):
    return '\n'.join(['<h3>Alleluja</h3>', resp('Alleluja, alleluja!'), p(lines(a['text'])), cite(a['cite']), resp('Alleluja!')])


def gospel(g):
    out = ['<h3>Evangélium</h3>', p('Az Úr legyen veletek.'), resp('És a te lelkeddel.'),
           p(f'Evangélium {esc(g["book"])} könyvéből.'), resp('Dicsőség neked, Istenünk.')]
    if g.get('summary'):
        out.append(p(esc(g['summary']), 'rub'))
    out += [paras(g['text']), p('Ezek az evangélium igéi.'), resp('Áldunk téged, Krisztus.'), cite(g['cite'])]
    return '\n'.join(out)


def faithful(f):
    out = ['<h3>Egyetemes könyörgések</h3>', p(esc(f['intro']))]
    for i, pet in enumerate(f['petitions'], 1):
        if isinstance(pet, dict):
            out.append(p(esc(pet['note']), 'rub'))
            pet = pet['text']
        out += [p(f'{i}. {esc(pet)}'), resp(f['response'])]
    out += [p(esc(f['conclusion'])), resp('Ámen.')]
    return '\n'.join(out)


# ---------- preface / Eucharistic prayer choosers ----------

def chooser(group, label, items, default):
    sel = ''.join(f'<option value="{k}"{" selected" if k == default else ""}>{esc(lab)}</option>' for k, lab, _ in items)
    var = '\n'.join(f'<div class="variant" data-opt="{k}"{"" if k == default else " hidden"}>\n{body}\n</div>' for k, _, body in items)
    return (f'<div class="choice"><label for="sel-{group}">{label}</label><select id="sel-{group}" data-sel="{group}">{sel}</select></div>'
            f'<div class="variants" data-group="{group}" data-default="{default}">\n{var}\n</div>')


def preface_body(k):
    pr = PREFACES[k]
    return (p(esc(pr['sub']), 'sub') + '\n' if pr.get('sub') else '') + paras(pr['text'])


# ---------- one Mass ----------

def build_mass(path):
    m = load(path)
    d = Date.fromisoformat(m['date'])
    if path.stem != m['date']:
        raise BuildError(f'{path.name}: file name must be the date ({m["date"]})')
    names = m.get('names', [])
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

    h = []
    h.append('<section id="r1"><h2 class="part">Bevezető szertartás</h2>')
    h.append('<h3>Bevezető ének</h3>' + options(m['entrance'], 'entrance', names, antiphon))
    h += [ORDO['greeting'], ORDO['penitential'], ORDO['kyrie']]
    if m.get('gloria'):
        h.append(ORDO['gloria'])
    h.append('<h3>Könyörgés</h3>' + options(m['collect'], 'collect', names, prayer(True)))
    h.append('</section>')

    h.append('<section id="r2"><h2 class="part">Az Ige liturgiája</h2>')
    h.append(reading(m['reading1']))
    h.append(psalm(m['psalm']))
    if 'reading2' in m:
        h.append(reading(m['reading2']))
    h.append(alleluia(m['alleluia']))
    h.append(gospel(m['gospel']))
    h.append('<h3>Homília</h3>')
    if m.get('creed'):
        h.append(ORDO['creed'])
    h.append(faithful(m['faithful']))
    h.append('</section>')

    h.append('<section id="r3"><h2 class="part">Az Eucharisztia liturgiája</h2>')
    h.append(ORDO['gifts'])
    h.append('<h3>Felajánló könyörgés</h3>' + options(m['offertory'], 'offertory', names, prayer(False)))
    h.append('<h3>Prefáció</h3>' + ORDO['preface_dialogue'])
    h.append(chooser('pref', 'Prefáció', [(k, PREFACES[k]['label'], preface_body(k)) for k in pref_keys], pref_keys[0]))
    h.append(ORDO['sanctus'])
    h.append('<h3>Eucharisztikus ima</h3>')
    h.append(chooser('ep', 'Eucharisztikus ima', [(k, v['label'], v['html']) for k, v in EPS.items()], ep))
    h.append('</section>')

    h.append('<section id="r4"><h2 class="part">A szentáldozás szertartása</h2>')
    h.append(ORDO['communion_rite'])
    h.append('<h3>Áldozási ének</h3>' + options(m['communion'], 'communion', names, antiphon))
    h.append('<h3>Áldozás utáni könyörgés</h3>' + options(m['postcommunion'], 'postcommunion', names, prayer(True)))
    h.append('</section>')
    h.append('<section id="r5"><h2 class="part">Befejező szertartás</h2>\n' + ORDO['concluding'] + '\n</section>')

    latin = ''
    if m.get('latin'):
        grid = (SRC / 'masses' / m['latin']).read_text(encoding='utf-8')
        latin = ('<section id="latin" class="bilingual"><h2 class="part">Latin–magyar szöveg</h2>'
                 '<p class="jump"><a class="btn" href="#top">↑ Vissza a magyar szöveghez</a></p>'
                 f'{grid}<p class="jump"><a class="btn" href="#top">↑ Vissza a magyar szöveghez</a></p></section>')

    readings = ' · '.join(x['cite'] for x in (m['reading1'], m['psalm'], m.get('reading2'), m['gospel']) if x)
    return {
        'date': m['date'],
        'dateLabel': f'{d.year}. {MONTHS[d.month - 1]} {d.day}. · {DAYS[d.weekday()]}',
        'title': m['title'],
        'rank': m.get('rank', ''),
        'meta': [m.get('day', ''), readings, EPS[ep]['label']],
        'hasLatin': bool(latin),
        'html': '\n'.join(h) + latin,
    }


def main():
    out = APP / 'data' / 'masses'
    out.mkdir(parents=True, exist_ok=True)
    cal, errors, written = [], [], set()
    for path in sorted((SRC / 'masses').glob('*.toml')):
        try:
            mass = build_mass(path)
        except (BuildError, KeyError) as e:
            errors.append(f'{path.name}: {e}')
            continue
        (out / f'{mass["date"]}.json').write_text(json.dumps(mass, ensure_ascii=False), encoding='utf-8')
        written.add(f'{mass["date"]}.json')
        cal.append({'date': mass['date'], 'title': mass['title']})
    if errors:
        sys.exit('Build failed:\n  ' + '\n  '.join(errors))
    for stale in out.glob('*.json'):
        if stale.name not in written:
            stale.unlink()
    (APP / 'data' / 'calendar.json').write_text(json.dumps({'masses': cal}, ensure_ascii=False, indent=1), encoding='utf-8')

    # New service-worker cache name whenever any app file changes, so installed apps pick up the update.
    digest = hashlib.sha256()
    for f in sorted(APP.rglob('*')):
        if f.is_file() and f.name != 'sw.js':
            digest.update(f.relative_to(APP).as_posix().encode() + f.read_bytes())
    sw = APP / 'sw.js'
    sw.write_text(re.sub(r"const CACHE = '[^']*';", f"const CACHE = 'szentmise-{digest.hexdigest()[:10]}';",
                         sw.read_text(encoding='utf-8')), encoding='utf-8')
    print(f'{len(cal)} masses: ' + ', '.join(c['date'] for c in cal))


if __name__ == '__main__':
    main()
