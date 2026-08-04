# Glossary

[← Documentation index](README.md)

Terms used throughout this documentation and the code.

## Card-game terms

**Active** — the Pokémon in the front spot. The only one that can attack (and
the only one that can normally be attacked).

**Bench** — the Pokémon in play behind the active, up to five. Ending a turn
with an empty bench loses the game.

**Prizes** — the six face-down cards you take one at a time for each knockout.
Taking all six wins. A regular Pokémon is worth one prize, an *ex* is worth two,
and a *mega ex* three — which is why prize value, not raw power, drives most of
the agent's trades.

**Knockout (KO)** — reducing a Pokémon to zero HP. The attacker's player takes
the prizes.

**Retreat** — moving the active to the bench, paying its retreat cost in energy.

**Gust** — dragging one of the opponent's benched Pokémon into the active spot
(what Boss's Orders does), usually to kill something that was hiding.

**Supporter** — a trainer card, one per turn. That "one per turn" limit is why
so many of the agent's rules are about *which* Supporter gets the slot.

**Item lock** — an effect that stops us playing item cards. It makes searching a
resource that expires rather than one we can save.

**Wall** — a body put in front specifically to be hard or impossible to remove,
usually immune to a whole class of our attackers.

**Mill / deck-out** — winning by making the opponent run out of cards to draw
instead of by taking prizes.

**Bench-out** — winning because the opponent has no Pokémon left to promote.

**Mirror** — playing against our own deck.

## Project terms

**Observation** — everything the simulator tells us at one decision point: the
board, the menu of legal options, and the log of what just happened.

**Option / menu** — the list of legal choices the simulator offers. The agent
returns indexes into it.

**Score** — the number the agent assigns to an option. Higher is better.

**Veto** — a negative score. It means "never choose this now", and no amount of
positive value from other rules can overcome it.

**Tier / play order** — a coarse ordering applied on top of scores in a normal
turn, so that plays happen in a sensible sequence. It only reorders options that
already scored positive.

**The plan** — the turn's chosen attacker, target and attack, computed once
before scoring so that every later phase agrees on it.

**Pivot** — rewriting the plan when the position is bad: retreat out of a doomed
active into a body that survives or trades better.

**Effective energy** — energy counted *after* our accelerator doubles Grass
energy and after any stadium raises our attack costs. All "can this attack?"
questions use effective energy, never the physical card count.

**The belief** — the running count of where each of our 60 cards is (deck, hand,
in play, discard, prize). It is what lets the agent reason about cards it cannot
see.

**Dead turn / sterile turn** — a turn that ends with cards still in hand and no
damage dealt. Treated as a failure mode, and detected automatically by the
loss-autopsy tool.

**Flip** — a decision that changed between two versions of the agent. The golden
corpus and the shadow harness both report flips; an unintended flip is a
regression.

**Golden corpus** — the snapshot of past decisions used to detect flips. See
[Testing](testing.md).

**Gate** — a measurement that a change has to pass before it is kept: the test
suite, the corpus, self-play winrate, the matchup matrix.

**Generic bot** — the reference opponent that pilots any deck legally but not
well. Useful because it is fixed: differences between our versions are signal,
its absolute level is not.

**Meta weight** — how often a given opponent list actually appears on the
leaderboard, used to turn a table of matchup winrates into an expected ladder
winrate.

**Prize differential** — the average prize lead at the end of a game. It keeps
discriminating between versions after winrate saturates.

---

Next: [How the agent thinks](how-the-agent-thinks.md) · [Strategy](strategy.md)
