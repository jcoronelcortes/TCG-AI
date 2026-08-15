# The answer to the wall is a reserve, not today's attacker (Crustle, step 58)

[← Documentation index](README.md)

One board of a game we **won** (episode 93210034, vs Crustle / Mega Kangaskhan
ex), and the sentence under it is the mirror image of
[Meganium is an attacker, not the doubler](crustle-meganium-is-an-attacker-not-the-doubler-2026-08-15.md):
that one says **charge the body that can hurt the wall**, this one says **do not
spend it on something else**.

---

## The board

**Step 58, turn 6** — `records/registro_006_pasos_045_hasta_061.json`

```
US (6 prizes)                          THEM (6 prizes)
active  Teal Mask Ogerpon ex           active  Mega Kangaskhan ex 300/300
        210/210, 4 eff. energies               0 energy, Rapid-Fire Combo 200
bench   Meganium 160/160, 4 eff.       bench   Crustle 170/170, 3 energy
        Teal Mask Ogerpon ex, 2 eff.           Dwebble 70, Dwebble 70
        Meowth ex, 0
```

The menu offered exactly three things: attack with the Ogerpon, retreat, end. The
agent **retreated** — discarding an energy card — promoted the Meganium and
attacked with it. Three things were wrong with that swap at once:

* **Less damage.** *Myriad Leaf Shower* is 30 + 30·(4 own + 0 theirs) = **150**.
  *Solar Beam* is **140**. The retreat paid a card to hit for ten less.
* **The wrong body in front.** *Rapid-Fire Combo* hits for 200: the 160 HP
  Meganium dies to it, the 210 HP Ogerpon it had just pulled back **survives** it.
* **The reserve spent for nothing.** *Mysterious Rock Inn* prevents all damage
  from our Pokémon ex, so that Meganium is the only body of ours that can ever
  hurt the Crustle waiting on their bench — and the Crustle was not what it was
  being sent to fight.

---

## The cause

Two branches of the retreat ladder
([ptcg/turn/options/retreat.py](../ptcg/turn/options/retreat.py)) promote the
anti-wall attacker at **3400**: `_tmo_attacker_ready` (our active is a Teal Mask
Ogerpon ex) and `_crustle_bench_atk` (our active is any ex). Both were guarded by

1. the **archetype** — `op_is_crustle_deck` / `op_is_cornerstone_deck`, and
2. **"the active does not knock out"**.

Both were true here. And (2) is equally true of every board where our ex damages
what is in front perfectly well and simply cannot finish a 300 HP body: "does not
knock out" is not "is blanked". The branches were written for the board where the
wall is **in front**, where our ex really does zero — and their guard never said so.

That is the fourth time an archetype flag has been asked a question about a body:
[the prize the wall does not own](crustle-the-prize-the-wall-does-not-own-2026-08-15.md),
[the wall is a body, not a deck list](matchups.md), the narrowing in
[Meganium is an attacker](crustle-meganium-is-an-attacker-not-the-doubler-2026-08-15.md),
and now the retreat that spends what those three were written to preserve.

---

## The rule

`THE_RESERVE_DOES_NOT_TAKE_THE_FRONT`
([ptcg/cards/ids.py](../ptcg/cards/ids.py)) asks the swap the only question that
pays for it:

> does the body coming up do **more** to their active **this turn** than the one
> going down?

* With the wall actually in front, our ex does 0 through `_our_effective_damage`
  and the promotion still fires **by construction** — the case the branches exist
  for is untouched.
* With anything else in front, the reserve stays on the bench, which is where it
  is worth something.
* **Strictly** more, because the retreat is not free: it discards whole energy
  cards from the body that steps back. A tie is a card paid for nothing.

It reuses the damage model rather than inventing an instrument — the same
`_attacker_base_damage` / `_our_effective_damage` pair the rest of the file
prices swings with — and it discounts the Grass the retreat burns
(`_retreat_grass_units`) before pricing the body coming up, so the promoted
Hydrapple is graded on the field it will actually attack from.

---

## What it measures

**Golden corpus:** two flips in 3 580 decisions, both inside `crustle_wall`
records and both the same sentence:

| record | turn | before | after |
| --- | --- | --- | --- |
| `registro_006` (this board) | 6 | RETREAT | **ATTACK** (150 vs 140) |
| `registro_023_crustle_wall_3` | 4 | RETREAT | **ATTACK** (180 with the Ogerpon vs 80 with a Dipplin) |

**Census** (`utils/census_the_reserve_does_not_take_the_front.py`, 200 games per
list, criterion **0.05 flips/game written before running**):

| list | flips/game | of which, a retreat we did not make |
| --- | --- | --- |
| crustle_wall_1 | **0.53** | 0.53 (100 %) |
| crustle_wall_4 | **0.30** | 0.30 (100 %) |
| great_tusk_crustle_1 | 0.00 | 0.00 |
| **dragapult_1 / alakazam_1** | **0.00** | **0.00** |

Six to ten times the criterion on two of the three lists that carry the wall, and
exactly zero on the ones that do not: the population is real and the rule does
not leak out of its matchup — it cannot, it lives inside branches gated on those
two flags (against `alakazam_1` the flag itself is up 0.00 times a game).

`great_tusk_crustle_1` is the honest exception and worth naming: the wall flag is
up **105 times a game** there and the rule still flips nothing, because on that
list the board it asks about — our ex in front, able to attack, with a charged
reserve behind it — does not come up. The population depends on the list, not
only on the archetype.

**Every single flip, on both lists, is a retreat the agent no longer makes.**
There is no knock-on tail: the rule does one thing.

**Rules oracle** (`utils/oracle_the_reserve_does_not_take_the_front.py`, K=100,
per-board floor from a second batch at different seeds):

| board | with the rule | without | delta | its own floor |
| --- | --- | --- | --- | --- |
| `registro_006` step 58 | 92/100, margin +3.08 | 82/100, +2.62 | **+10 pp** / +0.46 | 10 pp / 0.55 → inside |
| `registro_023` turn 4 | 97/100, +4.32 | 94/100, +4.00 | **+3 pp** / +0.32 | 1 pp / 0.28 → **clears** |

**1 for, 0 against, 1 inside its own board's floor.** Both deltas positive on
both axes; the bigger one is the one the instrument cannot separate from its own
noise, which is stated rather than rounded up.

**Winrate** (`utils/gate_the_reserve_does_not_take_the_front.py`, 1500 paired
seeds per list, two lists, each with its own `--control` row at the same N):

| list | candidate | control (the noise floor at the same N) |
| --- | --- | --- |
| crustle_wall_1 | **+0.60 pp** (z +0.46, p 0.65), prizes **+0.037** | **+0.00 pp**, prizes +0.000 |
| crustle_wall_4 | **+0.60 pp** (z +0.48, p 0.63), prizes **+0.036** | **+0.00 pp**, prizes +0.000 |

The control rows are exactly zero on both lists — the provenance proof that the
two arms differ in nothing but the flag — so the +0.60 is behaviour and not
seeding. It is also **not significant** (p ≈ 0.63): at half a flip per game
against a bot we already beat 85 % of the time, this axis cannot resolve the
rule, and that is a limit of the instrument rather than evidence against the
change ([the instruments](instruments.md)). What is worth more than the p-value
is that the sign is the same on both lists and on both axes (winrate and prize
margin), and the same way the oracle points.

---

## Status

Carried by the **board**, the **census** and the **oracle**, whose two deltas
point the same way; the winrate agrees in sign on both lists (+0.60 pp over a
zero control) without being able to resolve it. The switch to flip is
`THE_RESERVE_DOES_NOT_TAKE_THE_FRONT` in
[ptcg/cards/ids.py](../ptcg/cards/ids.py); the board it comes from is pinned in
[tests/test_the_reserve_against_the_wall_is_not_todays_attacker.py](../tests/test_the_reserve_against_the_wall_is_not_todays_attacker.py),
whose last test is the half that must not move: with the Crustle in the active
spot the reserve still takes the front.
