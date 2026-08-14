# The reversible bet: the promotion that gave the turn away

[← Documentation index](README.md) · [the other Marnie autopsy](marnie-la-cosecha-fuera-de-mesa-2026-08-14.md)

**Game**: episode 93022181, `records/registro_006_pasos_067_hasta_094.json`,
turn 6, against Marnie's Grimmsnarl ex. **Lost.**

Their Grimmsnarl ex knocked our active Teal Mask Ogerpon ex out and the menu of
step 94 asked which body comes up.

## The board when we chose

| | |
| --- | --- |
| **Our active** | — (just knocked out) |
| **Our bench** | Meganium 130/160, **0 energy** · Teal Mask Ogerpon ex 180/210, **2 effective** · Teal Mask Ogerpon ex 180/210, **2 effective** · Tapu Bulu 140/140, **0 energy** |
| **Our prizes** | 5 |
| **Their active** | Marnie's Grimmsnarl ex, **310/320**, 2 Darkness |
| **Their prizes** | 3 |
| **Hand** | Teal Mask Ogerpon ex · Hydrapple ex (no Grass, no Supporter) |
| **Deck** | 8 of the list's 14 Basic Grass still unseen |

The agent promoted the **Tapu Bulu**: 8514 against the Ogerpon's −1314.

## What the board was worth

### The knockout was one attachment away

Grimmsnarl ex is **weak to Grass**, Meganium's Wild Growth was on the bench — so
each attachment is worth **two** — and Myriad Leaf Shower is
`30 + 30 × (our active's energy + their active's energy)`:

| Grass on the Ogerpon | Base | Doubled by weakness | KO on 310? |
| --- | --- | --- | --- |
| 2 (as it stood) | — (below the cost of 3) | — | no |
| **4 (one attachment)** | **210** | **420** | **yes** |

Two prizes, on our turn, before they could answer — and the body that took them
is the one their deck cannot trade with cheaply.

### The Tapu Bulu could do nothing, and did nothing

Wood Hammer costs four and it carried zero; its retreat costs three and it
carried zero. It is a body that neither attacks nor steps aside.

Turn 7 opened by drawing a **Bug Catching Set**, which fetched **two Basic
Grass**. Both went to benched Ogerpon. The turn ended with **no attack**, and
the game went with it.

## Why every rule stayed silent

`_promote_setup_ko_attacker` is the rule for exactly this shape — "promote the
body that is ONE attachment from a lethal hit rather than a mute wall" — and it
knew five ways to get that attachment. All five were dead:

| Route | What it needs | On this board |
| --- | --- | --- |
| (a) | Lillie's / Dawn in hand | hand was two Pokémon |
| (b) | Lana's Aid in hand + Grass in discard | no Lana's Aid |
| (c) | the Meowth ex engine | no Meowth ex |
| (d) | Fezandipiti ex → Flip the Script | none in play or hand |
| (e) | the turn's own draw, **at our match point** | our pile was at five |

With no route the slot went to `_ko_prefer_basic_general` — "if their blow kills
even our biggest tank, hand over a cheap 1-prize body" — which scores the wall
by hit points and never asks whether it can act.

## What changed: route (f), the reversible bet

Every one of routes (a)–(d) asks the board to **guarantee** the missing energy.
This board is the one that shows the guarantee was never the thing being paid
for:

- the promotion resolves at the **end of their turn**, so nothing touches the
  promoted body before we act;
- if the draw brings the Grass, we take two prizes;
- if it does not, the Ogerpon **retreats** — cost 1, and it carries two — and
  the wall comes up *then*, before their reply.

A failed bet costs one energy card and a turn the mute wall was going to waste
anyway. So the top card of the deck is a route whenever the bet stays
**reversible**, which is what `_ps_keeps_its_way_out` already asked of route (d)
and what the new `PROMOTE_REVERSIBLE_BET` asks of every board:

```text
_ps_reversible_draw_bet = grass still unseen
                          and not a wall matchup (Crustle/Sylveon/Cornerstone/Iron Thorns)
```

plus, in the candidate loop, the exit test itself — now asked through
`_retreat_payable`, which counts the bill in **cards** rather than symbols
(with Wild Growth a single Grass pays two).

A third guard was written and then deleted: *"a body still on the bench after
the promotion, or there is nothing to retreat into"*. It is true and it can
never change a decision — the only board it excludes is a bench of one, where
the menu offers a single option and the answer is forced. The **mutation gate**
is what said so out loud: two survivors on that line, no test in the repository
able to watch it. Deleting it took the gate back to zero survivors.

Route (d) — the three cards of Flip the Script — becomes the special case of
this one.

## What it measures

| Instrument | Result |
| --- | --- |
| Golden corpus (`records/`) | **1 flip**: this step, Tapu Bulu → Ogerpon ex |
| Frozen corpus (3 580 decisions, 50 games) | **2 flips**, both the same sentence: a body one attachment from a knockout coming up instead of a mute wall |
| Firing census, 600 games / 4 matchups | 210 forced promotions, **1 changed** — the rule is rare by construction |
| Self-play vs the Marnie bot, paired seeds, n=3 000/arm | **2 795 vs 2 796 wins** — no signal, and none was available |
| Self-play vs Dragapult / Festival Lead, n=2 000/arm | identical |
| **Rules oracle, K=100 per batch, two independent runs** | **3 boards, 3 in favour, 0 against, both times.** This step: **+15 pp / +1.03** (floor 3 pp / 0.52) and **+11 pp / +1.28** (floor 2 pp / 0.26). The other two: +12/+1.65 and +15/+1.63, +2/−0.08 and +3/+0.50 |

**The winrate cannot see this rule and says so honestly**: a decision that
changes twice in a thousand games is invisible to a scoreboard that saturates at
93 % against the bot. What grades it is
`utils/oracle_the_promotion_bets_when_it_can_walk_back.py`, which rolls the two
options forward under the engine's own rules — and on the board this was written
from, betting is worth eleven to fifteen points of winrate and a full prize of
margin. The two runs are quoted rather than one because the search API is not
seeded: the oracle is an estimator, and a single batch is a sample of it.

Marked as **NEUTRAL in winrate, entered on the census and the oracle**, the same
standing the Cornerstone and Ultra Ball rules carry.

## Pinned by

- `tests/test_the_promotion_bets_when_the_bet_is_reversible.py` — the board, the
  arithmetic, the decision, and two controls: exhaust the Grass and the wall
  comes back; take the exit away and so does the bet.
- The controls of three older tests moved with it: "no draw engine" stopped
  being the same sentence as "no way to the energy", so each now switches the
  copies off as well.
