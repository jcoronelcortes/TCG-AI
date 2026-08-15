# The shield they buy for one turn (Acerola's Mischief)

*14 August 2026 — episode 93163758 vs a Comfey/Chandelure deck, **LOST holding
one prize** while the opponent never left six.*

## The game

From turn 13 to the end, their board never changed:

| us (2 prizes, then 1) | them (6 prizes) |
| --- | --- |
| active Teal Mask Ogerpon ex, 3 Grass | active **Comfey 70/70**, 1 energy |
| bench Teal Mask Ogerpon ex — 7 Grass, then 9, then 10 | bench Chandelure 130, Chandelure 130 |
| hand **Boss's Orders**, Applin, Dipplin, Forest of Vitality, Grass | |

Myriad Leaf Shower is `30 + 30` per energy on both actives, so every projection
in the agent said the Comfey died and `prizes_today` said one. The engine said
otherwise, every turn:

```
turn 13  {"type": 16, "serial": 66, "value": 0}
turn 15  {"type": 16, "serial": 66, "value": 0}
turn 19  {"type": 16, "serial": 75, "value": 0}
```

**Acerola's Mischief (1228)**, played on their turn, three copies (serials 120,
122, 121):

> You can use this card only if your opponent has 2 or fewer Prize cards
> remaining. Choose 1 of your Pokémon in play. During your opponent's next turn,
> prevent all damage from and effects of attacks done to that Pokémon by your
> opponent's Pokémon ex.

Its own precondition is what makes it expensive: at two prizes or fewer, i.e.
on the turns where the game ends.

## Why nothing in the agent saw it

This agent knows three walls and reads all three **off the board**: Crustle
(`EX_IMMUNE_IDS`), Cornerstone (`ABILITY_IMMUNE_IDS`) and Neutralization Zone
(the missing Rule Box under a stadium anyone can see). This one leaves *nothing*
behind — no tool, no ability, no stadium — and the protected body looks exactly
like the body it was. The only evidence is the **PLAY log** of their turn, which
goes past once, in the batch that closes it.

Worse, the one instrument built to catch "the agent believed a knockout the
engine refused" is **blind to this defect by construction**.
`differential_oracle.judge()` attributes a prediction to the single opposing body
whose hp *changed*, and an attack the shield zeroes changes nothing:
`if not hit: return None, False`. Run against `chandelure_1` with the reading off
it reports `NINGUNO` on 321 judged attacks — the same as with it on.

## The reading

* `OP_EX_SHIELD_IDS` names the card family (`ptcg/cards/ids.py`).
* `main.py` scans the **whole** log batch (not the post-turn-boundary slice: the
  play belongs to the turn *before* the one it governs) and pins two things:
  `_op_ex_shield_serial`, their active's serial at the moment of the play, and
  `_op_ex_shield_turn`, the one turn it buys. It publishes
  `AGENT_STATE.op_ex_shield_serial` for the observation being answered, plus the
  sticky `op_has_ex_shield`.
* **A serial, not the spot.** The shield travels with the body: gust it to the
  bench and the mute goes with it, while whatever comes up in its place is fair
  game. A reading keyed on "their active" would mute the wrong body one action
  after our own Boss's Orders — which is the answer to the card.
* `_shield_mutes_our_ex` (`ptcg/calc/damage.py`) sits on the line next to the
  stadium's zero inside `_our_effective_damage`, and `_wall_mutes_our_ex` joins
  the two for the energy routing.
* `attack.py` vetoes swinging into the shield, exactly as it already vetoes the
  coin dodge, and for the same reason: an attack ENDS THE TURN. On step 136 the
  agent attacked as its **first** action holding thirteen cards. Snipers
  (`SNIPE_ANY_TARGET_IDS`) are exempt — Cruel Arrow picks its own target.
* The forced discard (`ptcg/turn/options/card.py`, `DISCARD_SHIELD_*`): the same
  deck runs Xerosic's Machinations, and the Comfey ladder priced the hand for the
  deck-out race only. Under the shield the hand splits by one question — what can
  still put damage on their board — so our ex, the stadium and the Ultra Ball
  become the fodder, in that order, and Boss's Orders, the energy, the Applin and
  the Dipplin are kept.

## The turn it produces

Driving turn 13 forward through the engine with the agent choosing:

```
Teal Dance on the ACTIVE (3 -> 4 energy)   [before: on the bench twin]
attach Grass to the active (4 -> 5)
PLAY Boss's Orders -> their benched Chandelure
attack: 30 + 30x5 = 180 >= 130  -> knocked out, prize taken
```

Turn 19, with no gust in hand, becomes six real actions (Poké Pad, stadium,
bench a Meowth ex, retreat onto the ten-energy twin, Chikorita → Bayleef →
Meganium) instead of one null attack.

## What was measured

| instrument | result |
| --- | --- |
| frozen corpus (50 games) | **0 flips** — the card appears in none of them |
| harvested records | **7 flips**, all in this episode: attack-for-zero → gust / development |
| firing census (`--census`, 40 games × 5 lists) | **50–94** mute readings per game on the three lists that carry the card, **0** on both controls |
| self-play n=1000 × 5 lists | **+0.08 pp** — and the `--control` run (same code in both arms) spread to **−1.90 pp** on one of the same lists. Saturated at 94–98 %: the winrate cannot resolve this |
| search oracle, K=100 on the 7 flipped boards | **3 in favour, 0 against**, 4 inside their own board's floor |

**Neutral in winrate; it enters on the census, the corpus audit and the rules
oracle.** The two turn-19 boards read 0/100 in both arms — by then the rollout
has lost the game too — and the rollouts run *our* policy in both seats, which
does not reproduce the lock the real opponent held.

## Files

* `ptcg/cards/ids.py` — `Acerolas_Mischief`, `OP_EX_SHIELD_IDS`,
  `OP_EX_SHIELD_MAX_PRIZES`, the `DISCARD_SHIELD_*` rungs
* `ptcg/state/agent_state.py` — the three fields and the sticky flag
* `ptcg/calc/damage.py` — `_shield_mutes_our_ex`, `_wall_mutes_our_ex`,
  `OP_EX_SHIELD_ROUTING`
* `main.py` — the log scan that pins the serial and the turn
* `ptcg/turn/options/attack.py` — the veto
* `ptcg/turn/options/card.py` — the forced-discard rungs
* `tests/test_the_shield_they_buy_for_one_turn_mutes_our_ex.py` + two fixtures
* `utils/gate_the_shield_they_buy_for_one_turn.py` (census + two-arm gate)
* `utils/oracle_the_shield_they_buy_for_one_turn.py` (the rules oracle)

## Still open

* **The non-ex assembly is not a ROUTE.** With no Boss's Orders the answer is to
  build the body the shield cannot touch — stadium, Applin, Dipplin, four benched
  Pokémon for `20×bench`, retreat — and today that turn only *emerges* from the
  development ladders once the attack is vetoed. There is no `ROUTE_*` for it in
  `ptcg/turn/game_plan.py`, so nothing reserves the pieces for it.
* **The shielded body is assumed to be their active** at the moment of the play.
  The log does not carry their choice. It was the active on all three copies of
  this episode, and it is the only choice that costs us anything — but a list
  that shields a benched body would have us avoiding a front we could hit.
