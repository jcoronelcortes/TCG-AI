# The seat that hands the game over yields to the body that survives the reply (Mega Froslass ex, step 110)

*`records/registro_009_pasos_088_hasta_110.json`, last menu — episode 93638940
vs Mega Froslass ex / Mega Starmie ex, **lost**. Their pile at **one prize**. Our
Tapu Bulu 90/140 with four symbols in front of a Mega Froslass ex 310/310: *Wood
Hammer* hits 220 and does not knock out. Their *Resentful Refrain* is **50 per
card of OUR hand** and the hand was three: **150 onto a body at 90**. On the
bench, a Hydrapple ex 330/330, and the Tapu's retreat already paid for (two
physical Grass are four symbols against a cost of three). The agent attacked.*

## Two holes, and they covered for each other

1. **The reading.** `_op_active_attack_damage_to` returned **zero** for
   *Resentful Refrain*. Entry 1240 of `ptcg/cards/op_scaling.py` has read it
   correctly since the table existed (`50 * s.my_hand`), but it is **opt-in** and
   no defensive rule asked for it. With the projected reply at zero,
   `active_ko_likely` is False and **no pivot in the file can see the knockout
   coming**.
2. **The rule.** Even with the number, no sentence spoke about this board. The
   family that yields the front is written **body by body**: `_hydra_wall_pivot`
   and `_teal_wall_pivot` want a Teal Mask Ogerpon ex in front, `_doomed_mute_pivot`
   a **mute** active, `_prize_denial_pivot` and `_doomed_ex_sac_pivot` a two-prize
   ex to make cheaper. In front stood a **one-prize** body that **can** attack,
   and against a pile of one there is nothing to make cheaper.

And on top of both, the guard that took the turn: `_grd_prefer_attack` (*"the
active can attack and nobody knocks out → attack"*) vetoed the retreat from a
rung **above** the one the turn plan had already decided — the plan pointed at the
Hydrapple (`plan.attacker=4`, 150 of Syrup Storm), so the **ATTACK** menu vetoed
itself too. Attack −1, retreat −1, end −10000: the turn was left **with no play**
and the argmax fell on the vetoed attack by menu order. That `[0]` in the record
is not a choice, it is a tie between two vetoes.

## The sentence

If **their reply onto the body in front takes the game**, and the bench holds one
that **survives it**, the seat belongs to that one. It does not buy a better
turn: it buys that there **is** a turn. It names no card, so it belongs to no
deck in particular.

## It is two menus and both are needed

> *"Fixing one branch of a pair and leaving its twin is how this turn was lost."*

* **The retreat** — `_wall_that_outlasts_the_losing_reply` (`ptcg/calc/damage.py`)
  and rung **6750** in `retreat.py`, one step above `_grd_prefer_attack` and below
  everything that cashes a prize today.
* **The promotion** — `_losing_seat_survivor` and `PROMO_LOSING_SEAT_WALL`
  (**12000**) at the end of the `card.py` chain. **The census found this half, not
  a human reading a game**: the `doomed` counter showed 2 of 19 simulated
  promotions vs `crustle_wall_1`. The captured board (its own fixture): turn 23,
  their pile at one, their Cornerstone Mask Ogerpon ex hitting for 140, and of the
  whole bench only the Meganium 160/160 survives — but it was vetoed to
  `SCORE_NEVER` by *"the Meganium line does not go to the active spot"*, whose only
  exemption is written for the **forced** promotion, and this menu was opened by a
  retreat of ours. The seat went to an 80 HP Dipplin at **−4745**, the least bad of
  a table of negatives.

A reserve is an argument about the turns that are coming. **At their match point
they are not coming.**

12000 is a **floor** (`max`) and not an assignment, so `PROMO_CLOSER_SEAT`
(15000) and `PROMO_KO_BONUS` (20000) keep the last word with no exemption
written — if **our** knockout closes first, their reply never gets to exist — and
it carries the previous score clamped to 0..999 so the order **between**
survivors is not lost: with two that hold, the engine reserve decides again.

## Why `scaled=True` is read here, when it measured negative in the other 90 places

The other measurement (−0.10 / −0.08 / −0.05 prizes, three samples of three) was
calibrated against a failure mode that is **going passive**. These two rules only
speak when **not moving loses the game**. There is no passivity to buy — and it is
the only way the sentence can see a Mega Froslass ex at all, whose attack prints
**0**.

## The census arbitrates, because a 1–5 % firing does not fit in the bench's noise floor

| half | number |
| --- | --- |
| **Retreat** | frozen: 3 of 931 menus, **0 flips**; local records: **1 flip** (the finding); self-play **0.59–0.97 %** vs crustle/starmie, 0.15 % vs the record's list, **zero** vs alakazam and dragapult. Every observed flip is ATTACK/PLAY/PASS → RETREAT, escapes **0**, and `doomed` drops from 2 of 19 to **zero**. |
| **Promotion** | frozen: 6 of 180 menus, **0 flips**; self-play **0.22–4.71 %**, and `P.saved == P.flips` in every run: every seat that moves goes to a body that survives the reply. |

Frozen corpus overall: **0 flips of 3 580**. Gate at 1 500 games per arm:
crustle −0.7 / +2.1 / +0.2, starmie +1.1 / −1.5, the record's list +0.1 over a
matchup saturated at 97 %. **It changes sign between runs, so it is reading
nothing.**

## It moved a limit, and that is marked

`test_the_last_stand_takes_the_front_spot` used to prove *"a tank that costs us
the engine is not a last stand"* with a **400 HP Meganium** — the only body that
survives their 340. It was mixing two boards. It is split in two, and what
remains is the real boundary: **340 falls and stays vetoed; 341 holds and takes
the seat.**

## Files

* `ptcg/calc/damage.py` — `_wall_that_outlasts_the_losing_reply`.
* `ptcg/turn/options/retreat.py` — the 6750 rung.
* `ptcg/turn/options/card.py`, `ptcg/cards/scoring.py`, `ptcg/turn/ctx_scoring.py`
  — `_losing_seat_survivor`, `PROMO_LOSING_SEAT_WALL`.
* `tests/test_the_seat_that_loses_the_game_yields_to_the_wall.py` ·
  `tests/test_the_last_stand_takes_the_front_spot.py`
* `tests/fixtures/froslass_their_match_point_the_seat_that_loses_the_game_step110.json`
  · `crustle_their_match_point_the_engine_yields_the_seat.json`
* `utils/census_the_seat_that_loses_the_game.py`

---

Related: [The seat that closes the game is not a
tie-break](alakazam-the-seat-that-closes-the-game-is-not-a-tie-break-2026-08-16.md)
is the same menu at **our** match point instead of theirs, and its rung is what
keeps the last word over this one.
