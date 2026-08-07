# Matchups

[← Documentation index](README.md)

The agent does not play the same way against every deck. It identifies the
opponent's archetype and turns on rules that only make sense against it. This
page covers how that identification works, what the current results look like,
and where the remaining weaknesses are.

## How the agent identifies the opponent

Two sources, used together:

1. **The board.** The Pokémon in play, the stadium, and the tools attached tell
   us what we are facing. Anything positional — "there is an immune wall in
   front right now", "the sniper is on the bench" — has to come from here,
   because it changes turn by turn.
2. **The opponent's discard pile.** One archetype Pokémon in the discard
   identifies the deck **two or three turns earlier** than the board does. That
   head start is what makes the counter-plan possible: keeping a bench slot in
   reserve, holding disruption for the right moment, committing to a single
   attacker line.

The result is a set of flags — "this is a wall deck", "this is a control deck",
"this is aggro", "the opponent has ability lock in play" — that the scoring
rules read. A rule that is right against one archetype is usually wrong against
another, so most of them are gated on these flags.

> **Careful:** a single tech card in an opposing list does not make it that
> archetype. Turning on a whole matchup plan from one card is a known way to
> lose games you were winning.

## The archetypes we model

| Archetype | What makes it dangerous | Our answer |
| --- | --- | --- |
| **Marnie Grimmsnarl** | Bench damage that snipes our developing line, plus chip damage between turns. | Heal or evolve out of the snipe range; watch the window where a benched body becomes a free prize. |
| **Alakazam** | Damage that scales with the opponent's hand size, and ability pressure. | Strip their hand before the hit lands; keep a one-prize attacker ready; reserve a bench slot. |
| **Crustle Wall** | A front body our ex attackers cannot damage, healed and buffed. | Bring up a non-ex attacker that can hit it; kill the wall before spending resources behind it. |
| **Cornerstone / Cubchoo** | Same immunity problem, plus a body that punishes retreating. | Same relief attacker, with different energy caps — the two plans collide and are tuned together. |
| **Dragapult** | Item lock. Our search cards stop being playable. | Spend the search **before** the lock, digging for what we will play next turn. |
| **Mega Lucario / Mega Lopunny / Mega Kangaskhan / Mega Starmie** | High-prize attackers that kill our ex bodies in one hit. | Trade with one-prize bodies; pivot the fragile ex out. |
| **Mega Starmie**, specifically | The body they show is a 70 HP Staryu that threatens nothing; the body it becomes prints **Nebula Beam 210**, the exact HP of our Teal Mask Ogerpon ex. The damage projector only ever sees Jetting Blow (120), because three energies is more than a Staryu with one can pay — so no "is my active doomed?" reading fires in time. | Named as a **matchup**, not as an arithmetic threshold: on **our first turn**, with no attack available and a 2-prize ex in front, retreat it and put a one-prize body up (`STARMIE_SAC_PROMOTE_ORDER`). Bounded to the opening — see below. |
| **Comfey (mill)** | Wins by decking us out rather than on prizes. | Stop spending draw, commit to a single attacker plan. |
| **Iron Thorns / ability lock** | Turns off our engines entirely. | Play around the lock and treat it as a deck-size limit, not an ability question. |
| **Cynthia Garchomp, Festival Lead, Archaludon, Zoroark, Gardevoir, Greninja, Raging Bolt, Abomasnow…** | Individually rarer. | Targeted rules only where they were measured to matter. |

## Where we stand (7 August 2026)

Measured against the **97 real leaderboard decks** in `deck/real_opponents/`,
rebuilt from the August top-300 download, 400 games per matchup, weighted by how
often each list actually appears:

```bash
python utils/matchup_matrix.py --games 400 --weights
```

```text
EXPECTED LADDER WINRATE (weighted by meta share)
  weighted  : 92.8%   over 99.4% of the meta covered
  unweighted: 91.1%
  PRIZE DIFFERENTIAL, weighted: +3.803 per game
  our forfeits: 0 across all 97 matchups
```

Aggregated by archetype:

| Archetype | Meta share | Winrate | Prize diff. | Ladder points lost |
| --- | ---: | ---: | ---: | ---: |
| **Crustle wall** | 10.2% | **76.8%** | **+1.89** | **2.37** |
| Marnie Grimmsnarl | 38.0% | 95.4% | +4.53 | 1.76 |
| **Ogerpon Verde** | 7.3% | **86.7%** | **+2.38** | 0.97 |
| Alakazam | 18.5% | 95.4% | +3.47 | 0.85 |
| Mega Lucario | 2.2% | 89.6% | +3.21 | 0.23 |
| Mega Starmie | 0.9% | 82.7% | +2.23 | 0.16 |
| Mega Kangaskhan | 2.2% | 93.9% | +4.49 | 0.13 |
| Mega Lopunny | 3.3% | 96.7% | +4.16 | 0.11 |
| *(9 remaining archetypes)* | 14.5% | 93–99% | +4 to +5 | 0.42 |

The previous corpus (5 August, 93 lists) read 93.3% weighted and +3.905. Half a
point of that difference is the field and not the agent: the corpus was rebuilt
in between, four new lists came in, and the agent's only changes since were
readings that flip no decision (golden corpus, 0 flips).

**The worst single list is `crustle_wall_6` at 58.2%, with a prize differential
of -0.22** -- the only matchup in the table where the opponent takes more prizes
than we do. It is a pure stall build: 4 Crustle, 4 Jumbo Ice Cream, 4 Cook,
3 Waitress, 13 Grass, and two Teal Mask Ogerpon ex as the only other attacker. No
Boss's Orders, no Kangaskhan. Against it, `utils/healing_census.py` reports that
**83% of the damage we deal is healed back** before it becomes a prize.

### Reading the table

**Crustle wall is the real weakness, not Marnie.** Marnie costs more ladder
points only because it is 38% of the field; we beat it 95% of the time. Crustle
is 10% of the field and we win 77%. Three independent signals point at it: the
worst winrate, the worst prize differential (games decided narrowly — which is
exactly where a new rule can move the needle), and **18** distinct lists, so it
is the archetype and not one odd deck.

Two corpus refreshes in a row have **widened that gap instead of closing it**.
Nothing about the agent changed between the runs — the field did. Crustle went
8.7% → 10.0% → 10.2% of the meta while Marnie fell 43.4% → 39.0% → 38.0%, so the
archetype we win least is the one gaining ground.

**Ogerpon Verde is the second real hole** (86.7%, and it lost three points on
the refresh even as its share fell), invisible in a
winrate-sorted list because it weighs so little. Its share has moved 4.2% →
8.3% → 7.3% across the three corpora and the matchup itself has now given back
the four points it had gained, so it costs about one ladder point either way.

**Winrate alone stops resolving once it saturates.** Above ~94% the generic
opponent bot is the limiting factor. The **prize differential** keeps
discriminating there, because a game can be won without taking all six prizes —
it measures something else, not a disguised winrate.

**Zero forfeits in 38,800 games** means the agent never crashed and never chose
an illegal option against any real list.

**The meta is measured almost whole.** The screening admitted 97 of the 98
unique lists, so the weighted figure covers 99.4% of the field. The one rejection
is an N's Zoroark ex build the generic bot cannot start (13% for the bot against
itself, which measures the bot and not the matchup). When a list is rejected the
average is quietly computed over a hole; the hole is one list wide.

**Three of the 97 are near-copies of our own list** (two Festival Lead at 52 and
57 cards in common, one Ogerpon Verde at 47). Against those the bot is piloting
our engine rather than an opposing deck, and it plays it badly, so they come back
at 94–98%. They are kept — people do play them — but they flatter one archetype:
dropping them moves Ogerpon Verde from 86.7% to **86.2%** and its prize
differential from +2.38 to **+2.27**, which is the number to reason with. The
overall figure barely notices (92.78% → 92.75%), because together they are 0.9%
of the field — a third of what they were in the previous corpus.

### "We cannot attack" is not a rare board — hiding the ex is bounded to the opening

The Mega Starmie rule above is gated on `not can_attack`, and the first version
of it stopped there. Instrumented over 300 games it fired **9.8–11.4 times per
game**, spread over turns 2, 4, 6, 8, 10, 12 and beyond: a turn with no attack
available is simply what a developing turn looks like, and every firing discards
an energy to put a 40 HP body in front of a deck that is glad to take it.

Measured with two arms that differ only in `AGENT_STATE.op_is_starmie_deck`,
n=1000 per arm, control `alakazam.csv` (a deck the rule cannot fire against) at
−0.5 points / +0.01 prizes:

| Scope | `mega_starmie_1` | `mega_starmie_2` |
| --- | ---: | ---: |
| rule OFF | 88.3% (+2.95) | 88.6% (+2.66) |
| every turn we cannot attack | 84.0% (+2.41) | 81.3% (+1.97) |
| **our first turn only** | **88.5% (+2.90)** | **85.7% (+2.48)** |
| no-surplus-fee discriminant, any turn | 81.8% (+2.25) | 81.6% (+2.05) |

The shipped scope is our first turn: three independent runs put it inside the
control's band (+0.0/−0.7 points, −0.13/−0.10 prizes on the confirming run) and
it fixes the decision the rule was written for (`registro_002` step 28). The
general lesson is the first row of the table: a defensive rule gated only on "we
cannot attack" is not an opening rule, it is a per-turn tax.

## Cards we deliberately do not model

A card-by-card audit of the top archetypes (August 2026) found:

- **Nighttime Mine** (Alakazam lists) raises the attack cost of our Tera
  attacker. This was a **real bug** — the agent thought its attacker was ready,
  planned the attack, and the turn died. Fixed by recomputing attack costs once
  per decision. Winrate impact: neutral; kept because the number was
  demonstrably wrong, not because it was a hypothesis.
- **Handheld Fan** (moves energy off our attacker) exists in ~5% of the meta.
  Not implemented.
- **Marnie's engine** was already fully modelled; the rest of its cards are
  opponent consistency and do not touch us mechanically.
- **Crustle's package** (extra-HP tools, healing, effect-blocking energy) is not
  a blind spot: the HP we read already includes the buffs, and the effect-blocker
  stops effects, not damage. The matchup is hard by construction.
- **Cynthia's Roserade** was reviewed and skipped: the archetype is ~5% of the
  meta and we already win 97.6% of it with a +4.61 prize differential.
- **Comet Punch** (Team Rocket's Kangaskhan ex) flips four coins for 30 each.
  Left out with the rest of the coin flips: the expected value is computable,
  the damage is not. Its three companions from the same corpus refresh — Mega
  Symphonia, Verdant Storm and Buddy Blast — *were* implemented, because their
  scale is sitting on the board where the agent can read it. See
  `ptcg/cards/op_scaling.py`.

> One method note worth keeping: searching for a card ID inside the source gives
> **false negatives** — card IDs and attack IDs are different namespaces, and a
> "known" ID once turned out to be an attack. The only real bug in that audit was
> found by reading opposing lists by hand.

## Abilities that change what their attack does

Attacks that scale with the board live in `ptcg/cards/op_scaling.py`. A second,
smaller family changes the damage without touching the attack at all: an
**ability on the attacker** that adds a flat amount while some visible condition
holds. These are modelled inline in the opponent-damage projector, next to the
tools that do the same thing, because the bonus is flat, readable and lands
before weakness.

**Okidogi's Adrena-Power** is the one currently modelled: while it holds a
Darkness Energy its attack does 100 more to our active — an attack printed at 70
arriving as 170, or 340 against a body weak to Fighting. Two traps came with it,
and both are the same trap:

- the ability *also* grants +100 HP, and the engine already applies that. We read
  the HP it sends and never recompute it;
- the Darkness Energy does not have to be a basic one. **Prism Energy** provides
  every type on a Basic Pokémon, and the engine reports it as rainbow — which is
  exactly how the only list in the repo running Okidogi switches the ability on.
  Matching on "basic Darkness Energy" would have been blind to it.

See [the simulator layer](simulator.md) for the general rule both traps come
from: the observation already carries whatever the engine resolved.

**Still open:** a *different* Okidogi in the card pool has an attack that scales
with the prizes we took last turn. It is unmodelled, and the census gate in the
test suite is red because of it — that is the gate doing its job.

---

Next: [Improving the agent](improving-the-agent.md) · [Tools](tools.md)
