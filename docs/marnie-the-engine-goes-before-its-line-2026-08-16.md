# The engine goes before its line (Marnie's Grimmsnarl ex, step 110)

*`registro_008` step 110, episode 93525290, turn 8 vs Marnie's Grimmsnarl ex —
**lost**. Boss's Orders already played; the agent gusted the **Morgrem** and
knocked it out. `ex_preevo_takes_priority` lifts the high link of an ex line to
**19500** (12000 of `tier_ko` plus the step) against the Munkidori's **6450**.
They rebuilt the line and won.*

## The premise of that rung was false

The rung is paid for by *"a two-prize ex attacker we cannot answer"*. Marnie's
Grimmsnarl ex is 320 HP and **weak to Grass** (`weakness == GRASS` in the card
table): *Myriad Leaf Shower* doubles, and the Teal Mask Ogerpon ex **on our own
bench** with four Grass reads 150–210 base → **300–420** against an effective
300 (their own *Freezing Shroud* takes 20 off any body with an Ability, and
*Punk Up* is an Ability).

**The answer to the Stage 2 was already parked.** What is never answered is the
two abilities no evolution step controls:

* **Froslass** — *Freezing Shroud*, 20 a round to **our whole board**, because
  every body of ours has an Ability.
* **Munkidori** — *Adrena-Brain*, moves 30 counters to wherever it closes a
  knockout, with the ammunition reloaded every checkup by their own Froslass.

Munkidori is the worse of the two **because it aims**. The drip is arithmetic
you can plan around; the movement is what turns a body we had counted as a
survivor into a corpse.

## The rule

`marnie_the_engine_before_the_line`, in `ptcg/decision/boss_orders.py`:

* **The condition** `marnie_engine_first`: the Marnie matchup
  (`op_is_marnie_deck`, new and **sticky**) **and** a body on **our bench** that
  knocks out the Grimmsnarl ex. The bench and not the whole board is the only
  reading that means anything: an answer that has to be in the active spot to
  exist is not a reserve. With the active as the only answer, the line rule
  keeps its 19500 and its reason — they can knock the active out, and then
  nobody covers it.
* **With it:** `ex_preevo_takes_priority` **stands down** on the Marnie line
  (the Morgrem falls to its plain tier, 12700) and Munkidori > Froslass >
  Snorunt rise to `15000 + rank`.
* **`max` and not `+`:** between the three engine bodies the order has to be
  **absolute**. Summed, the 3000 per tier between a Stage 1 Froslass and a Basic
  Munkidori eats any spacing that fits in the band.
* **15000 is chosen to fit** between the ceiling of a one-prize knockout (12700)
  and the floor of a two-prize one (21000, tier 7): if the Grimmsnarl ex is on
  their bench and we can finish it, **two prizes still rule**. It also sits below
  `under_denial_the_trap...` (+40000) and `gust_wins_the_game` (+100000).
* **The Grimmsnarl projection** (`_ProjectedBody`): the real body if it has
  already evolved; otherwise 320 HP carrying the energy of the most charged body
  of the line. That is the **conservative floor** — *Punk Up* brings up to five
  energies, and more energy of theirs is *more* damage from our Ogerpon, never
  less.
* **`can_ko` filters every rung** by what the whole file repeats — a gust that
  takes no prize is a free retreat we hand them — so a Munkidori we cannot
  finish yields to the Froslass we can.
* **The switch** `MARNIE_ENGINE_BEFORE_THE_LINE` sits at a **single point** in
  `_ctx_gust_target`, because the two halves are one decision and an arm moving
  only one of them would measure a board nobody plays.

## Measurement

| instrument | number |
| --- | --- |
| Golden corpus | **1 flip**, this step (accepted with `--update`) |
| `registro_008` p136 | the other game lost to this list: the same flip |
| Census, n = 300 vs marnie | **0.02 flips/game**, and **6 of 7** are the exact sentence |
| Leakage | **0 of 39 781** decisions vs `crustle_wall_1` |
| `records/marnie/` | 0 flips in 296 decisions across 3 complete games |
| Gate, n = 1 500 | candidate **−0.13 pp** (z −0.18, p 0.857); **control +0.00 pp exactly** |

The control at exactly zero says the harness has no noise of its own, so that
−0.13 pp is **two games of 1 500** — and that is all it can be: at 0.02
flips/game the reading flipped on the order of thirty boards, and two of them
falling the wrong way is what a handful of flips in any direction looks like.
The row neither supports nor condemns.

**It is adopted on the census and on the two records that motivate it, not on the
scoreboard** — and the bot in the other seat does not play *Adrena-Brain* like a
person, so the matchup the gate simulates is not the matchup the rule was
written for.

## A side finding, **not** adopted

`Snorunt` (103, 60 HP) is **not the print these lists play**: they run **860**
(70 HP), which is the `preEvolution` of both Froslass in the record.
`Snorunt_Ice` and `SNORUNT_IDS` are added, but used **only** in the new ladder —
the old consumers (`HIGH_PRIORITY_BENCH_TARGETS`, `_gust_generic_tiers`,
`EX_PREEVO_IDS`) stay blind to 860, and widening them is a behaviour change with
no measurement behind it.

## Files

* `ptcg/decision/boss_orders.py` — the ladder, the projection and the condition.
* `ptcg/cards/ids.py` — `MARNIE_ENGINE_*`, `Snorunt_Ice`, `SNORUNT_IDS`.
* `ptcg/state/agent_state.py` — `op_is_marnie_deck`, sticky.
* `tests/test_marnie_the_engine_before_the_line.py` ·
  `tests/fixtures/marnie_step110_el_motor_antes_que_la_linea.json`
* `utils/census_marnie_the_engine_before_the_line.py` ·
  `utils/gate_marnie_the_engine_before_the_line.py`

---

Two later pages continue this one, and both hang off the same switch:
[the gust reads the energy, not the
HP](marnie-the-gust-reads-the-energy-not-the-hp-2026-08-16.md) orders the ladder
inside itself and carries it into the **jam** chain, and [a bare line is owed no
reserve](marnie-the-bare-line-asks-nothing-of-the-reserve-2026-08-16.md) is the
second way into `marnie_engine_first`.
