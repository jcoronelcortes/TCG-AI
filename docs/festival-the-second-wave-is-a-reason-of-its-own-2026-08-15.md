# The second wave is a reason of its own (Festival Lead, step 103)

[← Documentation index](README.md)

One board of a game we **won**, three turns later than it had to be (episode
93242395, turn 10, vs Festival Lead). Every reading the turn needed was already
in the agent, correct, and none of them was allowed to spend it.

---

## The board

`records/registro_010_pasos_099_hasta_114.json`, turn 10, action 5

```
US (3 prizes)                        THEM (3 prizes)
active  Teal Mask Ogerpon ex         active  Applin    40/40
        210/210, 2 {G} cards         bench   Thwackey 100/100
bench   Meganium 160                         Thwackey 100/100
        Teal Mask Ogerpon ex 210             Applin    40/40
        **Dipplin 80, ZERO energy**          Grookey   70/70
        Chikorita 70
        Meowth ex 170                stadium **Festival Grounds** (theirs)
hand    Hydrapple ex, **one Basic {G} Energy**, ...
```

**The turn that was available.** The Grass goes onto the benched Dipplin, the ex
retreats (cost 1, it carries two cards) and *Do the Wave* is 20 × 5 = **100**:
their 40 HP Applin dies, they promote, and because Festival Grounds is on the
field the same wave lands **again** — every body they hold is 100 HP or less.
Two prizes, from three down to one, and the body left in the front spot is worth
**one** prize instead of two.

**What the agent played.** Teal Dance banked that Grass on a benched Ogerpon ex
that already carried four energies; the Dipplin, now with nothing to charge it,
was evolved into Hydrapple ex; and Syrup Storm hit the 40 HP Applin for **330**.
One prize, 290 damage on the floor, a 2-prize ex in front and no second wave.

---

## Four readings, all correct, none of them executing

| reading | value on this board | why it did not spend the turn |
| --- | --- | --- |
| `prizes_today` | **2** | it *labels* a turn; it does not execute one |
| `_promote_ko_active_prizes` | **2** | its only executing consumer is `_win_ko_active_via_promote`, which asks the route to **close the game**: 2 ≥ 3 is false → mode RACE |
| the evolve veto under `_festival_lead_pays_us_now` | **it fired** (Hydrapple = `SCORE_VETO`) | it protected the **body**, and nothing protected the **energy** |
| `_festival_sac_pivot` — *this exact swap* | did not fire | its only door in was `active_ko_likely`, and the ex stood at **210/210** |

The third row is the root cause, and it is the interesting one. **Teal Dance took
the Grass the detector was counting on.** On the next action
`_festival_lead_pays_us_now` read `False` for want of that card, **the veto lifted
by itself**, and the body it had just been protecting was evolved. A reserve that
does not hold the thing it is reserving is not a reserve.

The rung that took it is a *development* charge:
`_active_already_kos and o.area != ACTIVE` → 31050, "our active finishes it
anyway, bank the Grass on a benched Ogerpon for tomorrow". Banking it is right
while the alternative is nothing; here the alternative was the second prize of
**today**.

---

## The change

**1. `_festival_sac_pivot` gains an offensive arm** ([main.py](../main.py)). The
doomed ex is not what makes the wave worth a retreat — the second wave is. The
arm opens on the criterion `_promote_ko_active_prizes` already uses to overrule
"the active can finish it itself": `_festival_second_wave_prizes` has to really
close a second body, and it refuses to claim one unless **every** body they can
promote dies to the same wave (they choose who comes up).

It carries a guard of its own, which the defensive arm does not need: the swap
stands aside when the 1-prize body we leave in front **closes their count**
(`op_prize <= prize_count(relay)`) — the reading `_prize_denial_pivot` was
written for, from the other side of the table. When the two prizes win the game
the question does not arise: that route is `_win_ko_active_via_promote`, and it
outranks this one.

**2. `_festival_wave_needs_the_grass` holds the card**
([ptcg/turn/options/ability.py](../ptcg/turn/options/ability.py)). The Teal Dance
development rung drops to 7500 — the same band as
`_reserve_energy_for_hydra_evolve`, below the manual attachment (~28000) that
puts the card on the body which cashes it. It is a **reserve, not a veto**: with
a second Grass in hand the hand pays for both and the dance keeps its say. The
ACTIVE spot is exempt for the same reason the sibling reserve exempts it — a
dance on the body in front may be paying the retreat fee this very route needs.

---

## What it measures

**The rules oracle** (`utils/search_oracle.py`, rolled forward in the real engine
from that board, K=50 determinizations, our own agent as the policy for both
seats). The winrate saturates — the board is already won against this policy, 50
of 50 either way — so the number with resolution is what the *turn* did:

| forced first choice | our prizes left when the turn ends | steps to game end |
| --- | --- | --- |
| **attach the Grass to the Dipplin** (the fix) | **1.00** (min 1, max 1) → two prizes | 20.9 |
| Teal Dance (what was played) | 1.86 | 36.5 |
| evolve into Hydrapple ex | 2.00 → one prize | 38.6 |

The engine plays the rest of the line by itself: retreat, promotion of the
**Dipplin** (not of the biggest tank — the fourth site
[the sibling finding](#see-also) warns about), and attack **115 twice**.

**The self-play gate is blind here, and its own control says so.** N=1000 against
`deck/real_opponents/festival_lead_5.csv`:

| arm | winrate | prize differential |
| --- | --- | --- |
| candidate | 98.3 % (−0.7 pp) | +5.00 |
| **CONTROL** — HEAD's own `main.py` against HEAD, same N | 98.7 % (**−0.4 pp**) | +5.00 |
| HEAD | 99.0–99.1 % | +5.06–5.09 |

The candidate's reading sits inside the floor the identical code produces. The
cause is already written on `switch_off_festival_lead`: the reference bot cannot
pilot this deck, and it puts the stadium on the field in a minority of games.

**Firing census** (`utils/census_the_second_wave_is_a_reason_of_its_own.py`), 40
games per matchup:

| counter | Festival Lead | control (`marnie_grimmsnarl`) |
| --- | --- | --- |
| our menus with a retreat | 580 | 341 |
| …stadium on the field | 96 | **0** |
| …the wave is lethal | 30 | **0** |
| …the Grass is reserved | 2 | **0** |
| …**and it out-prizes the front** | **13** | **0** |

≈ 0.33 firings per game on the matchup it is written for, and a flat zero on a
list that does not bring the stadium. The inertness is **structural**, not
measured: every path added here lives behind
`AGENT_STATE._festival_grounds_in_play`, and we do not carry Festival Grounds in
`deck.csv`.

**Corpus**: **1 flip** in the whole golden corpus, and it is that decision.
2 890 tests green, `lint_architecture` clean.

---

## Status

**Carried by the rules oracle and the census, NEUTRAL on the winrate gate and
stated as such.** The gate's control at the same N reads −0.4 pp with identical
code, so the candidate's −0.7 pp is not a measurement of this change; the
resolution lives in the two-prizes-instead-of-one the engine plays out
deterministically over 50 determinizations, and in a firing population that is
real (13 in 40 games) and does not leak (0 outside the stadium).

Test: `tests/test_the_second_wave_is_a_reason_of_its_own.py` — 12 cases,
including the three that must stay shut: a survivor on their bench, no stadium,
and their match point.

### See also

* [The second wave is the game, not a prize](../tests/test_the_second_wave_is_the_game_not_a_prize.py)
  — the same stadium read from the WIN route (registro_020, step 146), and the
  warning about the **four** places that count the prizes of a route: fixing
  three of them is worse than fixing none.
