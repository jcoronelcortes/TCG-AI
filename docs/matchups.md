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
| **Marnie Grimmsnarl** | Bench damage that snipes our developing line, plus chip damage between turns. **And the threat is not the ex.** Marnie's Grimmsnarl ex is 320 HP and **weak to Grass**, so a charged Teal Mask Ogerpon ex on our bench already reads 300–420 against it; what nothing answers is the two abilities no evolution step controls — Froslass's *Freezing Shroud* (20 a round to our whole board, because every body of ours has an ability) and **Munkidori's *Adrena-Brain*, worse because it aims**: 30 counters moved wherever they close a knockout, reloaded every checkup by their own Froslass. | Heal or evolve out of the snipe range; watch the window where a benched body becomes a free prize. And when the bench already covers the Stage 2, **gust the engine and not the line** — charged Munkidori first, then Froslass, then a bare Munkidori. Three pages, three switches: [the engine before its line](marnie-the-engine-goes-before-its-line-2026-08-16.md), [the energy and not the HP](marnie-the-gust-reads-the-energy-not-the-hp-2026-08-16.md), [the bare line](marnie-the-bare-line-asks-nothing-of-the-reserve-2026-08-16.md). |
| **Alakazam** | Damage that scales with the opponent's hand size, and ability pressure. **The threat is deferred**: with their hand small the *Powerful Hand* projection can be 80 against a 330 HP body, and what to fear is the hit the Abra → Kadabra → Alakazam line assembles afterwards. | Strip their hand before the hit lands; keep a one-prize attacker ready; reserve a bench slot. The defensive pivot is priced off the **canonical projection**, not the immediate reply — and it only pays when the corpse it avoids is actually on offer; then the promotion that follows gets the same list that justified the retreat. See [The front seat vs Alakazam](alakazam-the-pivot-promotes-the-body-it-pays-for-2026-08-16.md). |
| **Crustle Wall** | A front body our ex attackers cannot damage, healed and buffed. | Bring up a non-ex attacker that can hit it; kill the wall before spending resources behind it. |
| **Cornerstone / Cubchoo** | Same immunity problem, plus a body that punishes retreating. | Same relief attacker, with different energy caps — the two plans collide and are tuned together. |
| **Milotic ex / Sylveon** | **Two walls in one list, and they blank different bodies.** Sylveon cancels our *ex*; Milotic ex's Sparkling Scales cancels our *Tera* — the Teal Mask Ogerpon ex the deck is built to charge — and nothing else. In **0 of the 408** corpus lists, and met on ladder. | Read the wall off the **attacker property**, not the archetype: against the Milotic every non-Tera body of ours hits for full, so retreat the Ogerpon and promote whatever is loaded. See [The wall that reads our Tera](milotic-the-wall-that-reads-our-tera-2026-08-16.md). |
| **Dragapult** | Item lock. Our search cards stop being playable. | Spend the search **before** the lock, digging for what we will play next turn. |
| **Mega Lucario / Mega Lopunny / Mega Kangaskhan / Mega Starmie** | High-prize attackers that kill our ex bodies in one hit. | Trade with one-prize bodies; pivot the fragile ex out. |
| **Mega Starmie**, specifically | The body they show is a 70 HP Staryu that threatens nothing; the body it becomes prints **Nebula Beam 210**, the exact HP of our Teal Mask Ogerpon ex. The damage projector only ever sees Jetting Blow (120), because three energies is more than a Staryu with one can pay — so no "is my active doomed?" reading fires in time. | Named as a **matchup**, not as an arithmetic threshold: on **our first turn**, with no attack available and a 2-prize ex in front, retreat it and put a one-prize body up (`STARMIE_SAC_PROMOTE_ORDER`). Bounded to the opening — see below. |
| **Comfey (mill) / Chandelure** | Wins by decking us out rather than on prizes — **and buys a wall that is not on the board.** Acerola's Mischief makes one of their bodies immune to our ex for one turn, on a precondition ("2 or fewer Prize cards remaining") that lands it exactly on the turns that end the game. | Stop spending draw, commit to a single attacker plan; and read the shield off the `PLAY` log of their turn, pinned to a **serial**, so the answer is to gust the protected body away. See [Strategy §12.3](strategy.md). |
| **Mesprit / Uxie / Azelf (Neutralization Zone)** | A bench of 70 HP bodies with no Rule Box under a stadium that makes every ex of ours do zero to them. The wall is the *absence* of something, so it comes and goes with their promotion. | Route the energy to a non-ex that can still take a prize — the Meganium line above all. See [Strategy §12.2](strategy.md). |
| **Iron Thorns / ability lock** | Turns off our engines entirely. | Play around the lock and treat it as a deck-size limit, not an ability question. |
| **Festival Lead** | 4.3% of the field across 11 lists, and several of them are near-copies of our own sixty. The shared stadium that evolves for free arms *both* sides. | We beat it 97.5%. The rule worth knowing is that the stadium they brought also arms our Dipplin. |
| **Team Rocket Mewtwo** | New in the August corpus: 5 lists, 2% of the field. | No dedicated plan; 95.3% on the general machinery. |
| **Mega Lopunny / Mega Froslass** | Their Froslass drips a damage counter onto **every** Pokémon with an ability at each checkup — including their own Grimmsnarl ex, which is why the drip is also *ours* to count. **And Mega Froslass ex prints 0**: *Resentful Refrain* is 50 per card of **our** hand, so the body that looks harmless on the card is the one that ends the game. | Count the checkups into the HP the attack has to cover ([Strategy §2.1](strategy.md)). Its remaining losses are **starvation, not misplay** — 12 000 games per arm put the code's contribution at ±0.1 pp. At **their** match point, read the scaled reply and give the seat to a body that survives it: [The seat that hands the game over](froslass-the-seat-that-loses-the-game-yields-to-the-wall-2026-08-16.md). |
| **Archaludon** | A body big enough that our answer to it is a single charged ex, which their pile then makes a match-point target. | The match-point veto yields to a finisher that can pay its own retreat: their blow arrives a turn of ours later, so a body that can step aside is not there to receive it. |
| **Cynthia Garchomp, Zoroark, Gardevoir, Greninja, Raging Bolt, Abomasnow…** | Individually rarer. | Targeted rules only where they were measured to matter. |

## Where we stand (14 August 2026)

Measured against the **500 leaderboard decks** harvested on 12 August
(`deck/real_opponents_500/`, 133 admitted lists carrying their meta weight), with
the seeded engine and the game budget spread by meta share:

| Weighting | Ladder winrate | Prize differential | Lists carrying weight |
| --- | ---: | ---: | ---: |
| **The field** (all 500) | **95.4 %** ±0.17 | +4.172 | 133 |
| The field, on the 13 Aug list | 94.50 % ±0.19 | +4.063 | 133 |
| The top-100, on the 13 Aug list | 95.81 % ±0.25 | +4.179 | 38 |

**We do better at the top of the ladder than in the field**, which is not a
paradox: the field is weighted toward the two matchups we struggle in, while the
top-100 is weighted toward decks we beat almost freely. Climbing and holding are
different problems, and a field average quietly answers the second one. Both
weightings are reported for every headline; `utils/top100_weights.py` builds the
second one and `utils/reweight_matrix.py` applies it to a saved run without
replaying a game.

**Two things moved on 13–14 August and they are measured apart.** `deck.csv`
changed (−1 Tapu Bulu, −1 Night Stretcher, +1 Poké Pad, +1 Basic Grass) and the
day shipped thirteen rule commits. The four cards are worth **+0.59 pp
[+0.34, +0.84]** and the thirteen commits a further **+0.36 pp [+0.10, +0.63]** —
never added together, because they were measured in three arms for exactly that
reason.

The two hard matchups, and they are hard the same way. These rows and everything
below them were measured on the **13 August** list, so the winrates move a little
with the four cards above and the ranking does not:

| | Field share | Winrate | Prizes | Going first | Going second | Seat gap |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| **crustle_wall** | 8.23 % | **80.0 %** | **+2.32** | 83.2 % | 76.8 % | **+6.4 pp** |
| **ogerpon_verde** | 6.22 % | **85.4 %** | **+2.14** | 88.1 % | 82.8 % | **+5.3 pp** |
| *everything else* | — | 92–99 % | +2.7…+5.3 | — | — | ≈ +1 pp |

Lowest winrate, lowest prize differential and the largest seat dependence are
**the same two archetypes on all three axes**: these are the matchups where the
game is decided by tempo, and tempo is what the seat buys. Where the winrate is
saturated the seat is worth about a point; where the game is contested it is
worth five or six. Which of the two to work on depends on the goal — Crustle Wall
is the field's biggest leak and nearly absent from the top-100 (8.23 % → 2.02 %),
while **Ogerpon Verde does not shrink** (6.22 % → 6.06 %) and is the top-100's
biggest leak.

**Zero forfeits in 53 181 games**, including the ~26 590 games' worth of
`we_go_first == True` branches that no self-play had ever executed before the
seat policy reversed.

**What the 500 decks bought, and what they did not.** The same code against the
old 87-list corpus and the new 133-list one reads 94.6 % / +4.063 and 94.50 % /
+4.063 — the headline did not move and the prize differential is identical to
three decimals. For *how good are we*, the 500 bought a slightly tighter
interval and nothing else, and no past verdict needs relabelling on corpus
grounds. For *what should we work on*, it changed the answer: the old corpus did
not under-measure Crustle Wall, it **fragmented the archetype** across too few
lists to see its total weight.

The full playbook, including how to pilot each matchup, is
[Playbook against the meta](playbook-vs-meta-2026-08-13.md) — read its own
superseded-in-three-places banner first.

### The previous reading (11 August 2026), kept for comparison

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

#### Reading that table

The conclusion below survived the corpus rebuild — Crustle Wall is still the
biggest leak, and the archetype-level aggregation of the 500 made it *larger*,
not smaller.

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

Re-measured on the list of 14 August the seat is worth **+1.04 pp ±0.37**, half
of the +2.08 pp ±0.37 the previous list read — two intervals that do not
overlap. The direction is unchanged and so is the reading below.

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
- **The wall is a BODY, not the deck list it came in.** `op_is_crustle_deck` and
  `op_is_cornerstone_deck` are the right reading for *which body is worth
  recovering or searching for* against a wall, and the wrong one for *is this
  particular knockout available* — a Crustle list spends most of its turns with
  something else in front, and the damage model already returns 0 when the wall
  really is in the way. One archetype guard of that second kind cost a game:
  [The prize the wall does not own](crustle-the-prize-the-wall-does-not-own-2026-08-15.md).
  Worth checking whenever a new `op_is_*_deck` branch is added — and a second
  archetype guard of that kind cost the *charging* rules a rules-oracle grade of
  3 for / 6 against before being narrowed to `_ctm_wall_in_the_way`:
  [Meganium is an attacker, not the doubler](crustle-meganium-is-an-attacker-not-the-doubler-2026-08-15.md).
- **Against this wall the charging order is the order of the ATTACK**: Tapu Bulu
  (Wood Hammer 220), then **Meganium** (Solar Beam 140, and 160 HP survives their
  Superb Scissors), then Dipplin (20 per benched body, 80 HP). Meganium used to
  sit last on the grounds that it is the Wild Growth doubler — true against
  Cornerstone, which blanks the bodies *with an Ability*, and false against
  Crustle, which blanks the ones with a *rule box*. And the corollary the same
  write-up records: **a second ex charged against the wall that blanks ex buys
  nothing**, while the one non-ex we own sits at zero.
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

Attacks that scale with the board live in `ptcg/cards/op_scaling.py`. **The table
being right is not the same as the agent reading it**: the scaled read is
**opt-in**, and on 16 August 2026 a game was lost because no defensive rule asked
for it — *Resentful Refrain* projected as **zero**, so `active_ko_likely` was
False and no pivot in the file could see the knockout coming. When a rule only
speaks because not moving loses the game, it reads `scaled=True`; the same flag
measured **negative** in the ninety-odd places whose failure mode is going
passive, and that split is deliberate. See [the write-up](froslass-the-seat-that-loses-the-game-yields-to-the-wall-2026-08-16.md).

A second,
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
