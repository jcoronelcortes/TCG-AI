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
| **Festival Lead** | 4.3% of the field across 11 lists, and several of them are near-copies of our own sixty. The shared stadium that evolves for free arms *both* sides. | We beat it 97.5%. The rule worth knowing is that the stadium they brought also arms our Dipplin. |
| **Team Rocket Mewtwo** | New in the August corpus: 5 lists, 2% of the field. | No dedicated plan; 95.3% on the general machinery. |
| **Cynthia Garchomp, Archaludon, Zoroark, Gardevoir, Greninja, Raging Bolt, Abomasnow, Chandelure…** | Individually rarer. | Targeted rules only where they were measured to matter. |

## Where we stand (11 August 2026)

Measured against the **87 real leaderboard decks** in `deck/real_opponents/`,
rebuilt from the 9 August top-300 harvest, 400 games per matchup, weighted by how
often each list actually appears:

```bash
python utils/matchup_matrix.py --games 400 --weights
```

```text
EXPECTED LADDER WINRATE (weighted by meta share)
  weighted  : 94.0%   over 99.5% of the meta covered
  unweighted: 91.4%
  PRIZE DIFFERENTIAL, weighted: +3.853 per game
  our forfeits: 1 across 34 800 games
  weakest matchup: crustle_wall_5 at 69.8%
```

Aggregated by archetype (shares from `deck/real_opponents/pesos.csv`):

| Archetype | Meta share | Lists | Winrate | Prize diff. | Ladder points lost |
| --- | ---: | ---: | ---: | ---: | ---: |
| **Crustle wall** | 10.0% | 16 | **77.4%** | **+1.92** | **2.25** |
| Alakazam | 19.0% | 11 | 94.3% | +3.31 | 1.08 |
| Marnie Grimmsnarl | 36.0% | 9 | 97.6% | +4.55 | 0.88 |
| **Ogerpon Verde** | 5.0% | 8 | **88.8%** | **+2.66** | 0.56 |
| Mega Lopunny / Mega Froslass | 8.0% | 1 | 96.2% | +4.07 | 0.30 |
| Mega Lucario | 3.3% | 4 | 92.5% | +3.30 | 0.25 |
| Festival Lead | 4.3% | 11 | 97.5% | +4.59 | 0.11 |
| Team Rocket Mewtwo | 2.0% | 5 | 95.3% | +4.13 | 0.09 |
| Mega Kangaskhan | 1.3% | 4 | 93.3% | +4.24 | 0.09 |
| **Mega Starmie** | 0.7% | 2 | **87.1%** | **+2.52** | 0.08 |
| *(8 remaining archetypes)* | 9.9% | 16 | 91–99% | +3.3 to +5.2 | 0.20 |

The previous corpus (7 August, 97 lists) read 92.8% weighted and +3.803. Both
halves of the field and the agent moved in between, so the two figures are not a
clean before/after: sixty lists changed, sixteen disappeared and six are new.
The retired corpus is kept as `deck/real_opponents_2026-08-07/`, because a
finding written against a list is only reproducible while that list exists.

**The worst single list is `crustle_wall_5` at 69.8%**, and `crustle_wall_6` is
the one with almost no prize differential left (+0.05). That family is a pure
stall build — Crustle behind healing and buff tools, with two Teal Mask Ogerpon ex
as the only other attacker. Against those lists `utils/healing_census.py` reports
that a large majority of the damage we deal is healed back before it becomes a
prize; on the worst list of the previous corpus it was **83%**.

### Reading the table

**Crustle wall is the real weakness, not Marnie.** Marnie is 36% of the field
and we beat it 98%. Crustle is 10% and we win 77%. Three independent signals
point at it: the worst winrate, the worst prize differential — games decided
narrowly, which is exactly where a new rule can move the needle — and **16**
distinct lists, so it is the archetype and not one odd deck.

Three corpus refreshes in a row have **widened that gap instead of closing it**,
and mostly because the field moved rather than the agent: Crustle went
8.7% → 10.0% → 10.2% → 10.0% of the meta while Marnie fell 43.4% → 39.0% → 38.0%
→ 36.0%. The archetype we win least is the one holding ground while the one we
beat recedes.

**Ogerpon Verde and Mega Starmie are the other two real holes** (88.8% and
87.1%), invisible in a winrate-sorted list because they weigh so little
together.

**Winrate alone stops resolving once it saturates.** Above ~94% the generic
opponent bot is the limiting factor. The **prize differential** keeps
discriminating there, because a game can be won without taking all six prizes —
it measures something else, not a disguised winrate.

**One forfeit in 34 800 games**, against `mega_kangaskhan_1`. It is the first in
several corpus generations; every other list is clean, meaning the agent never
crashed and never chose an illegal option.

**The meta is measured almost whole.** The screening admitted 87 of the 88 unique
lists, so the weighted figure covers 99.5% of the field. The one rejection — an
N's Zoroark ex build the generic bot cannot start — sits in
`deck/real_opponents/no_pilotables/`. An unpilotable list measures the bot
getting stuck, not the matchup, and returns a falsely high winrate.

**Some of the lists are near-copies of our own sixty.** `pesos.csv` records the
overlap per list in its `solape_propio` column, and two Festival Lead builds
share 52 and 60 cards with us. Against those the bot is piloting *our* engine
rather than an opposing deck, and it plays it badly, so they read as matchups we
dominate. They are kept — people do play them — and flagged, so the aggregation
can report the field with and without.

### The seat: we now take the first turn (August 2026)

**There is no coin flip in this engine.** The `IS_FIRST` select is offered to
**seat 0, every game** — measured over 30 openings, `yourIndex` was 0 in all of
them and the seat that answered became `firstPlayer` in all of them. Whoever
sits at index 0 decides for both players; the randomisation lives in the seat
assignment, not in the engine.

Our agent now answers **YES** (`ptcg/turn/options/minor.py`): when the prompt
reaches us, this deck takes the first turn. It reverses the earlier policy of
declining — defensible under current rules, where the second player may attack
on their first turn — on the deck owner's call.

**Every number recorded before that switch is the going-second half of the
game.** The reference bot also answers YES, so with our old veto it took the
first turn in 60 of 60 matchup games, and every branch reading
`we_go_first == True` was code self-play never executed. Since `torneo`
alternates seats, matchup runs now split the first turn ~50/50 instead — 100/100
over 200 games against `crustle_wall_1` — so seat is no longer held constant
across a comparison. Use `OpponentBot(first_choice="second")` to pin it.

The reading that preceded the switch, with the bot declining so the seat was
decided inside a single run. 800 games per deck, six decks:

| Deck | Going first | Going second | Δ |
| --- | ---: | ---: | ---: |
| crustle_kangaskhan | 79.00% | 68.00% | **+11.00** |
| marnie_grimmsnarl | 94.25% | 89.50% | +4.75 |
| alakazam | 99.50% | 99.25% | +0.25 |
| dragapult | 98.00% | 97.75% | +0.25 |
| cynthia_garchomp | 98.75% | 99.00% | −0.25 |
| festival_lead | 98.50% | 99.25% | −0.75 |
| **aggregate** | **94.67%** | **92.12%** | **+2.54** |

And then the weighted matrix said no. At matched n over the 87 real lists, the
same flag is worth **+1.0 point unweighted and +0.2 weighted**, with the prize
differential moving +3.882 → +3.998.

Both readings are the same fact from two directions, and it is the one this
project keeps having to relearn: **the gain is real and the meta does not contain
it.** Going first is worth eleven points against Crustle, and Crustle is 2% of
the ladder by weight; 31% of it is a single Marnie list where we already win 98%
and there is no room. So this is a change to make for the hard matchups and to
measure on the hard matchups — not a ladder-winrate play.

A latent defect used to sit in the same lines and is worth knowing about:
`AGENT_STATE.we_go_first` was assigned while each option was **scored**, not
when one was chosen, so its value was whatever the last-scored option wrote — it
came out right only because the menu happens to list YES before NO. Both writes
are gone, and `utils/lint_architecture.py` R9 keeps any scorer under
`ptcg/turn/options/` from writing to `AGENT_STATE` again. The flag has exactly
one honest writer: `agent()`, reading `firstPlayer` off the board.

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
- **Cynthia's Roserade** was reviewed and skipped once, on the grounds that we
  already won 98% of the archetype — and then a real game showed a Gabite whose
  Dragonslice prints 40 taking 70 off a Tapu Bulu that had 70 left. The extra 30
  was the Roserade on their bench. It is now in `OP_TEAM_DAMAGE_BUFF`, together
  with Hop's Snorlax, and `utils/op_buff_census.py` audits that table. A winrate
  we already win is not evidence that a reading is right.
- **The coin-flip family** is left out on purpose, and the census makes each
  exclusion state its reason: Comet Punch (four coins for 30 each), Continuous
  Headbutt and Rapid-Fire Combo flip; Erasure Ball and Bellowing Thunder scale
  with how much energy the *opponent* chooses to discard. The expected value is
  computable in every case; the damage is not.
- **Everything else scaling is modelled.** `utils/op_scaling_census.py` currently
  reports 14 modelled, 5 excluded with a written reason, and **0 unmodelled**
  across every opposing deck in the repository. The suite runs it as a gate, so
  a corpus refresh that brings in an unread scaling attack turns it red.

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

There are two of them, and the split is deliberate. An ability on the **attacker
itself** goes in `OP_ACTIVE_ABILITY_DAMAGE`; an ability on a body sitting on
**their bench** that boosts the whole team goes in `OP_TEAM_DAMAGE_BUFF`. Both
tables live in `ptcg/cards/ids.py` and both are audited by
`utils/op_buff_census.py`.

**Okidogi's Adrena-Power** is the self-buff currently modelled: while it holds a
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

A *different* Okidogi in the card pool (a different card ID, same name) has an
attack that scales with the prizes we took last turn. It was the last entry in
the unmodelled bucket, and it is no longer in any opposing list in the
repository — which is why the census gate is green today and will say so again
the moment a refresh brings the card back.

---

Next: [Improving the agent](improving-the-agent.md) · [Tools](tools.md) · [The instruments](instruments.md)
