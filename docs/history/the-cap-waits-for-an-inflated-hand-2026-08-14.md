# The cap waits for an inflated hand (the floor moves with our prize counter)

[← Documentation index](../README.md) · A card rule of
[the day of 14 Aug 2026](../day-plan-2026-08-14.md)

**The criterion below was written before the change was measured**, in the
gate's own docstring (`utils/gate_the_cap_waits_for_an_inflated_hand.py`). That
ordering is the whole point: an acceptance test written after the number is not
an acceptance test.

---

## The record

`records/registro_003_pasos_025_hasta_031.json`, episode 92856565, **step 29**,
turn 3 vs Alakazam — LOST. Six prizes each, our Tapu Bulu active, and the menu
was {play Xerosic's Machinations, play Lillie's Determination, play Ogerpon ex,
end turn}. The turn's Supporter went on the **Xerosic** with the opponent
holding **six** cards: their hand 6 → 3, three cards their deck gives straight
back, and the matchup's only answer to Powerful Hand spent on turn 3.

The old floor of six (bought by step 17 of the same record) was cleared **by one
card**. Six is the size a hand simply IS after the draw, so on turn 3 the floor
was not measuring an inflated hand, it was measuring a dealt one.

## The rule

`_xr_alakazam_floor` (`ptcg/decision/disruption.py`). The floor is two numbers
and **our** prize counter picks between them:

| our prizes remaining | opposing hand the cap waits for |
| --- | --- |
| ≥ 5 | **8** (`XEROSIC_ALAKAZAM_FLOOR_EARLY`) |
| < 5 | **6** (`XEROSIC_ALAKAZAM_FLOOR_LATE`) |

ONE predicate, read by everything that decides about this card, because a
Supporter the play side vetoes is not one worth a two-prize body:

* the play ladder — `alakazam_needs_the_hand_floor` (renamed from
  `alakazam_needs_six_cards`) and `_xr_gate_alakazam`;
* the Last-Ditch fetch — `alakazam_xerosic_needs_the_hand_floor`,
  `xerosic_alakazam`, `xerosic_priority_over_boss`;
* the Ultra Ball engine that digs for it — `_alakazam_dig_xerosic_engine`.

`_CtxMeowthFetch` carries `my_prize` for that, defaulting to six — the opening
board, the strict end of the floor — so no caller loses the rule by forgetting
to pass it.

## The criterion (written first)

This is a **card rule stated by the user off a lost record**, not an estimated
improvement queued by a census. So neutral does **not** order a revert here: it
orders the marking. A neutral result is recorded as a user override and the rule
stays. What the gate is really asked is whether the change **costs** anything —
a significant negative delta is the finding that would send it back.

## The exposure (`--census`)

    CENSO sobre el corpus congelado: 7 de 3580 decisiones (0.20%) en 50 registros

Seven decisions, in **three** of the fifty records, and all seven are one board:
opposing hand **seven** with **six** of our prizes up (registro_001/005/006,
turn 4) — plus step 29 itself in the golden corpus. Nothing outside the band the
rule closes. The gate prints its own warning at that exposure: an event this
narrow can be invisible to self-play at any N worth paying for.

## The measurement (5 000 games per arm)

Both arms are the same tree loaded twice, with `XEROSIC_ALAKAZAM_FLOOR_EARLY`
rebound to the late floor in the baseline — the rule as it was, one number out
of place and nothing else. Provenance printed `candidato suelo=8, baseline
suelo=6`.

| deck | with the rule | without | delta | prizes/game |
| --- | --- | --- | --- | --- |
| alakazam | 99.54 % | 99.60 % | **−0.06 pts** (z −0.46, p 0.647) | 3.48 vs 3.46 |
| crustle_kangaskhan *(blind control)* | 77.80 % | 76.58 % | +1.22 pts (z 1.45) | 4.29 vs 4.24 |

**The noise floor of the same session** (`--control`: both arms neutralised, the
same code twice, same N):

| deck | arm A | arm B | delta | prizes/game |
| --- | --- | --- | --- | --- |
| alakazam | 99.48 % | 99.36 % | **+0.12 pts** (z 0.79) | 3.46 vs 3.41 |
| crustle_kangaskhan *(blind control)* | 76.12 % | 76.14 % | −0.02 pts | 4.24 vs 4.24 |

## The verdict: NEUTRAL, and the rule stays marked

The measured delta (−0.06 pts) is **smaller than the run's own noise floor**
(+0.12 pts on the same deck, same N, identical code) and twenty times smaller
than the blind control deck's +1.22 — a deck where the rule cannot fire at all.
The prize differential says the same thing: +0.02 measured against +0.05 of
noise. **Nothing here clears zero, in either direction.**

Two readings, and both were written before the numbers:

* the exposure explains it — 0.20 % of decisions, three records in fifty. A
  winrate against a bot we beat 99.5 % of the time cannot resolve that, and the
  saturation is itself the finding: on this instrument the Alakazam column has
  no headroom left to measure a card rule in;
* the criterion holds — neutral is **not** a revert for a user card rule. It
  ships **marked as an override**, exactly like the Cornerstone routes and the
  slot-belongs-to-the-search change before it.

What the gate did earn: the change **costs nothing measurable**, and the corpus
is clean — the seven flips are all the one board the rule was written about.

## The second instrument: the oracle, on the record's own board

The gate cannot answer "was this the better play" — it can only count wins
against a bot we beat 99.5 % of the time. So the question was asked again with
`utils/oracle_the_cap_waits_for_an_inflated_hand.py`, which rolls the boards out
to the end under the ENGINE'S rules (`utils/search_oracle.py`, phase D): force
one option, play to the end with our agent driving both seats, K rollouts.

**The record's board, step 29, K=100** — and the list was detected rather than
assumed: the fixture closes on sixty per seat under today's `deck.csv`, so that
game was played with the current sixty.

| option | rollouts won | prize margin |
| --- | --- | --- |
| with the rule (hold the cap, play Lillie's) | 100/100 | **+4.88** |
| without it (play the cap) | 100/100 | **+4.75** |
| delta | +0 pp | **+0.13** |
| the board's own floor (same option, other seeds) | 3 pp | **0.20** |

**Inside the floor.** At K=5 the margin looked like +0.60 for holding the cap; at
K=100 it shrinks to +0.13 against a floor of 0.20 measured on that same board.
The oracle killed the hunch by itself, which is exactly what a per-board floor
is for — and it is the module's own warning made concrete: *K=20 is not enough
for anything*.

The winrate saturates here too (100/100 both ways), so the prize margin is the
only column with resolution left. Two readings survive:

* **the rule is not a mistake on the board it was written for** — no option
  loses ground, and holding the cap is, if anything, marginally ahead;
* **and it is not provably better either.** A card rule from a lost record
  ships on the record, not on this number.

### What is still ungradeable, and it is said out loud

Two of the seven corpus boards cannot be graded at all: no Alakazam list we hold
lets their side close on sixty (`seat 1: 24 seen + 0 hand + 6 prize + 31 deck =
61`). The fifty frozen records are fifty different games against different
builds, and the determinization guard refuses a world the engine would have
accepted while playing a different game. They are reported as NOT GRADEABLE
rather than skipped in silence. The remaining five are queued for a night run at
K=100 (~30 min):

    python utils/oracle_the_cap_waits_for_an_inflated_hand.py --k 100

See [[el-suelo-del-tope-vs-alakazam-son-dos-numeros-y-los-separa-nuestro-marcador-de-premios]],
[[un-override-del-usuario-no-es-una-excepcion-de-la-politica]] and
[[el-censo-de-disparo-decide-si-neutro-obliga]].

---

Next: [the day](../day-plan-2026-08-14.md) · [Instruments](../instruments.md) ·
[Improving the agent](../improving-the-agent.md)
