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

**Match point** — a player needs only one more knockout to take their last
prize. It changes what a body in front is *worth*: at their match point every
one of our bodies pays their whole remaining pile, so the cheap-corpse rules
stop separating candidates and survival takes over.

**Snipe** — damage aimed past the active at a benched Pokémon. The best snipe
target is rarely the biggest body, so it has its own target selection.

**The reply** — what the opponent does on their next turn in answer to ours.
Half of every defensive reading in the agent is a projection of the reply.

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

**The attack plan** — the turn's chosen attacker, target and attack, computed
once before scoring so that every later phase agrees on it (`AttackPlan`). Where
the docs say just "the plan" in a scoring context, this is the one.

**The turn plan** — a different object, and the distinction matters. The attack
plan says *what we can hit*; the turn plan (`TurnPlan`) says *what the turn is
for*, decided from the prize count before the first decision. Its answer is one
of four **modes**.

**Mode** — `WIN_NOW` (a route closes the game), `DENY` (no route of ours, and
their reply closes it), `RACE` (we take prizes and survive) or `DEVELOP`
(nothing decisive today). Ordering rules consult it so they do not step aside
for a resource card on a turn that ends the game.

**Route** — how a `WIN_NOW` turn actually closes: `ACTIVE`, `PROMOTE`, `GUST`
or `RECOVER`. Ordered cheapest first, because the route that commits fewest
resources is the one a bad draw cannot break.

**Do-or-die** — the `DENY` turn seen from the agent's side: the last turn we
get, so every rule that prices a play against future turns is worth nothing.
About 0.5% of decisions in the frozen corpus.

**Pivot** — rewriting the plan when the position is bad: retreat out of a doomed
active into a body that survives or trades better.

**Relay** — retreating so that a *charged* body on the bench can come up and
attack. Offensive, not defensive, and often the whole turn.

**Fodder** — the cards spent to pay a cost (the Ultra Ball's two discards).
Cheapness is a property of **the hand**, not of the card: the right thing to
throw away is whatever this hand cannot use today.

**Gift window** — the damage a body will have taken by the time the opponent
next acts: their attack plus the recurring chip and any damage they can move
onto it. "Will this body still be alive" means this.

**Commitment** — a resource already spent that obliges a later play. Benching
Meowth ex costs two prizes and is only paid for by the Supporter its ability
fetches, so that Supporter must actually be played.

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

**Census** — a tool that counts how often a situation occurs at all, before
anyone writes a rule about it. Cheaper than a game, and several rules here were
written, measured neutral and reverted for a population under a tenth of a per
cent of decisions. See [The instruments](instruments.md).

**Rule / adjustment** — the shape every decision in `ptcg/decision/` is written
in. A **rule** is a named rung that prices an option; the first one that applies
wins (a **chain**), or, in **argmax** mode, the highest value does. An
**adjustment** then corrects the surviving score. Naming the rungs is what lets
a census count them and a test assert on *which rule* decided rather than on the
number it produced.

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
