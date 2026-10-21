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
latin_note = "…csak magyarul van meg; latinul a közös mise könyörgése áll."
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
still missing; the page shows "(A latin szöveg még nincs feltöltve.)" in their place.

## The page

- Header: date, title, colour, then the day ("29. évközi hét szerdája · választható emléknap") and
  **which Mass is used** (`mass_type`: proper / common (formula) / votive …). The Eucharistic prayer
  and the readings are **not** listed in the header.
- The **Latin–Hungarian section is always there**. Its preface and Eucharistic prayer follow the
  choice made in the Hungarian part. The prayer of the faithful is only in Hungarian.
- A Hungarian-only prayer (e.g. the own collect of a Hungarian blessed) has no Latin: the Latin
  column takes the common's prayer and a note says so (`latin_note`).

## Rules found so far

**Calendar and readings**
- Source of the day, readings and prayer of the faithful: igenaptar.katolikus.hu
  (`/nap/index.php?holnap=YYYY-MM-DD`; the month page `/` lists ranks and optional memorials).
- Weekdays, memorials and votive masses use the **ferial (continuous) readings** of the day,
  not the proper readings of the saint, unless the user asks otherwise.
- igenaptár labels Pauline readings "Szentlecke"; keep its label.
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
- Prayers with alternatives in the book ("Vagy:"): include all of them as buttons, first selected.
- **Collect: the common's only** (user's decision 2026-10-21, applied again 2026-10-22), even when
  the saint has an own collect — record the proper in the day's recipe. (Earlier rule, now
  superseded:) — "Saját" (the proper, first) and "Közös" (the common's
  collect), for celebration missals that do not yet have the proper.
- Prefaces: the saints' prefaces (I, II), or a proper one (martyrs, pastors, virgins…) if suggested.
- Replace "N." with the name in the case the sentence needs ("Szent N.-t" → "Boldog Károlyt").
- Drop "(H. i. alleluja)" outside Eastertime.

**Commons available** (`src/library/commons/`): `szentek-altalanos` (Szentek általános miséi 1-6;
Latin only for 1), `lelkipasztorok` (`papak-puspokok-1`: collect for popes, `collect_b` for
bishops). Pastors (popes, bishops, priests) → Lelkipásztorok miséi, preface `lelkipasztorok`.

**Votive masses** — propers from the votive formula of the missal; readings ferial.

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

| Text | Source |
|---|---|
| Readings, psalm, alleluia, prayer of the faithful | igenaptar.katolikus.hu |
| Commons, prefaces (until the new missal is available) | PPEK 335, Római Misekönyv 1991 |
| Proper collects of Hungarian blesseds not in the 1991 missal | parish / Magyar Kurír copies; note both and the differences |
| Latin missal | ordo.pallotyni.pl (Missale Romanum 2008: Ordo, EPs, prefaces, temporal); clerus.org (MR 2002 scans, file names hard to find — the Commune sanctorum not located yet) |
| Latin readings, psalm, alleluia; Latin commons | **Missale Romanum cum lectionibus 1977** (4 vols., archive.org item `MissaleRomanumCumLectionibus1977Vol34`, `*_djvu.txt` OCR: fix OCR errors by hand). Vol. IV: weeks 22-34 + commons. Fallback for readings: Nova Vulgata on vatican.va |
