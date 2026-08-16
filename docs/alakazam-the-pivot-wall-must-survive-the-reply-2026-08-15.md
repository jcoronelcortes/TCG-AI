# A wall that falls to the same hit is not a wall (Alakazam, step 119)

*Episode 93430769 vs Alakazam, **LOST**. `records/registro_011_pasos_112_hasta_127.json`,
step 119, turn 11. Reported by the user, 15 August 2026.*

## The board

| US — 4 prizes left | THEM — 2 prizes left |
|---|---|
| **active** Meganium **160/160**, 4 effective energies | **active** Alakazam **140/140**, 5 energies |
| **bench** Teal Mask Ogerpon ex 210 (4 en.) · Meowth ex ×2 · Bayleef 110 · **Hydrapple ex 330/330** (2 en.) | **bench** Fezandipiti ex 210 · Kadabra ×2 |
| | **hand 19 cards** → Powerful Hand projects 20 × (19 + 2) = **420** |

*Solar Beam* prints **140**. Their Alakazam has **exactly 140 HP** and is
untouched. The prize was already ours, this turn, for free — and taken by a body
that hands over **one** prize when it falls.

The agent **retreated it**. Paying the cost burned both Grass cards off the
Meganium; the promotion that followed put up a **Bayleef** with no energy; the
turn ended without attacking.

## Why

`_hydra_pivot_active` (main.py), the defensive pivot to Hydrapple ex. It fires on
two readings, both of them true here:

* the active is doomed — `active_ko_likely`, off their Powerful Hand;
* the benched Hydrapple ex knocks their active out from where it stands —
  30 + 30 × 8 Grass after the retreat = 270 ≥ 140.

It then points `plan.attacker` at the bench, and that is what does the damage:
with the plan pointing away from the active, the ATTACK option is suppressed. At
step 119 the scores were

```
[DBG] ctx=0 opciones=7
[DBG]   #1 idx=5 score=6500   <- RETREAT
[DBG]   #5 idx=4 score=-1     <- ATTACK, Solar Beam
```

**Its whole justification is the wall, and it never asked whether the wall
stands.** That same Powerful Hand projects **420** against 330 HP. So the trade
was: give up a free knockout, discard two Grass, and swap a one-prize corpse for
a two-prize one. The promotion chain then read the projection correctly — every
body it could promote dies — and picked the cheapest one to lose, which is how a
Bayleef ended up in front of an Alakazam at their match point.

## The fix, and it is not a new idea

The guard already existed **twenty lines above**, on the *other* promotion of the
same Hydrapple ex (`_promote_hydra`), learned from `registro_011` step 138 vs
Dragapult — also a lost game — and phrased there word for word:

> The pivot is only allowed if it SURVIVES the projected hit or if its own KO
> already wins the game.

The twin never got it. `THE_PIVOT_WALL_MUST_SURVIVE_THE_REPLY`
(`ptcg/cards/ids.py`) gives it the same one, with the same escape hatch: when the
knockout it delivers ends the game there is no reply left to survive. It reuses
`_op_active_attack_damage_to`, which already models Powerful Hand.

## Measurement

**The population is tiny, and that is the first number.** Census over 200 games
vs `alakazam_1`: **8 flips in 27 085 decisions = 0.04 per game**, five of them
"a retreat we did not make". Frozen corpus (50 records, 3 580 decisions):
**0 flips**. `records/`: **1**, the board itself (RETREAT → ATTACK).

**The self-play gate cannot resolve it, and says so.** n = 1500 paired seeds vs
`alakazam_1`: candidate **1459/1500**, baseline **1459/1500**, delta **+0.00 pp
exactly**, prizes +0.004. Two arms that never diverged into a different result.

**The rules oracle is what graded it — after the instrument itself had to be
fixed.** `search_oracle._choose` drives *both* seats with the policy it is
given, so `policy="agent"` plays their Alakazam deck with our Grass agent, out of
the same `AGENT_STATE`. That confound does not cancel between the two options,
and it reverses the answer:

| continuation policy | RETREAT | ATTACK | says |
|---|---|---|---|
| both seats = our agent | 96–99/100 | 64–68/100 | retreat, **+32 pp** |
| both seats = random | 40/60 | 54/60 | attack, +23 pp |
| **ours = agent, theirs = random** | **92.5 %** | **98.5 %** | attack, **+6.0 pp** |

Only the third asks the question we mean: grade OUR choice under OUR policy,
against an opponent that is merely legal. K = 200 × 3 batches per option, and the
batches are what makes the gap real rather than quoted — ATTACK **198/197/196**,
RETREAT **186/181/188**: the two ranges do not touch, which is more than either
option's own floor. `utils/oracle_the_pivot_wall_must_survive_the_reply.py`.

⚠️ **Read the first row before trusting the third.** A single instrument run one
way says the opposite of the change; what disqualifies it is a named confound,
not the answer it gave. If the shared-belief distortion is ever fixed in
`search_oracle`, this board is the one to re-grade.

## What does not change

Both controls in `tests/test_the_pivot_wall_must_survive_the_reply.py` are the
boards the pivot was written for, and both still fire:

* **the wall actually stands** — fourteen cards in their hand, 20 × 16 = 320,
  which kills a 160 HP Meganium and does not kill a 330 HP Hydrapple ex;
* **the knockout ends the game** — one prize left and their active worth exactly
  that.

Each is killed by its own mutant: dropping the survival read kills the first,
dropping the escape hatch kills the second, and turning the switch off returns
the recorded retreat.

## Files

* `main.py` — the guard, inside `_hydra_pivot_active`'s candidate loop
* `ptcg/cards/ids.py` — `THE_PIVOT_WALL_MUST_SURVIVE_THE_REPLY`
* `tests/test_the_pivot_wall_must_survive_the_reply.py` — 5 cases, 2 of them controls
* `tests/fixtures/alakazam_no_retirar_el_meganium_que_ya_noquea_step119.json`
* `utils/gate_the_pivot_wall_must_survive_the_reply.py` — the winrate row, with `--control`
* `utils/oracle_the_pivot_wall_must_survive_the_reply.py` — the per-seat-policy oracle
