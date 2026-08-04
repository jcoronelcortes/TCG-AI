# How the agent thinks

[← Documentation index](README.md)

This is the mental model of the whole agent. Everything else in the
documentation is a detail of one of these steps.

## The contract

The simulator calls `agent(observation)` every time it needs a decision — many
times per turn, not once. It passes:

- **the current state**: turn number, which seat we are, both players' active
  Pokémon, benches, hands, discards, prizes, the stadium in play;
- **the request**: what kind of decision is being asked (play a card, choose a
  target, promote a Pokémon, answer yes/no…) and the **menu of legal options**;
- **the log**: everything that happened since the previous observation — attacks,
  knockouts, evolutions, coin flips.

The agent returns a list of indexes into that menu. If no decision is being
asked at all, it returns our 60-card deck list instead (that is the initial deck
handover).

## The core mechanism: score every option, play the best one

The agent does **not** search a game tree. It walks the menu, gives each option a
number, and picks the highest.

1. **Score.** Every option gets a score. Higher is better. A negative score is a
   **veto**: "never choose this now".
2. **Order.** In a normal turn the agent also sorts plays into **tiers**, so that
   things happen in a sensible sequence — energy that enables a knockout first,
   then the stadium, then evolutions and development, then searching, then
   ordinary energy attachment, then everything else. Tiers only reorder options
   that already scored positive, so vetoes always win.
3. **Pick.** Options are sorted by `(tier, score)` and the top ones are returned.

Big round numbers in the code (thousands, tens of thousands) are not magic
tuning: they are **priority bands**. A rule that says "this wins the game right
now" sits far above the band of ordinary development, so no accumulation of
small bonuses can overtake it.

## What happens inside one call

```
observation
    ↓
 1. Read the board          who is active, what is on the benches, what is in hand
    ↓
 2. Update the belief       track where every one of our 60 cards is
    ↓
 3. Identify the opponent   which archetype is this, what can it do to us
    ↓
 4. Build the attack plan   best (attacker, target, attack) available this turn
    ↓
 5. Pre-compute flags       "we win this turn", "the active is doomed", vetoes…
    ↓
 6. Score the menu          one branch per option type, using all of the above
    ↓
 7. Order and return        tiers, then score, then the final selection
```

Steps 1–5 are the *reasoning*; step 6 is where that reasoning turns into
numbers. Most of the strategy lives in step 5: flags computed **once** before
scoring, so that every later branch agrees on the same reading of the turn.

## Three ideas that explain most of the code

### The belief

The agent keeps a running count of **where each of our cards is**: deck, hand,
in play, discard, or prize. It is updated from what the observation shows and
from the game log, and it gets sharper when the engine reveals the deck (for
example when we play a search card).

This is what lets the agent reason about hidden cards — "is there still a hand
refill left in the deck?" — and it feeds the draw-probability estimates behind
search and refill decisions.

### The plan

Before scoring anything, the agent computes the best attack available this turn:
which of our Pokémon, hitting which target, with which attack. Every later phase
**reads that plan** instead of recomputing it. Without it, the energy phase and
the attack phase could disagree and spend the turn charging a Pokémon that never
attacks.

The plan can be rewritten by **pivot flags** when the position is bad — for
example: "our active can attack but cannot knock out, and it dies next turn" →
retreat and promote a body that survives instead.

### Turn state vs. permanent state

Some things must survive between calls inside the same turn, and a few between
turns (did we get knocked out last turn? did we go first?). All of it lives in a
single state object rather than loose module variables, for one hard-won reason:
importing a value by name copies it, and a module that copied it would keep
reading a stale value forever — silently, with every test still green. See
[Project history](project-history.md).

## Where the decision for an option is actually made

| The option is… | Where its score comes from |
| --- | --- |
| Play a card from hand | the PLAY branch, which calls one scorer per important card |
| Attach energy | the energy scorer (who deserves the energy this turn) |
| Evolve | the EVOLVE branch |
| Use an ability | the ABILITY branch (draw engines, energy accelerators) |
| Retreat | the RETREAT branch (pivots, sacrifices, vetoes) |
| Attack | the ATTACK branch (plus the vetoes that stop a bad attack) |
| Choose a target / a card to fetch | the CARD branch, one rule per searching card |
| End turn | scored like anything else — ending is a decision too |

Each of these lives in its own module under `ptcg/turn/options/`; the cards
with real strategy behind them (Boss's Orders, Ultra Ball, Night Stretcher,
disruption…) get a dedicated module under `ptcg/decision/`. See the
[Code map](code-map.md).

---

Next: [Our deck and its engines](deck-and-engines.md) · [Strategy](strategy.md) · [Code map](code-map.md)
