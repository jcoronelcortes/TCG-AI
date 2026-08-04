# Strategy

[← Documentation index](README.md)

These are the principles the agent encodes. Every one of them came from a lost
game or a measured experiment, and each is expressed in the code as a score, a
priority band or a veto. This page is about **why**; the source is the authority
on the exact thresholds.

Read [Our deck and its engines](deck-and-engines.md) first if the card names
mean nothing to you yet.

---

## 1. Winning now outranks everything

If a line of play takes the last prizes this turn, it is played — ahead of
development, ahead of refilling the hand, ahead of any positional consideration.
The same applies to wins by other routes: emptying the opponent's bench, or a
knockout that reaches the prize count we were missing.

The mirror of this rule matters just as much: a knockout that **ties or hands
over** the game (because our attacker kills itself and gives up the prizes that
lose us the race) is vetoed even though it looks like a knockout.

## 2. Attacking with the active comes first

The most common way to throw away a turn is to spend it developing and never
swing. When the active can attack, attacking is the baseline, and anything that
displaces it has to justify itself. A turn that ends with a full hand and zero
damage is treated as a failure mode — there is a dedicated detector for it in
the loss-autopsy tool.

## 3. Prizes are the currency, not damage

Every body is priced in prizes. A two-prize ex trading with a one-prize
attacker is a bad trade even when the damage numbers look fine. This shows up
everywhere:

- prefer attacking with a one-prize body when it kills just as well;
- retreat a fragile ex and give up one prize instead of two;
- when choosing what to drag out with Boss's Orders, prefer the target that
  pays the most prizes;
- when promoting after a knockout, prefer survival and fewer prizes given away.

## 4. Boss's Orders: drag the right body, or don't drag at all

Boss's Orders costs the Supporter for the turn, so it has to buy something real.

**Worth it:** a knockout that wins the game; a target worth more prizes than
what we would kill up front; the highest evolution of a line that is coming for
us; a charged pre-evolution of an ex line (kill it before it becomes the
threat); dragging out a body that unlocks our own attack; using it to break out
from behind a wall.

**Not worth it:** a non-ex pre-evolution; a body that cannot be knocked out
(chip damage to the front is not a prize); a copy of a threat the active already
represents; dragging a line out without the follow-up to actually kill it.

## 5. Don't waste turns — the hand engine exists for this

A turn where nothing can attack and nothing develops is worth less than the
cards spent on it. When the board is stuck, refilling the hand becomes the
priority: bench Meowth ex, fetch Lillie's Determination, play it, and see a new
hand. Recovering the engine pieces from the discard counts as the same play.

The counter-rules keep the engine from firing pointlessly: don't refill if there
is already a ready attacker, if the Supporter for the turn is already in hand, or
if the Supporter slot is already spent.

## 6. Searching must pay for itself this turn

Ultra Ball discards two cards; Poké Pad, Bug Catching Set and Night Stretcher
each spend a slot. The rule is the same for all of them: **what you fetch has to
be played now**. Digging up a body for a bench that is full, an evolution whose
pre-evolution is not in play, or an attacker we cannot charge, is a net loss.

The exception is expiry: with item lock coming, the search is used today for
tomorrow's play, because tomorrow it will be illegal.

## 7. Energy goes where it changes something

Energy attachment is the scarcest resource of the turn — one per turn plus what
the abilities accelerate. The agent asks who *becomes able to attack* because of
this energy, not who is our best Pokémon:

- charge the attacker that reaches its cost, in effective energy;
- respect the caps — extra energy on an already-charged body, on a body that
  cannot use it, or on one that dies this turn, is waste;
- reserve enough to pay a retreat cost when the plan needs a pivot;
- energy that will be wasted is wasted **at the moment of the knockout**, which
  is why doomed bodies are not charged.

## 8. Retreating is a real play, not an admission of failure

Retreat is how a stuck position becomes a winning one, and the agent treats it
as a scored option like any other:

- pivot away from a doomed active into a body that survives the incoming hit;
- retreat a fragile ex to give up one prize instead of two;
- put the body that **endures** in front, not the one that merely looks strong;
- retreating costs cards, so the energy budget must cover it — sometimes the
  attachment for the turn exists purely to pay a retreat;
- play the Supporter **before** retreating when the retreat would end the turn;
- don't swap an ex for a worse body, and don't pivot into a body that is doomed
  anyway.

## 9. After a knockout, promote for tomorrow

The choice of who comes up is not about who is strongest today. It is about who
can attack **next** turn, who survives the projected hit, and who gives away the
fewest prizes. A wall pinned in place with no attack is worse than a mobile body
that can act. And the bench is never left empty: ending a turn with an empty
bench loses the game outright.

## 10. Disrupt on the right order

Hand disruption is cheap value against decks that hoard cards, but the order
matters: strip cards permanently first, then shuffle the hand away. The reverse
order throws away the cards the first effect would have removed for good. Both
also step aside when refilling our own hand is worth more.

## 11. Walls: the immune body in front

Several meta decks put a body in front that our ex attackers simply cannot
damage. This is the strategic problem the agent invests most in:

- promote a **non-ex** attacker that can hit it;
- a wounded wall is not a wall — the agent reads current HP, not printed HP;
- kill the wall before spending Boss's Orders behind it;
- don't feed energy into an attacker the wall is immune to.

## 12. Play order

Two plays can both be right and still lose the turn if they happen in the wrong
order. The agent enforces a sequence: energy that enables a knockout, then the
stadium, then evolutions and development, then searching, then ordinary energy,
then the rest. Ordering never overrides a veto — it only sorts plays that were
already worth making.

---

## How these rules get added

A rule is not added because it sounds right. It gets proposed from a real loss,
implemented, and then **measured**: if it does not change decisions, or it
changes them without winning more games, it is reverted. See
[Improving the agent](improving-the-agent.md).

Next: [Matchups](matchups.md) · [Improving the agent](improving-the-agent.md)
