# Meganium is an attacker, not the doubler (Crustle, steps 92 and 137)

[← Documentation index](README.md)

Two boards of the same lost game (episode 93251328, vs Crustle / Mega Kangaskhan
ex), fourteen turns apart, with the same sentence under both: **the turn's only
Grass went to a body the wall had already switched off, while the one attacker
we owned sat at zero.**

---

## The boards

**Step 92, turn 14** — `records/registro_014_pasos_090_hasta_096.json`

```
US (5 prizes)                          THEM (5 prizes)
active  Teal Mask Ogerpon ex, 4 eff.   active  Mega Kangaskhan ex 150/300
bench   Meganium 160, ZERO energy      bench   Crustle 170, 3 energy
        Meowth ex, Chikorita,                  Crustle 170, 1 energy
        Teal Mask Ogerpon ex, 2 eff.
hand    Hydrapple ex, ONE Basic {G} Energy
```

The active Ogerpon knocks the Kangaskhan out on the energy it already carries.
What stands up next is a Crustle, and *Mysterious Rock Inn* cancels all damage
from our Pokémon ex: of everything on that board only the Meganium can ever
touch it. The agent spent the Grass on **Teal Dance over the second Ogerpon ex**
— 31500 against the attachment's 27000 — charging a *second* ex against the wall
that blanks ex.

**Step 137, turn 20** — `records/registro_020_pasos_136_hasta_141.json`

```
US (1 prize)                           THEM (2 prizes)
active  Teal Mask Ogerpon ex, 4 eff.   active  Crustle 190/190, 3 energy
bench   Meganium 160, ZERO energy      bench   Crustle 150/150, 1 energy
        Meowth ex, Chikorita,
        Fezandipiti ex, Applin 40  (benched THIS turn)
hand    six Basic {G} Energy, Dawn, Lillie's Determination, Forest
```

Their Superb Scissors had just knocked our Tapu Bulu out. One prize from
winning, the turn's attachment went to the **Applin** (30000) over the Meganium
(27000) — a 40 HP basic that came down that very turn, so it could not evolve
until the next one, and whose Dipplin dies to one Scissors when it does.

---

## The two causes, one reading

**1. The reservation did not name Meganium.** `_wall_atk_needs_grass`
([ptcg/turn/options/ability.py](../ptcg/turn/options/ability.py)) already says
"with a single Grass in hand the last one belongs to the body that can still hit
the wall", and its Crustle creditor list read `(Tapu_Bulu, Dipplin, Pinsir)`. The
comment above it justified the absence with *"against Crustle and Cornerstone it
is the doubler"* — **true of Cornerstone**, whose Stance blanks the bodies *with*
an Ability and Wild Growth is one, and **false of Crustle**, which blanks the
bodies with a rule box. Meganium has none.

**2. The ladder ranked it last.** In the Crustle band of `_energy_score_base`
([ptcg/turn/energy.py](../ptcg/turn/energy.py)) Meganium's `+19000` was paid only
`if not _tapu_in_play_meg and not _dipplin_in_play_meg`, under Dipplin's `+23000`
and Applin's `+22000`.

The order is now the order of the attack, which is the order the user spelled
out:

| body | attack | cost | HP |
| --- | --- | --- | --- |
| Tapu Bulu | Wood Hammer **220** | 4 units | 140 |
| Meganium | Solar Beam **140** | 4 units | **160** |
| Dipplin | Do the Wave **100** at a full bench | 1 unit | 80 |

The HP column decides what the damage column leaves open. Their Superb Scissors
does a flat 120 that *"isn't affected by any effects on your opponent's Active
Pokémon"*: the Meganium survives it and swings twice, the Dipplin gives a prize
back after one. Neither one-shots a 150 HP Crustle, so only the one that lives to
swing again removes it.

**What did not change.** An **active** Dipplin that swings today keeps
`_ctm_charge_active_dipplin` at 50000 — a charge that attacks this turn was never
development, and the one that yields to Meganium is the **benched** Dipplin, a
promise for another turn exactly like the Meganium it now yields to.

---

## The narrowing, and it is the third time this repository has needed it

The first version was gated on `op_is_crustle_deck`. Graded by the rules oracle
over the fifteen boards where it changed a decision, that came back **3 for, 6
against** — and the six were legible:

| board | their active | delta |
| --- | --- | --- |
| `023_wall_3` t6 | **Mega Kangaskhan ex 400/400** | −8 pp |
| `012_wall_1` t10 | Crustle 150/150, our **Tapu Bulu at 6 units** in front | −7 pp |
| `022_wall_2` t6 | **Crustle 40/150** | −5 pp |
| `016_wall_13` t14 | **Mega Kangaskhan ex 300/300** | −2 pp |
| `020_wall_17` t6 | **Crustle 60/150** | −1 pp |

Five of the six are boards where the wall **is not the obstacle**: something else
is in front that our ex hit perfectly well, or the Crustle in front is already
dead. `op_is_crustle_deck` says they *brought* a wall; it does not say the wall
is in the way. Same defect as
[the prize the wall does not own](crustle-the-prize-the-wall-does-not-own-2026-08-15.md)
and as [the wall is a body, not a deck list](matchups.md) — an archetype flag
answering a question about a body.

`_ctm_wall_in_the_way` ([main.py](../main.py)) asks the board instead, in two
halves:

* **the wall is in front** → it is in the way while it still *stands*. A wall
  this turn's attack already removes is a wall that is answered. Same reading as
  the `_teal_wall_pivot` guard: a fee is worth paying while it is owed.
* **something else is in front** → the wall is only what we face *next* if that
  something falls to our attack today and a wall is waiting on their bench. That
  is step 92's own board.

It reuses `_active_already_kos` rather than inventing an instrument: that flag
prices our active's swing through `_our_effective_damage`, so the wall's
ex-immunity is already inside it — an ex in front of a Crustle reads `False`
because it really does zero.

> **A bug worth naming, because a control caught it and the author did not.** The
> first narrowing moved the *gate* to `_ctm_wall_in_the_way` and left the *band*
> reading the switch alone. On a board where the wall was not in the way,
> Meganium fell back to the old "only while no Tapu and no Dipplin are in play"
> gate and then collected the **new** 23000 anyway — the loosest of the three
> readings, and not one the oracle had graded. Both now resolve through a single
> `_ctm_meg_up`.

---

## What it measures

**Census** (`utils/census_meganium_is_an_attacker.py`, 200 games per list,
criterion **0.20 flips/game written before running**):

| list | flips/game | of which, energy onto Meganium |
| --- | --- | --- |
| crustle_wall_1 / 4 / 8 / 13 / 14 | 0.62 · 0.84 · 0.77 · 0.58 · 0.84 | 0.59 · 0.77 · 0.71 · 0.41 · 0.79 |
| great_tusk_crustle_1 | 0.79 | 0.77 |
| **marnie / alakazam / dragapult** | **0.00** | **0.00** |

Three to four times the criterion on the lists that carry the wall, and exactly
zero on the ones that do not: the population is real and the reading does not
leak out of its matchup.

**Rules oracle** (`utils/oracle_meganium_is_an_attacker.py`, K=100, per-board
floor from a second batch at different seeds), on the narrowed tree:

| arm | boards | for | against | inside their own floor |
| --- | --- | --- | --- | --- |
| both | 9 | **5** | 2 | 2 |
| ladder alone | 5 | **2** | 1 | 2 |
| reserve alone | 2 | **0** | 1 | 1 |

And the board-by-board reading matters more than the totals, because five
independent runs exist for each:

* **step 137 (the ladder): +17, +20, +26, +28, +18 pp**, every run 2–7× its own
  floor. This is the result the change rests on.
* **step 92 (the reservation): +1, −2, +2, −2, −1 pp**, floors between 0.02 and
  0.33. The sign moves with the seed: the oracle cannot separate that decision
  from noise, and alone the half grades 0 for / 1 against.

**Winrate** (`utils/gate_meganium_is_an_attacker_not_the_doubler.py` and paired
selfplay against `HEAD`, 1500 paired seeds per list, 17 wall lists + 6 controls):
see the table in the commit. The control arm is **+0.00 on every list**, which is
the provenance proof; the candidate rows sit inside their own spread. **Measured
NEUTRAL**, stated as measured.

---

## Status

**The ladder half is carried by the oracle.** The reservation half is **NEUTRAL,
shipped on the user's decision and not on a measurement** — its only real board
oscillates in sign across five runs and alone it grades 0 for / 1 against. It is
strategically right (a second ex charged against the wall that blanks ex buys
nothing) and its measured harm is inside the instrument's floor on the winrate
axis, but the honest reason it is small is visible on the board itself: the Grass
that goes to the second Ogerpon still raises Syrup Storm and still draws a card.

Marked so a later session can revisit it as a candidate for reversal rather than
mistaking it for a measured win. The switch to flip is
`MEGANIUM_IS_OWED_THE_LAST_GRASS` in [ptcg/cards/ids.py](../ptcg/cards/ids.py).
