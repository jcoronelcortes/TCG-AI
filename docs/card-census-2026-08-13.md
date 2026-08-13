# The card census — results, 13 August 2026

[← Documentation index](README.md) · [the plan this executes](card-census-plan-2026-08-13.md) · [why it was the top pending item](playbook-vs-meta-2026-08-13.md)

**Status: the plan's eight blocks B0–B7 are done.** The instrument is
`utils/card_census.py`, its two halves are pinned by
`tests/test_the_card_census_closes_on_sixty.py` (16 tests), and the numbers below
come from **10 635 simulated games** across 133 real lists weighted by meta share,
**2 500 more** on the two hard matchups, and **106 real ladder games** of our own.

Three independent winrates came out of the harness matching what the matrix
already said — 93.9 % on the weighted corpus, 78.6 % against `crustle_wall_1`,
86.9 % against `ogerpon_verde_1` — which is the cheapest evidence that the census
is watching the same games everything else measures.

---

## 1. What the plan got wrong, and what the engine actually does

The plan was written against one real episode and verified as far as one episode
can verify. Four of its design decisions did not survive contact with more data,
and the corrections matter more than any single card number.

**The fodder rule is simpler and stronger than planned.** §6.3 budgeted risk for
"a `HAND→DISCARD` with no `PLAY` for that serial in the same step", worrying that
a played Supporter and a discarded cost look alike. They do not look alike at all:
a played card emits **`PLAY` and no movement event whatsoever** — 22 of 22 on the
first episode, with zero paired movements — and every one of the 14
`HAND→DISCARD` events belonged to a copy that was never played. No same-step
correlation is needed.

**The impossible prize arithmetic was double counting.** §6.5 flagged 8
`PRIZE→HAND` events in a game that awards 6 prizes and rightly refused to trust
anything prize-shaped until it resolved. The cause is that **both seats' events
arrive in our own stream**, tagged by `playerIndex`. Filtered, the same game shows
**5 prize events, 5 prizes taken and 1 still face-down at the end** — it adds up.
The plan's §1.3 event table has the same defect and should be read as the
opponent's traffic mixed into ours.

**A fate is not a first-match-wins list.** §2's ordered rules assumed each fires
once. A copy can be drawn, shuffled back by a Marnie and drawn again: two rules
fire, and the list answered `DEVUELTA_AL_MAZO` for a card sitting in our hand at
the end. The fate is now **how the copy last left our hand**, with the observation
as the authority on where it ended. On the validation episode the resolver's
dead-in-hand set then reproduces the observed final hand exactly, card for card —
two independent sources agreeing on one fact.

**A mill opponent hides the hand it empties.** Running 10 635 games made the
resolver's own alarm fire 48 times, which is what the alarm is for. All twenty
attributable transitions were then censused and two were unhandled. The
interesting one is `LOOKING→DISCARD`: the opponent rifling our hand emits a
**face-down `HAND→LOOKING` with no cardId**, so the copy vanishes and only
reappears on its way to the discard. It gets its own fate,
`DESCARTADA_EN_REVELADO`, rather than being called fodder — we did not choose to
spend it. It concentrates exactly where it should: **19 of 36 games against Comfey
mill, against 21 of 1 096 versus Crustle Wall.**

---

## 2. V1 — the list, pooled over the weighted meta

10 635 games, 133 lists, budget by meta share. Ordered by conversion, worst first.
`conv` is conversion given the card was drawn — the plan's headline metric.

| card | cop | drawn | conv | dead in hand | fodder | declined | first play |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Xerosic's Machinations | 2 | 71.2 | **19.6** | 23.9 | 14.1 | 29.9 | 8.2 |
| Unfair Stamp | 1 | 68.4 | **23.5** | 28.7 | 0.1 | 32.0 | 9.9 |
| Boss's Orders | 2 | 70.7 | **31.1** | 19.5 | 9.7 | 30.6 | 9.7 |
| Dawn | 1 | 70.8 | **31.3** | 22.8 | 4.9 | 31.5 | 7.2 |
| Lana's Aid | 1 | 69.5 | **33.3** | 16.7 | 10.0 | 30.8 | 10.3 |
| Night Stretcher | 2 | 70.0 | 40.7 | 16.7 | 10.4 | 28.8 | 8.5 |
| Tapu Bulu | 2 | 73.9 | 43.7 | 19.7 | 12.4 | 19.2 | 3.2 |
| Fezandipiti ex | 1 | 72.7 | 47.4 | 19.8 | 7.7 | 25.4 | 5.5 |
| Ultra Ball | 4 | 69.1 | 47.9 | 17.9 | 6.0 | 27.1 | 5.2 |
| Forest of Vitality | 4 | 69.9 | 48.6 | 13.4 | 13.5 | 26.3 | 6.3 |
| Meowth ex | 2 | 76.9 | 50.0 | 18.9 | 6.6 | 23.8 | 4.1 |
| Hydrapple ex | 2 | 82.5 | 51.9 | 18.3 | 7.0 | 10.8 | 7.1 |
| Meganium | 2 | 83.6 | 52.1 | 17.4 | 9.8 | 10.2 | 6.6 |
| Bayleef | 2 | 84.2 | 56.1 | 17.1 | 8.3 | 9.2 | 5.5 |
| Chikorita | 2 | 82.1 | 62.5 | 15.7 | 7.6 | 7.0 | 3.2 |
| Dipplin | 2 | 84.4 | 65.0 | 15.6 | 3.9 | 10.7 | 6.0 |
| Poké Pad | 1 | 69.6 | 68.3 | 14.2 | 2.3 | 24.2 | 4.7 |
| Teal Mask Ogerpon ex | 4 | 78.5 | 69.0 | 14.5 | 4.6 | 8.1 | 3.6 |
| Applin | 2 | 83.6 | 77.2 | 12.1 | 3.1 | 6.1 | 3.6 |
| Lillie's Determination | 4 | 72.8 | 77.9 | 8.7 | 1.8 | 22.1 | 6.1 |
| Basic {G} Energy | 13 | 77.2 | 85.8 | 6.1 | 2.0 | 11.9 | 6.4 |
| Bug Catching Set | 4 | 69.4 | 90.5 | 4.9 | 0.2 | 18.7 | 5.8 |

**The `declined` column is new information no other instrument produces.**
`DECK→LOOKING→DECK` is us searching, seeing a card and putting it back. Roughly
**30 % of the copies of the five worst converters get looked straight past**,
against 6–11 % for the Stage-2 line. The searches are not failing to find those
cards; they are finding them and declining them.

---

## 3. V3 — and the confound that eats it

**The raw wins-vs-losses split measures the clock, not the cards.** Across the
corpus a won game runs **13.1 turns and a lost one 31.0**. Every card therefore
gets more chances to be played in a loss and fewer are stranded in hand when it
ends — and the first V3 table duly reported *dead in hand lower in losses for 13
of 14 cards* and *conversion higher for 11 of them*. That is one fact about the
sample dressed as fourteen findings about fourteen cards.

The instrument now prints the raw split **and** a split against a control group of
won games **matched on turn count**, and only what survives the match is a claim
about a card. What survives:

| matchup | games | card | conversion, matched | reading |
| --- | --- | --- | --- | --- |
| Crustle Wall | 900 | **Hydrapple ex** | 27.9 win → **18.5 loss** | −9.4 |
| Crustle Wall | 900 | Hydrapple ex, *fodder* | 54.2 → **62.9** | +8.7 |
| Ogerpon Verde | 1 600 | **Hydrapple ex** | 52.6 → **44.2** | −8.4 |
| Ogerpon Verde | 1 600 | **Meganium** | 54.1 → **45.9** | −8.1 |
| real ladder | 106 | Hydrapple ex | 52.9 → 48.0 | −4.9 |
| real ladder | 106 | Meganium | 53.4 → 49.1 | −4.4 |

**The same card points the same way in all three sources.** At equal game length,
in the games we lose our Stage-2 win condition is played less and **discarded as
Ultra Ball fodder more** — 63 % of Hydrapple copies against Crustle Wall end as
someone else's cost. That is the starvation finding made concrete on a single
card: not "we misplay the wall", but "we pitch the thing that beats it".

Everything that moved the other way is the comeback package — Unfair Stamp
+28.3, Boss's Orders, Night Stretcher, Lana's Aid — and those cards are **supposed**
to be played more when behind. §6.4's caveat, doing its job.

---

## 4. B7 — do the simulated games and the real ones agree?

The block that makes this more than bookkeeping. 10 635 simulated games against
the generic bot versus 106 real ladder games, compared as a **ranking**, since
real games are shorter, harder and fewer so every level moves.

* **Conversion: Spearman +0.775.** The two censuses put the list in the same
  order. **The generic bot is not, in general, distorting which cards die.**
* **Dead in hand: Spearman +0.554**, and the disagreement is not spread out —
  it is two cards. **Unfair Stamp** falls 19 places (28.7 % dead simulated → 5.7 %
  real; conversion 23.5 → **72.1**) and **Fezandipiti ex** falls 15.

That is a clean, mechanical explanation rather than noise: **against the generic
bot we are almost never behind** (93.9 % winrate), and both of those cards only do
their job when behind. Against real opponents we lose 36 % of the time and they
convert three times as often.

**So the bot has been shaping the list, in one specific place: it systematically
prices the comeback cards as dead.** Any list decision about Unfair Stamp,
Fezandipiti ex or the recovery package taken from simulated numbers alone would
have been taken on a saturated sample. That is worth more than any single card
this census ranked.

The real ladder is also where the loss-side signal is: **68 wins / 38 losses,
64.2 %**, against 93.9 % simulated. A few hundred real games carry more loss-side
information than several thousand simulated ones, exactly as the plan argued.

---

## 5. Where the census still cannot see

Reported next to every run, never assumed away:

* **`NO_VISTA` is "deck or unrevealed prize"**, never "we never drew it". Games
  end with a mean of 1.01 prizes still face-down simulated, 2.61 real.
* **Face-down movement carries no cardId**, and it is now accounted for by
  transition rather than as one total: 6.00 per game is the prize deal (a known
  constant) and 0.08 is the opponent reading our hand. A third kind appearing is
  treated as a new blind spot and said out loud.
* **`DESCARTADA_EN_REVELADO` is 0.015 % of copies** simulated and 0 % on the real
  ladder — the copies that left without our seeing who discarded them.
* **Events after our seat's last observation are lost**, typically the final
  knock-out.
* **A low conversion is not a bad card.** A counter-stadium that sits in hand all
  game because the opponent never played a stadium did its job by being
  available. **This census ranks candidates for a human; it does not cut cards.**

---

## 6. What this leaves on the table, for a human to judge

Nothing here is applied. In descending order of how much evidence stands behind it:

1. **Hydrapple ex is being pitched in the games we lose.** Three independent
   sources, length-matched, same direction. The question is not whether the card
   is good but whether the Ultra Ball cost is being paid out of the win
   condition — that is a *discard-priority* question, and the discard planner
   already has [a plan of its own](discard-plan-2026-08.md).
2. **Xerosic's Machinations converts at 19.6 %** and is declined in 30 % of the
   copies we look at, the worst pair in the list.
3. **The five worst converters are declined ~30 % of the time in search.** Either
   the searches are right and those slots are wrong, or the search priorities are.
   The census cannot tell those apart; a human reading one search menu can.
4. **Unfair Stamp and Fezandipiti ex must not be judged on simulated numbers.**
   §4 is the reason.

---

## 7. Running it

```bash
# the pure core on a recorded game -- no engine, no network
python utils/card_census.py --episodes log_analisys/

# simulated, one matchup, seeded and reproducible
python utils/card_census.py --games 900 --opponent deck/real_opponents_500/crustle_wall_1.csv

# the whole corpus, budget by meta share (V1 + V2 + V3)
python utils/card_census.py --games 80 --opponents deck/real_opponents_500 --allocation peso

# real ladder games of our own, opponents labelled by archetype
python utils/download_player_games.py --player "Jose Coronel" --out-dir log --folder real_games
python utils/card_census.py --episodes log/real_games --opponents deck/real_opponents_500

# B7, from two saved row files -- costs no games
python utils/card_census.py --compare log/card_census/b4_corpus_rows.csv log/card_census/b6_real_rows.csv
```

`--out` writes one row per copy per game, so any view can be recomputed without
replaying anything. Long runs write into `log/card_census/`.

---

Next: [the playbook](playbook-vs-meta-2026-08-13.md) · [Instruments](instruments.md) · [Tools](tools.md) · [Testing](testing.md)
