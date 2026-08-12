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

"It dies next turn" is a projection of the opponent's attack, and for a long
time that projection only looked at the Pokémon standing in front of us. Against
an evolution deck that is the wrong body: a pre-evolution with one energy looks
harmless and becomes, on their next turn, the card that takes two prizes. So the
projection also asks what the opposing active can **become in one step**, with
the energy it already carries. Only the sacrifice pivot reads that second number
— retreat the doomed two-prize Pokémon and put a one-prize body in front — for
the same reason the rest of the defensive machinery still reads the first one:
those rules were tuned against the smaller number, and a bigger one makes the
agent retreat when it should be racing.

### What the turn is for

The attack plan says *what we can hit*. A second, smaller object says *what the
turn is about*, and it is the prize count that decides: with one prize left, a
turn that can end the game is not the same turn as one that can take a prize.
The **turn plan** (`ptcg/turn/game_plan.py`) answers three questions once, before
the first decision:

- is there a route that **closes the game** — attack as we stand, retreat and
  promote the finisher, or gust a bench body with Boss's Orders?
- how many prizes can we take today?
- how many do they take on the reply, and does that close *their* count?

Those answers become one word — `WIN_NOW`, `DENY`, `RACE`, `DEVELOP` — that the
ordering rules consult. It exists because they used to decide without it: on a
turn with lethal on the board, a rule that says "play the disruption Supporter
first" vetoed the Boss's Orders that ended the game, and the agent spent nineteen
actions rebuilding a board it no longer needed. `PTCG_DEBUG=1` prints the plan
above the ranking, which is usually the fastest way to see why a play lost.

### The turn with no tomorrow

One of those four words is different in kind from the other three. `DENY` means
no route closes the game *and* their reply does: the turn is the last one we
get. The plan publishes it under a name of its own, `do_or_die`, because almost
every rule in the agent prices a play against the turns that come after it — a
body benched for tomorrow, a prize taken on account, a search kept for when it
is needed — and on that turn none of that arithmetic is worth anything. The only
question left is whether the turn can still *manufacture* the knockout.

Three habits of the agent turn out to be wrong there, and each of them was
reading a question one step away from the one that mattered:

- **the last bench seat.** A body goes down before a search is played, because
  a Pokémon play outranks an Item by play-order tier. With one seat left that
  order decides what the search is allowed to buy, and the search is the card
  that knows what the seat is for.
- **what the search buys.** "Do we have an attacker?" is answered by asking
  whether an attack is *legal*. On this turn ours was legal and took 240 off a
  300 HP body, which is the same as no attacker at all — so the search should
  buy the deepest look at the deck, not a body for a board we will not have.
- **where the energy goes.** The rule that puts the finishing charge on the
  active only looked at attackers that could not yet *pay* for their attack.
  Our attacks scale with energy, so past the cost each Grass is more damage:
  the number that decides is the opposing HP, not the printed cost.

All three corrections are gated on `do_or_die`, which is 0.5% of the decisions
in the frozen corpus. That gate is deliberate — the defensive machinery here has
measured negative three separate times when it was made to fire more often.

### The dead turn

A third, cruder reading runs alongside those two: **can the active attack at
all this turn?** When the answer is no, a different set of engines takes over —
the ones that spend the turn buying options instead of taking prizes, above all
benching Meowth ex so its search brings the hand refill out of the deck.

The answer is not just "count the energy on it". Our energy acceleration can
still charge the attacker mid-turn, so the reading prices that route: with
Ogerpon on the board and Grass left in the deck, the dances draw cards and those
cards may be the energy we need. What that estimate must never forget is the
**seed**: the ability attaches an energy *from hand*, so with nothing to pay the
first dance there is no dance, no draw and no route — and the whole chain is
worth zero, not a coin flip. When the hand cannot start it, the turn is dead and
the agent should be looking for the card that fixes tomorrow.

### An order is not a value

Many rules do not say "this play is bad", they say "not yet — play that other
card first". Refill the hand *after* the search that completes the evolution
line, so the refill does not shuffle away the pieces. Use the draw ability
*after* the Stamp that reshuffles our hand. Those are orderings, and they are
true only while the card being waited for can still be played this turn.

Scored as if they were judgements, they cost whole turns. Three correct rules
can point at each other in a circle and none of them gets played: it happened to
a once-per-turn ability whose blocker was itself vetoed, and it happens to the
Supporter of the turn against a deck that locks Items — the refill waits for a
search that this turn will never allow, and dies in hand.

So an ordering veto is not applied on the spot. It is filed, together with the
score the option really deserves and the cards it is waiting for, and lifted
again once the whole menu is known: if no blocker is on the menu, or if the turn
closes with this very action, the "afterwards" is never going to arrive and the
order is void. A **value** veto — the deck-out brake, keeping a line we can
evolve today — is decided before that and never revoked.

The subtlety is what counts as a blocker still being alive. Being *offered* and
being *worth playing right now* are different things: a search can sit at a veto
because its cost would eat the wrong card, and become playable ten seconds later
in the same turn once that card has been benched. What the engine does not offer
at all is the only reliable sign that a card cannot be played today.

### The tier decides before the score, so the tier has to know the score

Ordering vetoes are not the only thing that orders a turn. Above the scores sits
a small table of **play-order tiers** — the winning attack goes before any
charge, an evolution before an Item, the turn's energy before the attack that
ends it — and a tier is compared first, so a play in a higher tier beats a play
worth six hundred times more.

That is right exactly as long as a tier is a statement about the *kind* of play.
It stops being right where a scorer has a band that means "this play is worth
almost nothing". Supporters have had one for a long time,
`SUPP_SCORE_LAST_RESORT_BAND` — twenty, the height at which a scorer says *today
I do nothing useful: play me only if nothing else scores* — and three separate
rules already read it rather than counting cards. Energy has the same band under
another name: `SCORE_CHARGE_DOOMED`, the ceiling on charging a body the opponent
can knock out before our next turn.

Every attachment was handed the energy tier without anyone asking what the
attachment was worth. On turn 6 of a game against Marnie's Grimmsnarl ex that
put a Grass on a doomed Meganium — the agent's own number for it was 20 — ahead
of an Ultra Ball it had scored 11900, and the Grass was one of the two cards the
Ultra Ball discards to pay for itself, so one action later the search was not on
the menu at all. The turn attacked and ended with the Ultra Ball dead in hand
and four empty bench seats.

The correction is that a play priced in the last-resort band yields its tier
while any real play is still waiting. It **yields the order, it is not
cancelled**: turn-closers are left out of that comparison on purpose, so once
the real plays are gone nothing outscores the attachment any more, it takes its
tier back and still goes down before the attack — where the energy of the turn,
which does not accumulate, belongs.

### A card that pays with the hand is priced against the hand, not against a card

The same turn against Archaludon ex, six days and one deck later, lost the same
Ultra Ball to a play the agent had scored at *thirty thousand*, not at twenty —
so no band-reading could have saved it. The active could not knock out anything,
the bench held one body, the turn's Supporter was unspent and the deck still had
Meowth ex and Lillie's Determination: the exact board of the pivot that plays
the search **first**, ahead of the energies, because the Ultra Ball is the only
card on the menu that is about the rest of the game. The pivot did not fire, for
one reason: it asked for two Basic Grass Energy in hand, and the hand held one
Grass, one Ultra Ball and a second Hydrapple ex that no board of ours could ever
put into play.

A cost of "discard two" is a question about **surplus**, and surplus is a
property of the whole hand. The agent already had the count that answers it —
the one that walks every card and asks what the discard scorer would really let
go, keeping linked evolution pieces, a lone refill Supporter, a playable Meowth
ex — and three cost vetoes were already using it. Two energies were one instance
of surplus, not the definition of it; naming the card turned a general rule into
a rule about one deck's opening hand. The dead Stage 2 was surplus by every
reading except the one that was being asked.

The general shape, worth recognising anywhere: a rule that names cards where it
means a property will be silent on every board that has the property under
different names, and no amount of tuning its score will help — the rule never
speaks at all.

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
