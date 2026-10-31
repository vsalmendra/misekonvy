# How a Mass is assembled

This is the growing rulebook for turning a calendar day into a Mass text. Each day's own
recipe is in `src/masses/<date>.md`. Whenever a recipe repeats a pattern, move the pattern here,
so that masses can later be generated in bulk.

## The pieces

A Mass is put together from four kinds of text:

| Kind | Where it lives | Changes |
|---|---|---|
| **Fixed parts** (Order of Mass): greeting, penitential act, Kyrie, (Gloria), (Creed), preparation of the gifts, preface dialogue, Sanctus, communion rite, concluding rite | `src/library/ordo.toml`, Latin–Hungarian pairs in `src/library/ordo-latin.toml` | never (new Hungarian missal wording) |
| **Eucharistic prayers** I–IV | `src/library/eucharistic-prayers.toml` | never; the day only picks the default |
| **Prefaces** | `src/library/prefaces.toml` | the day picks the suggested ones |
| **Propers**: entrance antiphon, collect, readings, psalm, alleluia, gospel, prayer of the faithful, prayer over the offerings, communion antiphon, prayer after communion | `src/masses/<date>.toml`, or a reference into `src/library/commons/*.toml` | every day |

The build (`python3 tools/build.py`) merges them into `app/data/masses/<date>.json` and lists
every date in `app/data/calendar.json`. The app shows only those dates in its date picker.

## Mass file (`src/masses/<date>.toml`)

```toml
date = "2026-10-21"                    # file name must be the same date
title = "Boldog IV. Károly király"
day = "29. évközi hét szerdája · választható emléknap"
rank = "fehér színben"                  # liturgical colour line under the title
gloria = false                         # Sundays, solemnities, feasts: true
creed = false                          # Sundays, solemnities: true
eucharistic_prayer = 3                 # default in the dropdown (1-4)
prefaces = ["szentek-1", "szentek-2"]  # suggested, first is the default; ep2 and ep4 are always added after them
names = [["Szent N.-t", "Boldog Károlyt"], ["Szent N.", "Boldog Károly"]]  # "N." in Hungarian texts (commons, prefaces); longest first
la_names = [["beatum N.", "beatum Ioannem Paulum"], ["sancti N.", "sancti Ioánnis Pauli"]]  # the same in Latin, by case
mass_type = "Szentek általános miséje (1) · saját könyörgéssel"  # shown under the title: which Mass is used

entrance = "@szentek-altalanos/1"      # reference: common file / formula (key = the slot name)

[[collect]]                            # alternatives -> buttons "Saját | Közös", first selected
label = "Saját"
hu_only = true                         # no Latin equivalent: Latin column blank, note "Nincs latin megfelelője."
text = '''...'''
[[collect]]
label = "Közös"
ref = "@szentek-altalanos/1"
```

Text slots (`entrance`, `collect`, `offertory`, `communion`, `postcommunion`) take one of:

- a table `{ text = '''...''', cite = "...", source = "..." }`;
- a reference `"@<commons file>/<formula>"`, optionally `":<key>"` for another key of the formula;
- a **list** of the above (or `[[slot]]` tables, `ref` + `label`): alternatives for the same slot.
  The app shows them as a row of buttons, the first one selected. Used for prayers only (see rules);
  antiphons never get alternatives.

Readings with alternatives (e.g. feast or weekday): `[[readings]]` tables, each with `label` and
its own `reading1`, `psalm`, (`reading2`), `alleluia`, `gospel` subtables; buttons, first selected;
the Latin section follows the choice. A missing Hungarian text shows a placeholder (`NO_HU`).
Feasts (Ü): Gloria (`gloria = true`). On a feast on a weekday, offer the feast's readings first and
the weekday's second.

Every text can carry its Latin: `la` (same line/paragraph layout as `text`), `la_cite`; readings
`la_sub` + `la`, gospel `la_book` ("Lucam") + `la`, psalm `la_response` + `la_verses`, alleluia `la`.
Commons use `<key>_la`. Prefaces have `la_label` + `la`; Eucharistic prayers `la_label` + `la`
(one entry per Hungarian paragraph, rubrics skipped).

Plain-text conventions: prayers and antiphons are one line per verse line; readings, prefaces
and gospels are paragraphs separated by a blank line. The build adds "Könyörögjünk!", "Ámen.",
the reading acclamations, the gospel dialogue, the psalm response after every strophe and the
numbering of the petitions.

The build refuses to run if a text still contains an unreplaced `N.` (except the optional
petition for a deceased person, which is marked with a rubric). It prints how many Latin texts are
still missing; the page leaves the Latin column blank there, with a short note "Latinul még nincs
feltöltve." beside the first line of the text.

## The page

- Days without a Mass file show the Order of Mass alone (`ORDINARY` in `tools/build.py`): the day's
  prayers as rubric placeholders, prefaces of EP II (default) and EP IV, EP II default, and the
  readings of the **liturgical day** (`tools/litcal.py` → `src/cycle/<key>.json`, fetched from
  igenaptár; long forms kept, singing aids stripped; no Latin yet — in the Latin section the Hungarian
  column has them and the Latin column is blank with a note). Fixed-date feasts/solemnities (igenaptár "– Ü"/"– FÜ") are stored as `fix-MM-DD` and
  override the seasonal day (an Ü not on a Sunday). When a day gets a Mass file, its own readings are
  used; `src/cycle/<key>.json` is a good start for them.

- Header: date, title, colour, then the day ("29. évközi hét szerdája · választható emléknap") and
  **which Mass is used** (`mass_type`: proper / common (formula) / votive …). The Eucharistic prayer
  and the readings are **not** listed in the header.
- The **Latin–Hungarian section is always there**. Its preface, Eucharistic prayer, readings and the
  alternatives of each prayer (buttons) follow the choice made in the Hungarian part.
- **Text without a Latin equivalent** (prayer of the faithful; a Hungarian-only proper, marked
  `hu_only = true`): the Hungarian column has the text, the Latin column stays blank with a discreet
  note "Nincs latin megfelelője." (`latin_note = "…"` replaces the note's wording).
- **Jump list** (menu → "A mise részei", buttons "Magyar | Latin–magyar"): built from the page — parts (h2), headings (h3),
  and marked points inside long texts (`data-toc`: Köszöntés; in the Eucharistic prayer the
  consecration, "Hitünk titka", the doxology; Áldás és elbocsátás). Only structural names, nothing
  of the day (user, 2026-10-29): no citations, the preface / EP listed as "Prefáció" / "Eucharisztikus
  ima". A new heading in a text appears there by itself.

## Rules found so far

**Calendar and readings**
- Source of the day, readings and prayer of the faithful: igenaptar.katolikus.hu
  (`/nap/index.php?holnap=YYYY-MM-DD`; the month page `/` lists ranks and optional memorials).
- Weekdays, memorials and votive masses use the **ferial (continuous) readings** of the day,
  not the proper readings of the saint, unless the user asks otherwise.
- igenaptár labels Pauline readings "Szentlecke"; keep its label: it is the first word of the
  **title the reader announces** ("Szentlecke Szent Pál apostolnak a filippiekhez írt leveléből."),
  shown in black small capitals just above the text. The heading names only the place: "Olvasmány"
  (one reading), "Első olvasmány" / "Második olvasmány" (two). The lectionary's summary sentence
  (`summary`) comes between the heading and the title, in red italics (user, 2026-10-30).
- **Prayer of the faithful: from the lectionary, not from igenaptár.** The weekday lectionary has
  different sets for even and odd years, and igenaptár does not always pick the right one.
  (Source still to be found online — www.liturgia.hu? Until then igenaptár's text is used and the
  day's recipe says so.) Drop "Pap:/Lektor:/Hívek:", write the response in full, keep the optional
  petition for a deceased person with its rubric.

**Gloria, Creed**
- Sundays: Gloria + Creed. Solemnities: both. Feasts: Gloria only.
- Weekdays, memorials, votive masses: neither. (Gloria and Creed are not in `ordo.toml` yet; add
  them before the first Sunday.)

**Saints and blesseds (memorials)**
- Proper collect if the saint/blessed has one (Hungarian proper or the national calendar);
  everything else from the common.
- **From a common, always take the first formula** (e.g. "Szentek általános miséi" 1). Do not offer
  several formulas.
- **Antiphons (entrance, alleluia, communion): no alternatives** — take the first one given,
  unless the user says otherwise.
- Prayers with alternatives in the book ("Vagy:"): **only the first one** (user, 2026-10-25),
  unless the user asks for the alternatives (then buttons, first selected).
- **Collect with an official proper: two options** — "Saját" (first) and "Közös" (the common's),
  for celebration missals without the proper. Look for it in the CDW decrees on vatican.va (Latin)
  and in Vatican News Hungarian. If the proper is not official or its wording is uncertain
  (Boldog IV. Károly, 2026-10-21: the user removed it), use only the common's and record the proper
  in the day's recipe.
- Prefaces: the saints' prefaces (I, II), or a proper one (martyrs, pastors, virgins…) if suggested.
- Replace "N." with the name in the case the sentence needs ("Szent N.-t" → "Boldog Károlyt").
- Drop "(H. i. alleluja)" outside Eastertime.

**Commons available** (`src/library/commons/`): `szentek-altalanos` (Szentek általános miséi 1-6;
Latin only for 1), `lelkipasztorok` (`papak-puspokok-1`: collect for popes, `collect_b` for
bishops). Pastors (popes, bishops, priests) → Lelkipásztorok miséi, preface `lelkipasztorok`.
`elhunytak` (Megemlékező gyászmisék több vagy minden elhunytért: `tobb-c`, `tobb-d`, `tobb-e`;
`collect_b` / `postcommunion_b` = the "Vagy:"; Latin for all).

**Masses for the dead** — allowed on ferial weekdays. Propers from the missal's "Gyászmisék"
(several or all dead: formula C first); colour violet; prefaces of the dead I–V (`megholtak-1`…`-5`),
I by default; readings ferial unless the user asks for the lectionary for the dead. The names
("N.-nek és N.-nek", Latin "(N. et N.)") are optional: for all the dead drop them with `names` /
`la_names`, for named dead put the names in.

**Votive masses** — propers from the votive Mass's own first formula (e.g. "A"), not from a feast
the rubric also allows (user, 2026-10-28: Eucharist votive → formula A, not Úrnapja); readings ferial.

**Prefaces** — the dropdown always offers, after the day's suggestions, the own prefaces of
Eucharistic prayers II and IV. Choosing EP IV switches the preface to EP IV's own (it may only be
said with it).

**Wording**
- New Hungarian missal (Pentecost 2023; Romania 29 June 2023). There is no online copy; the
  1991 edition on PPEK (ppek.hu/k335.htm, `Misekonyv_1.pdf`) is the fallback, with the new-missal
  changes listed in `CLAUDE.md`. Mark every text taken from 1991 in its `source`.
- Pope: "Leó pápánk(kal/at/ról)", Latin "Papa nostro Leóne"; bishop still N.
- Strip singing aids: capitals inside words (ATyánk), dashes at line starts, "(Mert)", "(És)",
  "(Most)", "(zengjük:)", "(énekeljük:)", psalm asterisks, tone numbers ("– 2. tónus").
- Lowercase "te" for God inside prayers, as in the missal ("a te országodba").

## Sources

**Only liturgical sources** (missal, lectionary, official liturgical decrees and their published
texts) — never a Bible translation (Nova Vulgata, SZIT/szentiras.hu, Károli …), not even for Latin.
If the liturgical text is not available, show the placeholder and say so (user's rule, 2026-10-28).

| Text | Source |
|---|---|
| Readings, psalm, alleluia, prayer of the faithful | igenaptar.katolikus.hu |
| Commons, prefaces (until the new missal is available) | PPEK 335, Római Misekönyv 1991 |
| Propers that igenaptár also gives (antiphons, prayers) | **igenaptár's wording wins over 1991** where they differ (likely the new missal; user, 2026-10-31); note both in the recipe |
| Proper collects of Hungarian blesseds not in the 1991 missal | parish / Magyar Kurír copies; note both and the differences |
| Latin missal | ordo.pallotyni.pl (Missale Romanum 2008: Ordo, EPs, prefaces, temporal); clerus.org (MR 2002 scans, file names hard to find — the Commune sanctorum not located yet) |
| Latin readings, psalm, alleluia; Latin commons | **Missale Romanum cum lectionibus 1977** (4 vols., archive.org item `MissaleRomanumCumLectionibus1977Vol34`, `*_djvu.txt` OCR: fix OCR errors by hand). Vol. IV: weeks 22-34 + commons. |
