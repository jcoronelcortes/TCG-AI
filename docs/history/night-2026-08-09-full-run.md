# The first complete run of the pipeline — 9 August, 14:11–15:49

`python utils/nightly.py --full --since 69ad2e3`, on `7bb0bb6`. **1 h 38 min**
(estimated 1 h 35). 28 stages, **zero FAILED, zero INVALID**, exit code 0.

This is the first time the whole apparatus built on 8 and 9 August ran together
and at full size. This document is what it produced.

---

## 1. The gates: all green

| | |
|---|---|
| Suite | 1 878 tests, 16 s |
| Architecture lint | no violations |
| Local golden corpus | 50 records, no flips |
| Coverage floors | 37 modules, **none below** (26 min) |
| **Mutation gate** | over the whole of the day's agent diff: **zero survivors** |

The mutation gate passing at zero over the lines written today is the hardest of
the five numbers to get, and it was not passing this morning: it stood at one
survivor inside the prize fix itself.

---

## 2. The differential oracle: the residue REPRODUCES

19 decks × 2 000 games, **165 104 attacks judged**.

| | last night (v4) | now | Δ |
|---|---:|---:|---:|
| Findings | 2 351 | **2 303** | −48 |
| Rate over attacks judged | 1.42% | **1.39%** | −0.03 pts |

No per-deck difference exceeds what the variance between unseeded runs moves on
its own (the largest is −36 on `archaludon`, which has 101). **That is the
point:** the residue was not the noise of one run. It is a stable number,
measured twice independently, and it is **still unexplained**.

Where it lives, and it has not moved:

| Deck | Findings | % of total |
|---|---:|---:|
| `festival_lead` | 885 | 38% |
| `crustle_great_tusk_nz` | 356 | 15% |
| `crustle_kangaskhan` | 285 | 12% |
| `jellicent_lock` | 170 | 7% |
| the other 15 | 607 | 26% |

---

## 3. The invariant monitor: zero on everything objective

2 000 games. The only non-zero counters are `STALE_FLAG` (14 851) and
`STALE_READ` (2 490), which are **documented as non-defects** in the file
itself: 743 reads were audited and the three recorded promises are guarded at
their consumption points.

What matters is what does **not** come out, over 2 000 complete games:

    DECK_BELIEF 0 · ILLEGAL_INDEX 0 · END_EMPTY_BENCH 0
    ENERGY_CAP 0 · DOUBLE_ATTACH 0 · AGENT_RAISED 0

This morning's `_identify_prizes` fix holds at scale: zero impossible beliefs
about the prizes across 2 000 games.

---

## 4. Permutation and properties

- **0.67% of decisions are order-dependent** over **253 197 decisions**. The
  known level was 0.56–0.77% measured over 40–150 games; now it is a solid
  number rather than a sample.
- **20 000 examples** of hypothesis, all 6 properties green in 2 min 53 s.

---

## 5. THE FINDING OF THE NIGHT: the Crustle family

The matchup matrix — 98 real leaderboard lists × 200 games — by archetype:

| Family | Lists | Mean winrate | Worst |
|---|---:|---:|---:|
| **`crustle_wall`** | **18** | **76.6%** | **54.5%** |
| `mega_lucario` | 5 | 87.0% | 84.0% |
| `mega_starmie` | 3 | 89.5% | 87.5% |
| `ogerpon_verde` | 11 | 90.7% | 84.0% |
| `alakazam` | 10 | 95.8% | 93.5% |
| … the other 12 archetypes | | 94–99% | |
| **Overall** | **97** | **91.4%** | |

`crustle_wall` is **10 points below** the next worst family and **15 below** the
mean. With 18 lists at 200 games each it is not one odd list: it is the
archetype.

**And two independent detectors point at the same place.** The two largest
oracle residues after `festival_lead` are the two Crustle decks (641 findings
between them, 28% of the total). The oracle says "the agent gets its damage
projection wrong against these decks" and the matrix says "and against these
decks it wins much less". Agreement does not prove it, but it is the first time
two tools built for different things have named the same archetype.

**An honest caveat:** the matrix measures against the generic bot. 54.5% against
that bot is not 54.5% against a person. What *is* comparable is the GAP: the 97
lists are measured the same way, and this family is 15 points below.

---

## 6. The morning's list

1. **The oracle's 641 findings against the two Crustle decks**, crossed with the
   54–84% from the matrix. It is the only place where two detectors agree, and
   there are dumps to reproduce each one.
2. **`festival_lead`, 885 findings, 38%**, measured the same way twice. Still
   unexplained since last night.
3. Nothing else. The gates are green, the objective invariants are at zero and
   the mutation gate is at zero: **there is no third thing to fix**, and saying
   so is worth as much as the first two.

## What I would NOT do

- **Do not touch the agent over the oracle's residue without reproducing a
  concrete case first.** 2 303 findings are not 2 303 defects: last night the
  same detector had three versions, and the first two reported thousands of
  things that did not exist.
- **Do not chase the 0.67% of permutation.** It is inside its historical band,
  and this is the largest measurement ever made of it.
- **Do not add stages to the pipeline.** What is missing is not a stage — it is
  reading the two items above.
