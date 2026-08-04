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
| **Comfey (mill)** | Wins by decking us out rather than on prizes. | Stop spending draw, commit to a single attacker plan. |
| **Iron Thorns / ability lock** | Turns off our engines entirely. | Play around the lock and treat it as a deck-size limit, not an ability question. |
| **Cynthia Garchomp, Festival Lead, Archaludon, Zoroark, Gardevoir, Greninja, Raging Bolt, Abomasnow…** | Individually rarer. | Targeted rules only where they were measured to matter. |

## Where we stand (August 2026)

Measured against the **89 real leaderboard decks** in `deck/rivales_reales/`,
400 games per matchup, weighted by how often each list actually appears:

```bash
python utils/matriz_matchups.py --partidas 400 --pesos
```

```text
EXPECTED LADDER WINRATE (weighted by meta share)
  weighted  : 93.1%   over 98.8% of the meta covered
  unweighted: 92.0%
  PRIZE DIFFERENTIAL, weighted: +3.905 per game
  our forfeits: 0 across all 89 matchups
```

Aggregated by archetype:

| Archetype | Meta share | Winrate | Prize diff. | Ladder points lost |
| --- | ---: | ---: | ---: | ---: |
| **Crustle wall** | 8.7% | **75.3%** | **+1.94** | **2.15** |
| Marnie Grimmsnarl | 43.4% | 95.4% | +4.56 | 2.01 |
| Alakazam | 19.1% | 95.4% | +3.40 | 0.88 |
| Ogerpon Verde | 4.2% | **85.8%** | **+1.99** | 0.60 |
| Mega Lucario | 1.8% | 86.5% | +2.85 | 0.24 |
| Mega Starmie | 1.2% | 88.2% | +2.96 | 0.14 |
| Cynthia Garchomp | 5.2% | 97.6% | +4.61 | 0.13 |
| *(11 remaining archetypes)* | 12.6% | 94–99% | +4 to +5 | 0.40 |

### Reading the table

**Crustle wall is the real weakness, not Marnie.** Marnie costs more ladder
points only because it is 43% of the field; we beat it 95% of the time. Crustle
is 8.7% of the field and we win 75%. Three independent signals point at it: the
worst winrate, the worst prize differential (games decided narrowly — which is
exactly where a new rule can move the needle), and 11 distinct lists, so it is
the archetype and not one odd deck.

**Ogerpon Verde is the second real hole** (85.8%), invisible in a
winrate-sorted list because it weighs so little.

**Winrate alone stops resolving once it saturates.** Above ~94% the generic
opponent bot is the limiting factor. The **prize differential** keeps
discriminating there, because a game can be won without taking all six prizes —
it measures something else, not a disguised winrate.

**Zero forfeits in 35,600 games** means the agent never crashed and never chose
an illegal option against any real list.

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

> One method note worth keeping: searching for a card ID inside the source gives
> **false negatives** — card IDs and attack IDs are different namespaces, and a
> "known" ID once turned out to be an attack. The only real bug in that audit was
> found by reading opposing lists by hand.

---

Next: [Improving the agent](improving-the-agent.md) · [Tools](tools.md)
