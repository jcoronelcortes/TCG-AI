# The night of 10 August — the first one against the meta that exists

**This one runs on its own.** It was launched at 23:01:48 on `HEAD 450c996` and
needs nobody. This document is what to read on waking.

---

## 0. Why this night is not the previous one again

`docs/night-plan-2026-08-10-b.md` posed six questions and answered one, at 5
games instead of 2 000. Its five unexecuted blocks are still the right
questions — but they were written against a corpus that no longer exists.

On 9 August at 21:11 the top-300 harvest was redone. The result is not "the same
decks, updated":

| | Before | Now |
|---|---:|---:|
| Top-300 decks with different contents | — | **267 of 300** |
| Unique lists | 98 | **88** |
| Mega Lopunny / Mega Froslass | 9 decks | **24** |
| Ogerpon Verde | 23 | 15 |
| Marnie Grimmsnarl | 115 | 108 |
| Crustle Wall | 32 | 30 |

And `deck/real_opponents/` — the corpus the oracle, the matrix and the radar all
consume — was **from 7 August**. Everything the previous night was going to
measure was pointing at retired lists.

---

## 1. What phase A already answered, before launching anything

### A1 · The corpus, rebuilt

`deck/real_opponents_2026-08-07/` holds the old one. The new one is **87
pilotable lists out of 88**, and the share of the meta the harness can measure is
**99.7%**. A single list (`otro_ns_zoroark_ex_2`) will not start with the bot.

Four lists in the corpus are **near-copies of ours** (`festival_lead_4` shares
all 60 cards). The bot pilots OUR engine there, badly, so its winrate reads high
and it is not a matchup. They are flagged in `pesos.csv`.

### A2 · The Crustle finding can no longer be reproduced — and that is an answer

`utils/corpus_bridge.py`, written for this, matches by **content** and not by
name, because `real_opponents.py` numbers by meta weight and therefore
`crustle_wall_6` **is not a deck, it is a rank**.

| | |
|---|---:|
| Old lists identical in the new corpus | 45 |
| Drifted (≤12 cards) | 37 |
| **Gone from the top 300** | **15** |
| New lists nobody has ever measured | **32** |

**The `crustle_wall_6` that measured 54.5% is among the 15.** The closest list in
the new meta is **32 cards away**, and the name `crustle_wall_6` has landed on a
deck that has never played a game against us. Six of the sixteen new
`crustle_wall` lists are ones nobody has measured.

That is why the night carries a **B2b** block that was in no plan: measure the
dead deck at n=1 000 **from the backup**, which is the last chance to know
whether the 54.5% was real or the ±7 of 200 games. One of the two answers
transfers to the six new lists and the other does not.

### A3 · The new meta, and who rules at the top

`log/noche_2026-08-10-c/A4_meta.md`. The headline is not the presence, it is the
band:

> **Mega Lopunny / Mega Froslass is 26.7% of positions 1–30** while being only
> 8% of the field. It is the archetype that wins, not the one most played.

And in the corpus it is **a single list**: the 24 decks are identical card for
card. One file is worth 8% of the meta and a quarter of the top 30.

### A4 · A red test the harvest brought in

`tests/test_op_scaling_attacks.py::test_no_opposing_attack_scales_without_being_read`
now fails, and **no code change broke it**:

```text
Tapu Koko ex — Linked Lightning (458): 60 base, +20 for each of their
Pokemon on the bench. Nobody reads it.
```

Card 329 is in **1 deck of 408 now and in 0 before** the harvest
(`mazo_278.csv`, Mega Kangaskhan, position 278). The test is exactly the guard
written for this: a new deck brings a scaling attack and the agent does not see
it; it does not crash, it walks into the hit.

**Not touched tonight.** Putting it into `OP_SCALING_DAMAGE` is a change to the
agent, and a rule landing halfway through the night means the blocks before and
after measured two different agents. At 1 deck in 408 there is no hurry. A
decision for tomorrow: is the number **read** off the board (yes: their bench is
visible), or would we be guessing?

---

## 2. What is running

```text
log/noche_2026-08-10-c/RESUMEN.txt     ← start here
log/noche_10ago_c.txt                  ← the trace, with timestamps
```

| | The question it answers | Size | Estimate |
|---|---|---|---:|
| **B1a** | Does the oracle's residue exist against the lists people play now? | 87 lists × 300 games | ~60 min |
| **B1b** | The five worst **by rate**, dumped as fixtures | 5 × 1 000, with `--dump` | ~12 min |
| **B2** | Is there a `crustle_wall` that breaks away, with the whole family at ±3? | 16 Crustle + 4 Lucario × 1 000 | ~33 min |
| **B2b** | The **retired** `crustle_wall_6`: real 54.5% or noise? | 3 × 1 000, from the backup | ~5 min |
| **B3** | The invariants at ten times the sample, every violation dumped | 20 000 games | ~40 min |
| **B4** | The order-dependent decisions, dumped for triage | 2 000 games | ~6 min |
| **B5** | The properties at ten times the budget | 200 000 examples | ~24 min |
| **B6** | The collision radar **over the real lists** — for the first time | 87 lists × 400 | ~81 min |
| **B7** | How are we doing against the weighted meta? It does not exist for these lists | 87 × 300, with `--weights` | ~44 min |
| | | | **~4 h 30** |

Each block writes its own log and **none of them can stop the night**.

---

## 3. What to look at on waking, in this order

**First `RESUMEN.txt`**, which fits on one screen. `rc != 0` **in B4 is not a
failure**: the permutation probe reports through its exit code, and calling a
tool's findings a failure is how people are taught to ignore the red.

> **B1a has already finished (57m 17s, rc=0) and it changes how everything else
> reads.** **2 664 findings over 128 338 attacks judged: 2.08%**, against the
> 1.39–1.42% of the synthetic decks. Not an order of magnitude, so the decks
> loaded correctly.
>
> What matters is the shape. By family, `crustle_wall` leads with **4.58% mean
> across sixteen lists** — not one deck breaking away, the whole family — with
> `great_tusk_crustle`, the other Crustle shell, right behind.
> `marnie_grimmsnarl`, which is 36% of the meta, sits at **0.11%**.
>
> **And the rate alone does not separate a dangerous residue from a harmless
> one: the sign does.** A positive drift is the agent predicting MORE damage
> than the engine resolves — it believes it knocks out, attacks into a body that
> survives, and hands over the turn. `crustle_wall` is **90% positive, median
> +40**. `festival_lead` has a comparable rate at **44% positive**, which is why
> its residue has never predicted losing.
>
> Two cautions: the optimistic bias is **general** (nearly every family between
> 60% and 90%); what is singular about Crustle is having it almost pure AND the
> highest rate at the same time. And the drift is summarised by **median**, not
> by mode — the mode said "−70" next to "67% positive".
>
> **Consequence for B1b:** it picks the five worst **by rate**, a criterion
> fixed before anyone knew the sign was what mattered, and three of its five
> slots go to `festival_lead`. Hence a queued **B8** that starts when the night
> ends and dumps `crustle_wall_11`, `crustle_wall_12` and
> `great_tusk_crustle_1`, which are positive drift and B1b does not reach.

| Log | What to look for | What we already know |
|---|---|---|
| `B1a.log` | ~~the rate per list~~ **the sign per family** | See the box above: done and read |
| `B1b.log` + `violaciones_oraculo/` | one JSON per finding, observation included | Each is a fixture ready to be pinned. **Detecting is not executing**: reproducing the board is another job. The three `festival_lead` entries here are the harmless family |
| `B8.log` | the dumps with **positive** drift | Supplementary, starts on its own when the night ends |
| `B2.log` | whether any `crustle_wall` breaks away from its family | The deck that was breaking away is gone. The question is whether another takes the slot, or whether it belonged to that one deck |
| `B2b.log` | `crustle_wall_6` from the backup at n=1 000 (±3) | At 200 games it read 54.5% [47.6–61.3]. If it rises towards 76%, it was the ±7 and there was nothing there |
| `B3.log` | `DECK_BELIEF`, `ILLEGAL_INDEX`, `END_EMPTY_BENCH`, `ENERGY_CAP`, `DOUBLE_ATTACH` | All five at **0** over 2 000 games. `STALE_FLAG`/`STALE_READ` come out in the thousands and **are not defects** |
| `B4.log` + `permutacion/` | not how many, but **how many are `ATTACK` vs `RETREAT`** | 0.67% is the known level. A `CARD` vs `CARD` tie is cosmetic; an attack-or-retreat fork decided by menu position is not |
| `B5.log` | any falsification | The most valuable artefact that can come out, because it arrives **minimised** |
| `B6.log` | "resolution well below the median" | **First time the radar looks at real lists.** Against the synthetic ones it was already flagging `juega_supporter` on `festival_lead` |
| `B7.log` | the weighted figure against the new meta | There is nothing to compare it with: it is this corpus's baseline. The 4 near-copies inflate it; `pesos.csv` flags them |

---

## 4. The rule that is never skipped

**No finding from tonight becomes a change to the agent without being
measured.** In two days, four detectors in this repository reported their own
bugs as defects of the agent: the oracle three times (16 764 non-existent
findings in v1), the monitor twice, the mutation gate twice more.

Tonight's version of it has already claimed a scalp. The script's dry run
revealed that `listas()` used `find | xargs basename`, that `xargs` splits on
spaces, that this project lives under `VS Proyectos/TCG AI`, and that the census
therefore happily measured **261 decks instead of 87** — two of them called `VS`
and `TCG` — for seven minutes, **with exit code 0 and a complete log**. A number
that looked exactly like a measurement.

And if a finding turns out to be real: **measure the frequency before the
winrate.** The 9 August fix corrected an impossible belief on 25% of boards and
moved 2 decisions in 50 955; at that frequency a winrate gate can only return
NEUTRAL by construction.

---

## 5. What was done while it ran

**T3.1 · The `opponent_bot.py` suite** — done, commit `6165426`. It was "the
first thing tomorrow" in the previous plan because every matchup finding rests
on that bot. 22 tests over the half of its policy nobody had pinned: menu order,
evolution by stage, attacking by damage rather than by position, and the *else*
branch of every rule whose *then* branch was already pinned.

All 22 passed first time, which is when a test deserves the least trust, so each
policy was broken in memory and re-run: **seven of seven fail when their rule is
broken**.

Out of that came a correction to the bot's own docstring, written as a test:
**×2 weakness cannot change which attack is chosen** — both attacks of the same
attacker share its type, so the ×2 scales all of them equally. Where it does
decide is the **gust target**, and that is pinned separately.

---

## 6. What the night does NOT do — the hand work that remains

From `docs/testing-plan-2026-08.md`, reordered by what tonight makes urgent:

1. **T1.3 · Boundary pairs** from `decision_grid.boundaries()`: kills the
   `boundary: 1 -> 2` and `GtE -> Gt` mutant families by construction.
2. **T1.2 · Reason assertions** on the 30 highest-value tests (the Boss's gust
   family, promotion, retreat).
3. **T3.4 · Grow and freeze the golden corpus**: CI still skips the comparison,
   and the flip-diff is the project's most useful review artefact.
4. **T3.3 · SPRT** for the A/B, and **T3.2 · a second opponent policy**.
5. **T4.2 · Hygiene** and a rule → test-file index.
6. **The dead `meganium_active` parameter** in `_our_effective_damage`, which the
   mutation gate flagged as an equivalent mutant.

And the two strategy items memory had marked PENDING, neither of which is
measurement:

- **The projector for "which body, when benched, raises MY damage"** (the
  Dipplin / Do the Wave case: the agent spent a 2-prize Meowth ex where the
  Ogerpon alone already gave the exact knockout). It affects every attacker
  whose damage counts bodies.
- **The opponent's tempo**: `_op_disruption_belief` ignores its second parameter
  and nobody looks at their discard between turns, which is where "their hand is
  stuck" comes from.

---

## 7. The success criterion

The usual one: **a list of reproducible findings and detectors that still
validate themselves**, with **zero lines changed in `main.py`**.

And one specific to tonight. The previous night's question was which of three
`crustle_wall` is, and **the bridge has already answered "none of the three"**:
the deck left the meta. What has to be writable by morning, in one sentence, is
whether any of the sixteen new lists inherits the hole (B2 would say so), or
whether that 54.5% was the ±7 of a short sample (B2b would say so) — in which
case the project has spent two nights chasing noise, which is also a result, and
one of the cheap ones.
