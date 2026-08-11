# The second night of 9–10 August — the three questions the full run left open

**You are the one who runs it.** This document is the task, not a report.

`docs/night-plan-2026-08-10.md` was the full run, and it got spent during the
day: `utils/nightly.py --full` finished at 15:52 with 28 stages, 1 h 38 min,
zero FAILED and zero INVALID. That night is done. What follows is not repeating
it bigger: it is **what that run asked and could not answer with the sample it
had**.

---

## 0. What it left open, in three sentences

1. **The oracle's residue reproduces and is still unexplained.** 2 303 findings
   over 165 104 attacks judged (1.39%), against 2 351 and 1.42% the night
   before. Measured twice, stable — and measured **only against the 19 synthetic
   decks** in `deck/opponents`.
2. **`crustle_wall` is the weak family.** 18 real lists, mean 76.6%, worst
   54.5%, against an overall mean of 91.4% and no other family below 87%. And
   `crustle_wall_6`, at 54.5%, is **18 points below its own family**, not just
   below the rest of the meta.
3. **1 698 order-dependent decisions (0.67%)** that nobody has looked at one by
   one. It is the only stage that came back with FINDINGS, and its dump has
   never been triaged.

**And a cross-reading worth doing before launching anything.** `festival_lead`
has the **largest** oracle residue — 885 findings, 5.2% of its judged attacks,
almost four times the global rate — and at the same time wins **97.1%** of its
matchups. The residue on its own **does not predict losing**. `crustle_wall` is
the only place where both instruments point at once, which is why it is
tonight's target and `festival_lead` is not.

---

## 1. Before launching — 3 minutes, and the first is not optional

**The tree is dirty right now and I have not touched it.** At 16:56 there was a
half-written rule:

```text
 M ptcg/cards/ids.py            SCORE_EVO_CONDITION_UNLOCK = 34000
 M ptcg/turn/options/evolve.py  the evolution that wakes the active
```

There is another session working in the same tree (`tcg-ai-09`). **Decide what
the night measures before starting it**: commit the rule, or set it aside with
`git stash`. Whatever is in the tree at launch time is what gets measured for
two and a half hours, and a rule that lands halfway means B1 and B2 measured
**two different agents**, and neither of their numbers compares with the other.

This is not the danger of the other night — this run does not execute the
mutation gate, so nobody is going to rewrite files on disk. It is the worse
danger of the numbers coming out fine and nobody knowing what they are of.

With the tree decided:

```bash
cd "/Users/jcoronel/Desktop/VS Proyectos/TCG AI"
git status --short           # let it say what you want it to say
git log --oneline -1         # note the hash: everything is measured against it
python utils/nightly.py --quick --since HEAD~1      # ~40 s
```

The `--quick` has to finish with no FAILED and **no INVALID**. An INVALID means
a detector cannot validate itself, and then its numbers tonight would be worth
nothing.

---

## 2. The command for the night

```bash
bash utils/noche_2026-08-10.sh 2>&1 | tee log/noche_10ago_b.txt
```

Everything it produces lives under `log/noche_2026-08-10/`: one log per block, a
`RESUMEN.txt` with the exit code and elapsed time of each, and the dumps. No
block can stop the night — one that fails leaves its log and the next one
starts.

Levers, in case you want a shorter night or to relaunch only one part:

```bash
SOLO=B2,B3 bash utils/noche_2026-08-10.sh          # only those blocks
CENSO_GAMES=150 MONITOR_GAMES=8000 bash utils/...  # half a night
PY=.venv/bin/python bash utils/...                 # a different interpreter
```

---

## 3. The six blocks and what each one answers

| | The question it answers | Size | Time |
|---|---|---|---:|
| **B1a** | Does the 1.4% residue exist the same way against the decks people **actually** play? | 98 real decks × 300 games | ~45 min |
| **B1b** | The five worst **by rate**, dumped as fixtures | 5 × 1 000, with `--dump` | ~7 min |
| **B2** | Is the 54.5% real, or is it the ±7 that 200 games carry? | 18 `crustle_wall` + 5 `mega_lucario` × 1 000 | ~18 min |
| **B3** | The invariants at ten times the sample, with every violation dumped | 20 000 games | ~32 min |
| **B4** | The 1 698 order-dependent decisions, dumped for triage | 2 000 games | ~6 min |
| **B5** | The properties at ten times the budget | 200 000 examples | ~30 min |
| **B6** | The collision radar — the tool built for exactly B2's question | 19 synthetic × 400 | ~12 min |
| | | | **~2 h 30** |

The times are a linear extrapolation from today's run (0.07 s per oracle game,
0.094 s per monitor game, 0.17 s per permutation game), which is linear and
measured. **What is verified is that all six launch**: I have run the oracle at
3 games against `crustle_wall_6`, the probe at 5, the radar at 2 and the matrix
at 2 over the exact 23 lists of B2. All four answered. What is not verified is
the time at full size.

**Why B1b picks by rate and not by number of findings:** a deck that judges
twice as many attacks reports twice as many findings at the same defect level.
`festival_lead` leads in absolute terms (885) and in rate too (5.2%); but across
the census of 98, that distinction is what decides which five decks the dump
budget is spent on.

**Why B2 carries a control group:** `mega_lucario` is the next weakest family
(87.0%). Without it, a narrower Crustle figure cannot be told apart from
everything coming out narrower.

---

## 4. What to look at on waking, in this order

**First `log/noche_2026-08-10/RESUMEN.txt`**, which fits on one screen.
`rc != 0` **in B4 is not a failure**: the permutation probe reports through its
exit code, and calling a tool's findings a failure is how people are taught to
ignore a red pipeline.

Then, in order of what a defect of each class costs:

| Log | What to look for | What we already know |
|---|---|---|
| `B1a.log` | the rate per real deck | Expected overall ≈1.4%. **If it comes back an order of magnitude different, suspect the deck loading before the agent**: these 98 lists have never been through the oracle |
| `B1b.log` + `violaciones_oraculo/` | one JSON per finding, observation included | Each one is a fixture ready to be pinned. Detecting is not executing: reproducing the board is another job |
| `B2.log` | `crustle_wall_6` at n=1 000 (±3) | At 200 games it read 54.5% [47.6–61.3]. The question is whether it stays alone, or takes the rest of the family down with it |
| `B3.log` | `DECK_BELIEF`, `ILLEGAL_INDEX`, `END_EMPTY_BENCH`, `ENERGY_CAP`, `DOUBLE_ATTACH` | All five at **0** over 2 000 games today. `STALE_FLAG`/`STALE_READ` come out in the thousands and **are not defects** |
| `B4.log` + `permutacion/` | not how many, but **how many are `ATTACK` vs `RETREAT`** | 0.67% is the known level. A `CARD` vs `CARD` tie is cosmetic; an attack-or-retreat fork decided by menu position is not |
| `B5.log` | any falsification | It is the most valuable artefact the night can produce, because it arrives **minimised** |
| `B6.log` | "resolution well below the median" | Today, at a noise level of 2 games, it was already flagging `juega_supporter` on `festival_lead` at 23.5% against a median of 50% |

---

## 5. The rule that is never skipped

**No finding from tonight becomes a change to the agent without being
measured.** In two days, **four** detectors in this repository reported their own
bugs as defects of the agent: the oracle three times (16 764 non-existent
findings in v1), the monitor twice, the mutation gate twice more. The only thing
that has worked is the self-test that aborts the run.

Tonight's version of it: **B1a is the first time the oracle sees the real
lists.** The script launches one invocation per deck rather than a single one
with all of them, precisely so that each runs its own self-test. A census whose
detector cannot demonstrate it still works is the most deceptive result there
is.

And if a finding turns out to be real: **measure the frequency before the
winrate.** The 9 August fix corrected an impossible belief on 25% of boards and
moved **2 decisions in 50 955**; at that frequency, a winrate gate can only
return NEUTRAL by construction.

---

## 6. What the night does NOT do — the hand work that remains

From `docs/testing-plan-2026-08.md`, ordered by what tonight makes urgent:

1. **T3.1 · A suite for `opponent_bot.py`** — 1–2 days, and tonight promotes it
   to the first thing tomorrow. **The whole Crustle finding rests on a bot with
   13 tests, and all 13 are about the ability engine.** Its gust target, its
   attachment priority and its retreat condition are unpinned, and its coverage
   is not even measured (`utils/` is not in `coverage.json`). If the bot plays
   Crustle badly, the 54.5% is a measurement **of the bot**. The three possible
   outcomes — a defect of the agent, a defect of the bot, or simply a hard
   matchup — can only be told apart once this is done.
2. **T1.3 · Boundary pairs** from `decision_grid.boundaries()`: kills the
   `boundary: 1 -> 2` and `GtE -> Gt` mutant families by construction.
3. **T1.2 · Reason assertions** on the 30 highest-value tests (the Boss's gust
   family, promotion, retreat).
4. **T3.4 · Grow and freeze the golden corpus**: there are 50 local records, but
   CI still skips the comparison. The flip-diff is the project's most useful
   review artefact and on a clean checkout it does not yet exist.
5. **T3.3 · SPRT** for the A/B, and **T3.2 · a second opponent policy**.
6. **T4.2 · Hygiene** and a rule → test-file index.

And two corrections to the plan document itself, which is already out of date:

- **T0.3 says "not yet in CI" and that is false**: the `mutation` job exists in
  `.github/workflows/gates.yml`, with `--self-test-only` before trusting its
  zero. What actually remains is the dead `meganium_active` parameter.
- **A 15-minute job that B6 is crying out for**: `utils/collision_radar.py` has
  `deck/opponents` hard-wired at line 344, so **it cannot look at
  `crustle_wall_6`**. Giving it an `--opponents` like the one `matchup_matrix.py`
  already has turns the radar into the tool that answers tonight's question
  against the real lists.

---

## 7. The success criterion

The same as last night: **a list of reproducible findings and detectors that
still validate themselves**, with **zero lines changed in `main.py`**.

And one specific to tonight: by morning it has to be possible to write, in one
sentence, which of the three `crustle_wall` is — **a defect of the agent** (B1a
and B1b would say so, with the oracle's rate concentrated on those lists), **a
defect of the bot** (B2 would say so if the 54.5% holds but B6's radar finds no
situation that collapses) or **just a hard matchup** (B2 would say so if at
n=1 000 the family rises towards the mean and the 54.5% was the ±7).

A night that answers "none of the three, T3.1 is needed first" is also a result.
The failure mode this project knows by name is *a number nobody read*.
