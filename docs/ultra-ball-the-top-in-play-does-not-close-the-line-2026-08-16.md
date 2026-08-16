# The top in play does not close the line — measured and **not** adopted (Marnie, step 72)

*`records/registro_007` step 72, episode 93493222 vs Marnie — **won**. Turn 7,
our Forest of Vitality down, the bench **full**, a Hydrapple ex active and a
Dipplin on the bench holding two effective energies with the second Hydrapple ex
still in the deck. The menu was four things: two Ultra Ball, the attack, and
pass. It attacked.*

This page records a candidate that was **written, instrumented, measured and
shipped switched off**. It is here because the verdict is the useful part: the
reading is sound, the winrate says no, and the number it produced points
somewhere else entirely.

## What the trace said

Both Ultra Ball scored **−100** (`SCORE_CANCEL`), and *not* because of their
price: every `_ub_cancel_*` returned False. `_eval_ub_best_target` returned
**0** — no target at all.

The reason is two `if`s in `ptcg/decision/ultra_ball.py`:

```python
if not meganium_in_play: ...   # the Chikorita → Bayleef → Meganium ladder
if not has_hydrapple: ...      # the Applin → Dipplin → Hydrapple ex ladder
```

With the bench full, **an evolution is the only thing an Ultra Ball can buy** —
there is no seat left for a new Basic. And the guard does not close only the
*top* of the line: it wraps the whole ladder, so it also switches off the
Dipplin an Applin is waiting for while a Hydrapple ex happens to be somewhere
else on the board.

## The candidate, written and switched off

`TOP_IN_PLAY_DOES_NOT_CLOSE_THE_LINE` ships **`False`**: the tree behaves
exactly as before (3 064 tests green, golden corpus unmoved, lint clean,
`test_submission` green).

Behind it, `_evolution_ladders(mega_open, hydra_open)` extracts the two ladders
verbatim and asks them **twice** — the second pass, for the line whose top is
already on the board, only if the first pass left the Ultra Ball with no target
whatsoever. The FETCH menu reads the same switch through
`_line_closed_by_its_top()`, so the two menus cannot buy the Item for one target
and then spend it on another.

## Measurement

| instrument | number |
| --- | --- |
| Frozen corpus, `census_the_top_in_play_does_not_close_the_line.py` | 51 valuations of the shape → **32 dead** → **29 of those with a full bench** |
| Self-play, n = 2 000 | **0.09–0.16 turns per game** in which an Ultra Ball dies to the guard — 2× to 4× the censuses this repo has closed *below* their criterion |
| Two-arm gate, n = 1 000 × 4 lists | reading **−0.70 pp** (z = −1.91, p = 0.057) against a `--control` arm — the same code twice — of **+0.25 pp** |
| Curated boards | **eleven** disagree, and all eleven are the same menu |

The census unit is **distinct turns, not valuations**: the step-72 board is
priced eleven times inside the same turn, and counting valuations would have
inflated the exposure by an order of magnitude. The census also neutralises the
switch on itself, so it always measures the *exposure* and never the
post-fix world.

The gate row does not clear its own floor, but the **sign does not dance the way
the control's does**: −1.20 / −1.20 / 0.00 / −0.40 with the reading, against a
control that came back positive on three of the four lists. Prizes agree
(−0.08 and −0.09 on the two that lose).

## What this work does establish, and it is not the sentence

It is the **band**. A live Ultra Ball is worth 10 000–12 500 — *above* plays
that take a prize and score less (`_wall_ko_promote` = 6 700). The eleven broken
boards are all exactly that: the Ultra Ball put in front of something that was
already taking the turn.

While that inversion is there, opening the guard only moves the Item forward at
the expense of the play that was winning. **That is where to look next**, and
this page exists so nobody re-opens the guard blind.

## Files

* `ptcg/decision/ultra_ball.py` — `_evolution_ladders`, `_line_closed_by_its_top`,
  and the switch with the record in its comment.
* `ptcg/turn/options/card.py` — the FETCH menu reading the same switch.
* `utils/census_the_top_in_play_does_not_close_the_line.py` — the exposure.
* `utils/gate_the_top_in_play_does_not_close_the_line.py` — the decision, with
  its criterion written before the number was seen.

---

Related: [The Supporter that buys bodies cannot unblock a turn nothing can attack
in](festival-lead-the-body-search-cannot-buy-the-energy-2026-08-15.md) is the
other page about a search priced above the play that was already winning — there
the inversion *was* the defect, and here it is what stops the fix from paying.
