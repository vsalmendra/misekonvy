# How a Mass is assembled

This is the growing rulebook for turning a calendar day into a Mass text. Each day's own
recipe is in `src/masses/<date>.md`. Whenever a recipe repeats a pattern, move the pattern here,
so that masses can later be generated in bulk.

## The pieces

A Mass is put together from four kinds of text:

| Kind | Where it lives | Changes |
|---|---|---|
| **Fixed parts** (Order of Mass): greeting, penitential act, Kyrie, (Gloria), (Creed), preparation of the gifts, preface dialogue, Sanctus, communion rite, concluding rite | `src/library/ordo.toml` | never (new Hungarian missal wording) |
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
names = [["Szent N.-t", "Boldog Károlyt"], ["Szent N.", "Boldog Károly"]]  # only when a common text has "N."
latin = "2026-10-20.latin.html"        # optional Latin–Hungarian section

entrance = "@szentek-altalanos/1"      # reference: common file / formula (key = the slot name)
communion = ["@szentek-altalanos/1", "@szentek-altalanos/1:communion_b"]  # alternatives -> buttons 1 | 2
```

Text slots (`entrance`, `collect`, `offertory`, `communion`, `postcommunion`) take one of:

- a table `{ text = '''...''', cite = "...", source = "..." }`;
- a reference `"@<commons file>/<formula>"`, optionally `":<key>"` for another key of the formula;
- a **list** of the above: the alternatives the book gives for the *same* slot ("Vagy:"). The app
  shows them as a row of buttons, the first one selected. Use this only for alternatives inside one
  formula, not to offer several formulas of a common (see the rule below).

Plain-text conventions: prayers and antiphons are one line per verse line; readings, prefaces
and gospels are paragraphs separated by a blank line. The build adds "Könyörögjünk!", "Ámen.",
the reading acclamations, the gospel dialogue, the psalm response after every strophe and the
numbering of the petitions.

The build refuses to run if a text still contains an unreplaced `N.` (except the optional
petition for a deceased person, which is marked with a rubric).

## Rules found so far

**Calendar and readings**
- Source of the day, readings and prayer of the faithful: igenaptar.katolikus.hu
  (`/nap/index.php?holnap=YYYY-MM-DD`; the month page `/` lists ranks and optional memorials).
- Weekdays, memorials and votive masses use the **ferial (continuous) readings** of the day,
  not the proper readings of the saint, unless the user asks otherwise.
- igenaptár labels Pauline readings "Szentlecke"; keep its label.
- The prayer of the faithful from igenaptár: drop the "Pap:", "Lektor:", "Hívek:" labels, write the
  people's response in full, keep the optional petition for a deceased person with its rubric.

**Gloria, Creed**
- Sundays: Gloria + Creed. Solemnities: both. Feasts: Gloria only.
- Weekdays, memorials, votive masses: neither. (Gloria and Creed are not in `ordo.toml` yet; add
  them before the first Sunday.)

**Saints and blesseds (memorials)**
- Proper collect if the saint/blessed has one (Hungarian proper or the national calendar);
  everything else from the common.
- **From a common, always take the first formula** (e.g. "Szentek általános miséi" 1). Do not offer
  several formulas.
- If the formula itself gives alternatives ("Vagy:"), include all of them as buttons, first selected.
- Prefaces: the saints' prefaces (I, II), or a proper one (martyrs, pastors, virgins…) if suggested.
- Replace "N." with the name in the case the sentence needs ("Szent N.-t" → "Boldog Károlyt").
- Drop "(H. i. alleluja)" outside Eastertime.

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
| Latin missal | clerus.org (Missale Romanum 2002), ordo.pallotyni.pl (Ordo, EPs, prefaces) |
| Latin Bible | Nova Vulgata on vatican.va |
