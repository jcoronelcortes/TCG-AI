# The knockout that ends the game does not belong to a pivot (Alakazam, step 173)

*Episode 93675887 step 173, turn 15 vs Alakazam — **won in spite of this**. Our
pile at **one prize**. Active Meganium 130/160 with four symbols in front of a
70 HP Dunsparce: *Solar Beam* hits 140 and cashes the last prize. The agent
played Boss's Orders, gusted their Fezandipiti ex, retreated the Meganium,
promoted the Hydrapple ex and attacked with Syrup Storm — giving away a whole
turn in a game that was already won.*

## The culprit was not the Boss's ladder

`_active_attack_wins_now` was **True** and the ATTACK scored **1100**. The
finisher rung of the attack menu (99000, `ptcg/turn/options/attack.py`) is
conditioned on `plan.attacker == 0`, and the plan said **1**. With the attack out
of its rung, `win_via_bench` (5600) took the turn by 4 500 points.

## The chain, measured on the loop itself

* The attack loop chose **correctly**: active Meganium, `SCORE_WIN_GAME + 524`,
  above the three bench candidates (50302, 50002, 50002).
* The Hydrapple ex pivot **overwrote it immediately afterwards**
  (`plan.attacker = _hydra_mc_idx`), on the argument that a 330 HP body on the
  bench **lasts longer** than a Meganium at 130. Its two exceptions do not cover
  this board: the Tapu Bulu one is by species, and the survivor one compares HP
  (330 <= 130 is false). And `_ph_gana` — *"the gust wins the game"* — had also
  switched off the exposure brake.

## The machine that prevents it already existed and was missing a half

`_active_win_plan` captures the active's winning plan **before** the pivots and
restores it afterwards. Its condition read **only one of the two ways a turn
closes a game**: the opponent with an **empty bench**, unable to promote a relay
(`registro_016` p138 vs Crustle).

The ordinary one was missing — **the knockout cashes the prizes we are short
of** — so on any board at match point the pivots were free to trade the winning
blow for a tougher body.

Durability, prize denial and mismatch are arguments about the **next** turn, and
a turn that ends the game does not have one.

The sentence is deck-agnostic by construction: it reads `my_prize` and
`prize_count_op(target)`, never an archetype or a card list. It is the same one
the Boss's ladder already says twice from the other side
(`winning_finisher_on_the_active_after_retreating`,
`the_field_ability_wins_on_the_active`); what was missing was saying it **in the
plan**, which is what all those consumers read.

## It keeps both brakes

Anchoring the plan to an attack that does **not** win would be worse than the
pivot, so `_active_attack_wins_now` keeps them:

* the knockout must be **guaranteed** (`_ko_not_guaranteed`, the same test the
  loop uses for `SCORE_WIN_GAME`), and
* it must not be the **suicidal finisher that draws** — if our own attack knocks
  our body out and that corpse gives them their last prize, the bench relay that
  wins cleanly has to stay reachable (`registro_016` p184 vs Marnie).

## A census arbitrates it, because the fix deletes its own population

Counting the population on the fixed agent returns zero and proves nothing, so
**each arm plays its own games**. 120 games per arm across four lists
(`alakazam_1`, crustle+tusk+NZ, marnie, dragapult):

```text
baseline HEAD     turns 2013  lethal 1591  ends_game 122  diverted 6 (0.3%)  thrown 5
candidate         turns 1939  lethal 1472  ends_game 121  diverted 0 (0.0%)  thrown 0
```

`diverted` is the rule's board — the turn had the win and the plan pointed
elsewhere — and `thrown` the five where the win never got played. **The
instrument demonstrates it can fail before it reports the zero.**

| instrument | number |
| --- | --- |
| Frozen corpus | **3 flips**, all three the **same turn** of `registro_046_festival_lead_8_asiento0` (turn 16, our pile at one prize, Myriad Leaf Shower 150 in front of an 80 HP Dipplin). Before: Night Stretcher → evolution → retreat, and the same game won a turn later. Now it attacks. |
| Local corpus | unchanged |
| Mirror self-play vs HEAD, 400 games alternating seat | **54.2 %** [CI95 49.4–59.1], prize differential **+0.28** |
| Matchups, 300 games per arm | alakazam_1 98.3 vs 98.7 (prizes +4.04 vs +4.01); crustle+tusk+NZ 98.0 vs 99.3 (+4.20 vs +4.25) — saturated and flat, no collateral |

The winrate does not clear the noise at that N and is declared the way it came
out; the **differential** is what grades it.

## It moved a test board, and that is marked

`test_archaludon_pivot_when_the_tank_really_knocks_out` was asking about the
defensive pivot **at match point** (our pile at 2, their Archaludon ex worth 2),
where the pivot has nothing to answer: it was paying a retreat to win the same
game the active already closed. Two prizes are added so the question exists, and
the original board now has a test of its own.

## Files

* `main.py` — `_active_win_plan`.
* `tests/test_the_ko_that_ends_the_game_is_not_a_pivots_to_trade.py` ·
  `tests/test_main_regressions_1.py`
* `tests/fixtures/alakazam_the_ko_that_ends_the_game_step172.json` ·
  `..._step173.json`
* `utils/census_the_ko_that_ends_the_game.py`

---

Related: [The gust that ends the game is not a
jam](dragapult-the-gust-that-ends-the-game-is-not-a-jam-2026-08-16.md) is the
same sentence in the Boss's target ladder — there the win was found and thrown
away by the ladder; here it was found, chosen, and then overwritten by a pivot.
