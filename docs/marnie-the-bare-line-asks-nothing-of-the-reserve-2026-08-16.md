# …or their line is bare, and then the reserve is owed to nobody (Marnie, step 49)

*`records/registro_007_pasos_049_hasta_053.json` step 49, episode 93683313, turn
7 vs Marnie's Grimmsnarl ex — **won**, and the gust still went to the Morgrem.*

```text
US (seat 0, 5 prizes)                RIVAL (6 prizes)
active Teal Mask Ogerpon ex, 3G      active Marnie's Impidimp 70/70, 0e
bench  Bayleef, Meowth ex,           bench  Snorunt, Snorunt,
       Teal Mask Ogerpon ex, 2G             Morgrem 100/100, 0e,
                                            Munkidori 110/110, 1D,
                                            Munkidori 110/110, 0e
```

Boss's Orders was already played; this is the target select. The agent dragged
out the **Morgrem** and left the charged Munkidori — the body that moves 30
damage wherever it closes a knockout, reloaded every checkup by their own
Froslass — sitting on their bench.

## Why the engine ladder did not fire

`marnie_engine_first` asks `_marnie_bench_answers_the_grimmsnarl`, and here it
reads **False**: our reserve is a second Teal Mask Ogerpon ex holding two Grass,
**below its own attack cost**, so it prices at zero damage against a projected
320. With the flag down the whole engine ladder stands aside and the scores are
the plain stage tiers:

```text
Snorunt          3200
Snorunt          3200
Morgrem          9600   <- chosen: `tier_ko` 9000 + the line band
Munkidori 1D     6450
Munkidori 0e     3450
```

## The premise it was deferring to was never made

The bench question is owed to `ex_preevo_takes_priority`: that rung pays **19500**
for *"a two-prize ex attacker we cannot answer decides the game on its own"*, and
it is what the engine must not outbid while our active is the only body covering
the Stage 2.

But it demands a **charged** pre-evolution (`c.energy >= 1`), and on this board
their **whole line is at zero** — the Stage 2 is two steps and an attachment
away, and the Morgrem won on the generic stage tier alone. **There was no 19500
to protect.** A line carrying no energy is not the thing the reserve answers, so
it is not owed the question.

`_marnie_line_is_bare` reads it off the **same projection** the reserve question
uses (`_marnie_grimmsnarl_projection` inherits the energy of the most charged
body of the line — the real Grimmsnarl ex's own when it is on the board, the
floor *Punk Up* arrives with otherwise), so the two halves cannot drift apart.
No line in play is **not** bare: there is nothing to project and nothing to gust,
and the caller's other half already reads False.

It reads **their** line and not ours, and it lives inside the one
`marnie_engine_first` field — therefore inside one switch — for the same reason
the rest of it does: both chains and both consumers read it there.

Switch: `MARNIE_ENGINE_BARE_LINE_NEEDS_NO_RESERVE`. False restores exactly the
previous behaviour (the reserve question asked on every board), which is what
makes the two arms of its census one tree with one name rebound.

## The control, and it is the sibling record's board

Put a **single Darkness** on their Morgrem and the line stops being bare.
`ex_preevo_takes_priority` comes back with its 19500, our bench still does not
cover the Stage 2, and cutting the line is once again what keeps us alive — the
gust returns to the Morgrem.

## Measurement

| instrument | number |
| --- | --- |
| Replay of every stored log | 1 151 decisions, 986 with the Marnie flag, 8 gust menus → **1 flip**, the record's: Morgrem (idx 2) → **charged** Munkidori (idx 3) |
| Autopsy corpus, 25 opponents | 4 285 observations → **0 flips**. Leakage zero |
| Golden corpus | unmoved |
| Census, n = 200 vs `marnie_grimmsnarl` | 25 158 decisions, 134 gust menus, **46 with their line at zero energy**, **5 flips = 0.03/game** — **above** its 0.01 criterion. 2 are "line → ENGINE" (the record's sentence) and 3 are "engine → another engine": the rung arrives before the stage tier and reorders the engine itself, which is the ladder doing its job. **Zero knock-ons.** |
| Leakage, n = 100 vs `crustle_wall_1` | 13 272 decisions, **0** with the flag, **0** flips |
| Leakage, n = 60 vs `dragapult` | 6 322 decisions, **0** with the flag, **0** flips |
| **Gate, n = 4000 vs `marnie_grimmsnarl`** | candidate 3828/4000 = 95.70 % vs baseline 3828 → **+0.00 pp**, z +0.00, p 1.000, prizes **+0.002**. **CONTROL row +0.00 pp / prizes +0.000, exactly** |

The shape row is the one to read: **0.23 boards per game** reach a bare line
inside a gust menu, and one flip in nine of them. The reading is narrow because
the shape is — it needs the Marnie matchup, a Boss's Orders target menu, an
uncharged line **and** an engine body we can finish, all on the same turn.

The criterion was written before the file was run and not moved afterwards: at or
above **0.01 flips/game** against the Marnie lists and **0.00** on the list that
is not Marnie's. A rate an order of magnitude *above* it would have been the
alarming answer, not the good one — it would mean the reading is firing on boards
where their line is a real threat.

**The gate came back NEUTRAL, and read its control row first.** That row is
exactly zero — same seeds, same tree, the flag played against itself — so this
harness has no noise floor of its own and the candidate's `+0.002` prize delta is
the rules and nothing else. What the rules did is move the prize differential by
two thousandths of a game and **not one game's winner**: at 0.03 flips a game the
reading changed on the order of a hundred boards at this N, and none of them
changed who won.

That is the expected result rather than a verdict. The pressure this rule answers
is *Adrena-Brain* aiming 30 damage at the body that was going to survive, and the
bot on the other seat does not play that card the way a person does — **the
matchup the gate simulates is not the matchup the rule was written for**. Its
sibling measured −0.13 pp and was kept for the same reason. The noise floor
against this deck has been measured at **~1.5 points**, which no rate of this
order could ever resolve; the census is the number that says whether there was
anything to measure at all, and the switch is the whole revert.

## Files

* `ptcg/decision/boss_orders.py` — `_marnie_line_is_bare`, and the second way
  into `marnie_engine_first`.
* `ptcg/cards/ids.py` — `MARNIE_ENGINE_BARE_LINE_NEEDS_NO_RESERVE`.
* `tests/test_marnie_the_bare_line_asks_nothing_of_the_reserve.py` (12 tests,
  including the charged-line control) ·
  `tests/fixtures/marnie_step49_la_linea_pelada_no_le_debe_nada_a_la_reserva.json`
* `utils/census_the_bare_line_asks_nothing_of_the_reserve.py` ·
  `utils/gate_the_bare_line_asks_nothing_of_the_reserve.py`

---

This is the third page of one engine, and each half keeps its own switch:
[the engine goes before its line](marnie-the-engine-goes-before-its-line-2026-08-16.md)
(the reserve question itself) and [the gust reads the energy, not the
HP](marnie-the-gust-reads-the-energy-not-the-hp-2026-08-16.md) (the order inside
the ladder, and the jam chain).
