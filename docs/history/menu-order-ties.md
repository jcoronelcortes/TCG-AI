# The menu-order ties, opened one class at a time

[← Documentation index](../README.md)

Backlog item 1 of [the night of 7 Aug 2026](night-2026-08-07.md): *"the nine
order-decided MAIN decisions. Attacking or retreating is not a tie."* This is
what they turned out to be, and the one bug that came out of the bottom of them.

## The probe now hands over the board

`utils/permutation_probe.py` reported a percentage and printed ten one-line
samples. A percentage is not a finding: a board nobody can reopen cannot be
arbitrated. It takes `--dump DIR` now (every divergence written out whole, the
observation included) and `--kinds ABILITY,ATTACH` to narrow the dump to one
class. Everything below was read off those files.

## The population

300 mirror games: **246 of 36,868 decisions (0.67%)** decided by the order of the
menu. The percentage is stable across runs (0.56 / 0.65 / 0.67); the per-class
counts are not, because the games are not seeded. Read the classes.

| Class | n | What it is |
| --- | ---: | --- |
| context TO_HAND, CARD | 92 | which card a search brings back |
| **MAIN: ABILITY vs ATTACH** | **52** | a charging ability against the turn's attachment |
| context DISCARD, CARD | 26 | which card is discarded |
| MAIN: ABILITY vs ABILITY | 24 | Teal Dance against Ripening Charge |
| **MAIN: ATTACK vs PLAY** | **13** | attacking against benching a body |
| **MAIN: ATTACK vs RETREAT** | **9** | attacking against pivoting |
| the rest | 30 | singletons, card against card |

## 1. The biggest class is one collision, and it is harmless

The 52 ABILITY-vs-ATTACH ties are a single structural collision. One flag,
`_charge_active_enables_attack`, becomes `SCORE_CHARGE_ACTIVE_ATTACK` (31300) in
three places -- `ptcg/turn/energy.py` for the manual attachment and two branches
of `ptcg/turn/options/ability.py` for the abilities. Two distinct plays, one
number, so the emission order picks.

**And the two plays reach the same board.** Ripening Charge attaches *a Basic {G}
Energy from your hand* and heals 30, so with one Grass in hand both routes put
the same card on the same body; the heal is the only difference, and on 21 of the
24 dumped boards the receiving body is at full HP. On the other three the heal
detector deliberately did not arm, because +30 does not take those bodies out of
the opponent's window.

The last argument for a tie-break was that the order decides which route the turn
*wastes*. Measured over 60 games, 267 of our turns that ended: 94 ended with a
Grass still in hand, 2 with Ripening still on the menu, 7 with the attachment
still open, and **0 with both**. With one Grass the unused route is not waste, it
is unusable. No rule here, and that closes the largest class in the backlog.

## 2. Attacking against retreating: nobody was deciding

On all nine boards the scores are `ATTACK -1`, `RETREAT -1`, `END -10000`. `-1`
is the default: no rule speaks, and the only thing separating the turn from
ending is the veto on END. About one board per 33 games.

With `utils/turn_explorer.py`'s root restricted to each arm, three of the nine
leave real damage on the table (+110, +80, +20), and two of those three are the
same board twice: a Dipplin in front chipping for 100 while a charged Teal Mask
Ogerpon ex waits on the bench.

**But the bigger line is not automatically the right one.** The explorer models
our turn only. Swapping the active for each benched candidate and reading the
agent's own `TurnPlan` on the resulting board, the 210-damage line of the first
board promotes a two-prize ex while they sit on two prizes: `op_wins_next=True`.
The line the explorer calls dominant is the line that hands them the game.

So the arbiter these ties need already exists in the observation and is not
consulted. That is a rule to write, and it needs the defensive half first.

## 3. Following the retreat down: the promotion, and a real bug

The main-menu RETREAT does not name a body -- the promotion is its own decision
two steps later, with its own rules. So the question is not "is the best
candidate safe" but "is the candidate the agent ACTUALLY promotes safe". A census
over self-play reads the plan for every candidate and then watches the real
choice:

```
retreats with a promotion                          502   (300 games)
... promoted a safe body                           500
... promoted a body that lets them WIN               2
... ... with a safe candidate available              1
```

Rare, and the consequence is the whole game. The one board was dumped and
reproduced (`tests/fixtures/mirror_t8_match_point_overrules_the_engine_veto.json`):

    US (4 prizes left)                   THEM (2 prizes left)
    bench  **Meganium 160/160, 4 Grass** active  Hydrapple ex 330/330, 4
           Meowth ex 170/170, 0          bench   Ogerpon ex 210/210, 6
           Meowth ex  50/170, 0                  Ogerpon ex 210/210, 4
           Applin     40/40,  0                  Tapu Bulu, Meganium, Meowth ex
           Teal Mask Ogerpon ex 210, 0

Every ex on our bench is their whole pile. The agent promoted the **Teal Mask
Ogerpon ex at zero energy** -- a two-prize body that cannot even attack -- with a
Meganium at four Grass next to it (one prize, Solar Beam costs two).

Why: `ptcg/turn/options/card.py` protects the Wild Growth engine with a blanket
"the Meganium line does not go active" veto, `score = SCORE_NEVER`, with narrow
exemptions per matchup (Crustle/Cornerstone at four energy, Alakazam,
Neutralization Zone, the forced promotion that finishes). None of them is about
prizes, so in the mirror the veto stands and the only body that answers is
removed from the menu:

```
#1 idx=4 score=193     Teal Mask Ogerpon ex
#5 idx=0 score=-10000  Meganium
```

The rule that should have decided is thirty lines above and had already fired:
*prize denial when promoting* adds +3000 to a body worth fewer prizes than they
still need. `score = SCORE_NEVER` is an assignment, so it overwrote it -- the
project's own recurring shape, a ceiling applied after everything else silently
overriding the rules above it ([Improving the agent](../improving-the-agent.md),
step 4).

**The fix** is one more exemption, written with the same sentence the
prize-denial rule uses (`op_prize <= 2 and prize_count(card) < op_prize`), so the
two halves cannot disagree. It stays as narrow as its neighbours: their pile at
two or less, the Meganium able to attack THIS turn, and its own price leaving
them short. With their pile at ONE it does not fire, because there a one-prize
body hands over the game exactly like the ex -- the sentence the measured rule
already carries.

### Measured

| Gate | Result |
| --- | --- |
| Unit suite | 1608 green (6 new) |
| Golden corpus | **0 flips** |
| 485 real promotions from 300 games, scored with both versions | **0 decisions changed** |

Zero, and the reason is worth writing down rather than hiding. Of those 485
promotions, 57 happen at their match point and 24 also have a Meganium on the
bench -- but only 3 have one charged to its four effective energies, and on all
three the alternative was a body that **finishes the game this turn** (20625
against the 3400 the exemption can reach). A finisher correctly outranks prize
denial: there is no next turn to protect. The exemption only takes over where
nothing wins today, which is exactly the board that motivated it.

So the change is neutral in aggregate and correct on the board it was written
for. It is kept under the project's own exception -- neutral gets reverted
*unless it corrects a value that was demonstrably wrong* -- and a blanket
assignment that overwrites a measured rule and promotes a body the agent's own
projector says loses the game is a wrong value, not a preference.

A self-play A/B was NOT run, deliberately: with 0 decisions changed out of 485,
any winrate difference would be noise measured at some expense.

## What is still open

1. **The attack-vs-retreat arbiter** (§2). The plan's `op_wins_next` has to be
   read against the promotion the agent WOULD make, which §3 now shows how to
   compute.
2. **The other shape of unsafe promotion**: a second census board promoted a
   charged Ogerpon ex at their match point where the only safe bodies were mute
   (a Meganium at zero energy, two Applin). Mute survival against a two-prize
   attacker is a different question, and the project has measured before that
   surviving is not worth it if the survivor cannot answer. It deserves its own
   board, not an extension of this rule.
3. The remaining tie classes: 13 ATTACK vs PLAY, 24 ability against ability.
