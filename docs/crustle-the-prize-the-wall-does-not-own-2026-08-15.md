# The prize the wall does not own

*15 August 2026 — episode 93232495 vs a Crustle / Mega Kangaskhan ex deck,
**LOST**. `records/registro_017_pasos_123_hasta_125.json`, turn 17, steps 123
and 125.*

## The turn

Two turns earlier our Tapu Bulu had put Wood Hammer through the Mega Kangaskhan
ex for 220 and taken 30 back. Their reply was two Crushing Hammers, one of which
landed and took a Grass card off the Tapu. Then our turn 17 opened:

| us (4 prizes) | them (3 prizes) |
| --- | --- |
| active **Tapu Bulu 30/140, 2 units** | active **Mega Kangaskhan ex 80/300, no energy** |
| bench Meganium (4), Teal Mask Ogerpon ex (4), Fezandipiti ex, Teal Mask Ogerpon ex (4), Meowth ex | bench Crustle 150 |
| hand Poke Pad, **Night Stretcher**, Teal Mask Ogerpon ex, Xerosic's Machinations | |
| discard **six Basic Grass Energy** · the turn's attachment UNSPENT | |

Wood Hammer costs four units and does 220 flat. Meganium's Wild Growth is on the
bench, so one basic Grass **card** is two units: the Tapu sat at 2 of 4, and one
Grass out of that discard both paid for the attack and knocked out a Mega ex at
80 HP — **three prizes**, four down to one, against a board whose only other
body is a Crustle and whose active could not even answer (zero energy on it).

The agent played Xerosic's Machinations and then ended the turn with the Night
Stretcher in hand. `utils/turn_explorer.py` finds the line unaided on that same
observation:

```
best line found by the explorer (13 nodes):
  NS->PLANTA -> ATTACH->Tapu Bulu -> RETREAT->Meganium -> ATTACK
evaluation (wins, prizes, damage, development): (0, 3, 80, 72)
```

Three prizes against the agent's zero.

## What was deciding, and it was not a scoring judgement

`_score_night_stretcher_play` **replaces** its ballot against a wall archetype:

```python
if ctx.op_is_crustle_deck or ctx.op_is_cornerstone_deck:
    best, traza = _resolve_max(_ESC_NS_CRUSTLE, w)     # the whole ballot
else:
    best, traza = _resolve_max(_ESC_NS_RECUPERACION, w)
```

That swap is right for the question it was written for — *which body is worth
recovering when our ex cannot touch the thing in front* — and it silently
swallowed a different one. Every scenario that prices a recovered **energy** by
whether it takes a prize today lives in the list that gets replaced:
`energia_syrup_letal`, `energia_remate_con_el_activo`,
`energia_remate_via_promocion`, `energia_retirada_letal`. Against a Crustle list
they never got a vote. Not rarely — never, and regardless of who was standing in
the active spot. Here the Crustle was on their **bench**.

On top of that, three of those four predicates each carried
`not w.op_is_crustle_deck and not w.op_is_cornerstone_deck` of their own, so the
guard was in the file twice.

`PTCG_DEBUG` over the record shows the consequence at step 125, with the menu
down to Poke Pad / Night Stretcher / END:

```
plan=TurnPlan(my_prize=4, op_prize=3, prizes_today=0, mode='DEVELOP', ...)
[DBG] ctx=0 opciones=3
[DBG]   #1 idx=2 score=1100      <- END
[DBG]   #2 idx=0 score=-1
[DBG]   #3 idx=1 score=-1        <- the Night Stretcher, vetoed
```

## The asymmetry is what makes it a defect

The **fetch** half of this same card already scores that Grass at 1400, its top
band — `_RULES_NS_GRASS.grass_makes_the_active_ko` — with no archetype guard at
all. It was written for `registro_008` step 85, against this very same Mega
Kangaskhan ex, and `tests/test_night_stretcher_takes_the_energy_that_kos.py`
argues at length why none is needed:

> `_our_effective_damage` applies weakness, resistance, Neutralization Zone and
> the immunities of Crustle / Cornerstone / Drednaw / Sturdy. An unreachable
> target can therefore never make it fire, and **no matchup guard is needed on
> top**.

So the two halves of Night Stretcher were reading one board and disagreeing
about it — and the half that says *no* is the half that runs first. The fetch
table's answer was never asked for, because the card was never played.

## The rule

**A wall is a BODY in the active spot, not a deck list.** A recovery whose payoff
is a proven knockout on the body actually standing there is not an archetype's to
veto: the damage model already answers that exact question for that exact target,
and answers it with a 0 when the wall really is in the way.

## The change

* The four scenarios whose predicate ends in `_our_effective_damage` are
  collected into `_ESC_NS_REMATE_HOY` (main.py) and resolved **alongside**
  whichever list the archetype picks, never instead of it. The Crustle whitelist
  keeps its veto over which **body** comes back; what it no longer does is
  swallow the prize on the table.
* The duplicated archetype guard comes out of `_ns_e_syrup_letal`,
  `_ns_e_finisher_with_active` and `_ns_e_finisher_via_promotion`
  (`ptcg/decision/night_stretcher.py`), which is what makes the fix reach every
  deck rather than this one board.

Deck-agnostic by construction: not one card id is named anywhere in the change.

## The measurement

| | |
| --- | --- |
| **Frozen corpus** | **0 flips in 3 580 decisions** over the committed fifty games. |
| **Non-wall matchups** | Untouched by construction — the `else` branch is unchanged and the three predicates only differ when a wall flag is on. `dragapult_1` at 600 games per arm: **delta +0.0**. |
| **Census** (`utils/census_the_prize_the_wall_does_not_own.py`) | **0.06 flips per game** over 600 games on the five Crustle lists that match the record's opponent — **below the 0.10 the criterion was written at**, and above it on two of the five. |
| **Gate** (`matchup_matrix --base HEAD`, 600 per arm) | `crustle_wall_4` −0.3 · `crustle_wall_11` +2.8 · `crustle_wall_1` −5.0 · `crustle_wall_9` +3.0 · `crustle_wall_8` +4.7. Mean **+1.0 pp** inside a ten-point spread: noise. |
| **The one row that looked like a regression** | `crustle_wall_1` re-run at **1 600 per arm: +1.4 pp** (85.6% vs 84.2%, prize margin +0.05). The −5.0 does not reproduce, and that arm's baseline had itself swung from 87.8% at n=600 to 84.2% at n=1600. |

Per list, from the census:

| list | flips / game | played / game |
| --- | --- | --- |
| `crustle_wall_1` (n=200) | 0.10 | 0.06 |
| `crustle_wall_11` (n=100) | 0.10 | 0.02 |
| `crustle_wall_4` (n=100) | 0.04 | 0.03 |
| `crustle_wall_9` (n=100) | 0.04 | 0.04 |
| `crustle_wall_8` (n=100) | 0.01 | 0.01 |

⚠️ **NEUTRAL in winrate, and it entered below its own census criterion.** That is
recorded rather than argued around. The window is roughly one board in sixteen
games, so even a change that won every one of them could not clear a ±5 noise
floor — which is a statement about what the gate can resolve, not evidence that
the change is worth nothing. What carries it instead: a reproduced lost board, a
line the turn explorer finds on its own, zero corpus flips, and a contradiction
the codebase already documented against itself in the sibling half of the same
card.

Two things the census also says, kept because they are the honest half:

* of 20 boards where a `REMATE HOY` scenario fired, **19** beat the whitelist —
  so on those boards the whitelist had nothing better to offer, and the change is
  never a trade;
* the card is then actually played on only **about half** of them. The rest are
  outranked by the play-order tiers, which is a separate question and is *not*
  touched here.

## Frozen

`tests/test_the_prize_today_is_not_the_walls_to_veto.py`, eleven assertions on
two fixtures out of the record plus four synthetic boards. Three of them fail on
the code as it was. The controls are the point of the file:

* the same board with the target 30 HP out of reach → the recovery goes back to
  being vetoed;
* our ex against an **active** Crustle → vetoed by the damage model returning 0,
  which is what the removed guard was standing in for.

---

Next: [Matchups](matchups.md) · [Tools](tools.md) · [Testing](testing.md)
