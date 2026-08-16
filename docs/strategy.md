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

**But "attacking comes first" says nothing about who attacks.** When the body in
front can finish the target and a benched body can finish it just as well, the
question stops being whether to swing and becomes which of the two is left
standing afterwards. If their reply knocks our active out and those are their
last prizes, then taking the prize from the front takes it and loses the game;
paying a retreat to take the same prize with a body that outlasts the reply
wins. Two conditions keep this from becoming a habit rather than a rescue: the
body coming up must actually survive their projected hit and hand over no more
prizes, and the reply must be the match — a trade we merely dislike is not worth
the retreat cost.

Three places the agent used to be blind to this, and each one is a seam where
the ordinary reading of their reply is simply *wrong*, not merely pessimistic.
Outside them the pivots already measured against those boards keep deciding.

- **The attack that prints no damage at all.** Powerful Hand places counters and
  scales with the size of their hand, so the attack table reads zero and every
  defensive rule sees a harmless attacker.
- **The reply that comes off their bench.** These rules only run when our own
  attack is about to knock their active out — which means the body they were
  reading is on its way to the discard. What actually replies is whatever they
  promote, and their bench is fully visible.
- **The knockout that loses the game.** The two above open only where their
  active looks harmless. When it does *not* — when the body in front is doomed
  whatever we do — the turn belongs to the rules written on a doomed active, and
  those refuse to retreat while a prize is available from the front. That is
  right except on one board: their promoted body knocks our active out and those
  prizes close their count. There, cashing the prize from the front *is* the
  losing move, and the plan already says so (`op_wins_after_ko`). The relay still
  has to take the same knockout, so the prize is never given up — only the corpse
  left behind changes.

### 2.1 The HP the attack has to cover is not always the HP printed on the card

A hit that falls short is only short of the number the body will still be
carrying when the knockout is checked, and something on the board can pay the
rest. Their own Froslass is the case in our meta: *Freezing Shroud* puts one
damage counter on **every** Pokémon with an ability, "both yours and your
opponent's", and their own 320 HP Grimmsnarl ex has one — so two Froslass on
their bench make that body 280 to us, which is exactly what our Solar Beam does
through their Darkness weakness.

Two things make this a rule rather than an arithmetic trick:

- **the unit is the checkup, and how many there are depends on whose turn the
  menu belongs to.** One for our own attack (the checkup that opened the turn is
  already inside the HP we can see), **two** for the forced promotion after a
  knockout, because it resolves at the end of *their* turn, one for a voluntary
  retreat. The drip is also the safest damage there is: it lands between turns,
  where they can neither heal it off nor move it with Adrena-Brain;
- **the body we promote eats the same checkup before it swings.** A Meganium at
  20 HP is removed by the very counter that softens their Grimmsnarl. It never
  attacks, so it is not a knocker — it is a free prize.

Where it deliberately stops: "this attack wins the game" still reads printed HP.
With a deferred knockout both deaths land on the same checkup, and if the drip
also closes their count the result is a **draw**, not a win. Without a Froslass
in play the reading returns the printed HP unchanged, which is what makes it safe
to wire into every knockout test in the agent.

## 3. Prizes are the currency, not damage

Every body is priced in prizes. A two-prize ex trading with a one-prize
attacker is a bad trade even when the damage numbers look fine. This shows up
everywhere:

- prefer attacking with a one-prize body when it kills just as well;
- retreat a fragile ex and give up one prize instead of two;
- when choosing what to drag out with Boss's Orders, prefer the target that
  pays the most prizes;
- when promoting after a knockout, prefer survival and fewer prizes given away.

**And the deck is the clock the prizes are raced against.** One card is drawn
every turn and at best one prize is taken every turn, so a deck holding fewer
cards than the prizes still owed has already lost the race on time, however well
the board is going. In that corner a Supporter that shuffles the hand back in
stops being a refill and becomes the only play that buys the turns the win
needs — it goes first, ahead of the vetoes that merely postpone it, and it costs
nothing, because a Supporter does not end the turn. What is deliberately *not*
paired with it is a brake on the cards the engine burns: that was built and
measured against the wall decks and it only converted deck-out losses into prize
losses, one for one.

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

**And one case where the knockout is the wrong answer.** A gust knockout does
not empty the opposing active spot: the body we killed leaves, and the opponent
promotes whatever they like, for free, with no retreat to pay. So the attacker
that was in front of us is back in front one action later. That is fine while we
still have time to spend the prize — but not when their next attack ends the
game. When the turn plan says their reply closes it, a prize that does not win
buys nothing, and the better target is the one that cannot answer and cannot
leave: a body short of the energy its attack costs, and short of its own retreat
cost. Dragging that one out costs them the whole turn, and the bigger it is the
better, because it stands there while we chip it down. A gust that actually ends
the game still outranks everything.

**And a gust that cashes is not a Supporter to weigh against the other
Supporters.** Refills compete with each other for the one slot the turn has, and
a refill that was already paid for — searched out with a body we put on the
bench for it — keeps that slot against the rest. Boss's Orders is not in that
argument. It refills nothing: it rewrites which body is in the active spot, and
when a knockout is already behind it, it is the attack. So the whole upper half
of its ladder — the branches that need a prize, a wall or a win — outranks a
committed refill, and only the gusts that take nothing yield to one.

**And the dead turn, where the same body is the whole play.** Some turns have no
attack and no knockout anywhere: the active is one energy short, the attachment
is spent, nothing on the bench is any closer. The Supporter for the turn is then
about to be thrown away with the hand, and ending the turn keeps a Boss's Orders
that buys nothing later either. If their bench holds a body that cannot answer
from the active spot even after an attachment, and cannot pay its own retreat to
get back, dragging it out is not a nuisance — it is a denial. They lose the
attack, or they lose the energy they have to spend getting that body out of the
way. It is the last thing the card is asked to do, below every reason with a
prize behind it and below refilling the hand, and it is still worth more than
ending the turn with the card in hand.

Two things stop it. One: their active has to be attacking, otherwise the gust is
a free retreat we hand them. Two: what comes up must not be a pre-evolution of
their attacking line. A bare pre-evolution looks harmless — its own attack costs
more than it can pay — but it evolves in the active spot and attacks with the new
body, so putting it in front of us is doing their work. The walls and the ability
lockers read as harmless for the same reason and are excluded for a worse one:
from the active spot they cancel our attackers.

**And the third thing that stops it: a trap can be a lock on our own door.** The
whole denial above is a purchase, and a purchase only pays if we can spend the
turn it buys. There is a state where we cannot — the active neither attacks this
turn nor can pay its way out of the front — and there the seat does not change
hands until *they* knock it out. Freeze them and we freeze ourselves behind a body
that will not move, with the real attackers stranded on the bench.

So in that state the question turns over. It stops being *what costs them most to
escape* and becomes **what is the seat worth selling for**: a body whose attack
knocks our doomed active out — that is what opens the seat — and that an attacker
already charged on our bench kills from the seat it inherits. That is a knockout
route the usual reading has no name for, because both of the usual ones need an
active that can act: attack from the front, or retreat and hit with the bench.
This is the third, and it is the only one alive here.

Among the bodies that qualify, take the one worth the **most prizes**. Their
two-prize attacker spends its turn knocking out our one-prize corpse and our relay
takes two back — the race goes 1 for 2 and keeps that shape. The floor that keeps
it a trade: the knockout we are handing over must not be the one that ends the
game for them.

Note what makes the biggest body the softest one here. Our scaling attacks count
the energy on **both** actives, so a heavily charged target pays for the attack
that kills it; and the alternative is not free for them either, because retreating
that body out discards the energy the retreat costs.

**And the highest link of an ex line is only the threat while it IS one.** The
rung that lifts a charged pre-evolution above everything else is paid for by "a
two-prize ex attacker we cannot answer decides the game on its own", and that
premise has to be checked rather than assumed. It fails two ways, and both send
the gust to their **engine** instead:

- **Their Stage 2 is already answered.** If a body on our *bench* — not the board:
  an answer that has to be in the active spot to exist is not a reserve — already
  knocks the evolved threat out, then cutting the line buys a body they rebuild,
  while the abilities no evolution step controls keep working. Between engine
  bodies, take the copy that already has its turn assembled: the charged one
  attacks from the seat we are selling it, the bare one is a body they still have
  to pay for.
- **Their line is carrying no energy at all.** The rung demands a *charged*
  pre-evolution, so at zero it never fires — there is nothing to protect, and the
  engine is owed the gust by nobody.

Two shape rules come out of building that ladder, and they outlive the matchup.
**`max` and not `+`**, because a stage table summed on top of a band eats any
spacing that fits inside it. And **the ladder belongs in the field, not in a
chain**: the menu is routed by whether *our own* active can attack, and a matchup
reading that only holds while that happens to be true is an accident of which
chain ran, not a reading. One object, both lists, identity pinned by test.

## 5. Don't waste turns — the hand engine exists for this

A turn where nothing can attack and nothing develops is worth less than the
cards spent on it. When the board is stuck, refilling the hand becomes the
priority: bench Meowth ex, fetch Lillie's Determination, play it, and see a new
hand. Recovering the engine pieces from the discard counts as the same play.

The counter-rules keep the engine from firing pointlessly: don't refill if there
is already a ready attacker, if the Supporter for the turn is already in hand, or
if the Supporter slot is already spent.

"Already in hand" means a Supporter that really takes the turn. Every Supporter
scorer has a bottom band it uses to say *I do nothing today, play me only because
nothing else scores* — an empty gust with no target, a hand cap against an
opponent already down to four cards. A Supporter sitting in that band is not the
Supporter of the turn, and it is no reason to leave the hand engine dead in hand:
if nothing we hold does anything, a fresh Supporter out of the deck is worth the
two-prize body on the bench. Above the band the counter-rule stands.

## 6. Searching must pay for itself this turn

Ultra Ball discards two cards; Poké Pad, Bug Catching Set and Night Stretcher
each spend a slot. The rule is the same for all of them: **what you fetch has to
be played now**. Digging up a body for a bench that is full, an evolution whose
pre-evolution is not in play, or an attacker we cannot charge, is a net loss.

The exception is expiry: with item lock coming, the search is used today for
tomorrow's play, because tomorrow it will be illegal.

A card can also stop being playable in the middle of our own turn, and the
Unfair Stamp is the way it happens: it shuffles **our** whole hand back into the
deck, so anything a search leaves in hand and does not play before it is gone.
While the Stamp is going to be played this turn, the Meowth ex the Ultra Ball
digs out is not a body, it is a Supporter engine — and every Supporter yields the
turn to the Stamp, so that engine cannot fire before the shuffle. That fetch is
the Item plus its two discards for nothing. What survives the shuffle is what
reaches the **board**: with the Stamp pending, the search takes the body it can
put down now. The mirror of the same fact is that emptying the hand with Items
before the Stamp is *good* — it is what makes its refresh clause pay. The line
is not "no Items before the Stamp", it is "nothing bought may still be in hand
when it resolves".

And the payment has to come out of surplus. A hand of the Ultra Ball plus two
cards has no surplus: those two *are* the cost and the hand ends the turn empty.
That is only acceptable when neither of them is a Supporter — because a
Supporter that cannot be played today is not a spare card, it is the whole of
tomorrow. Discarding it to bench a body trades a turn for a Pokémon.

Surplus is not the same as hand size. What counts is how many cards the discard
scorer would really let go: an evolution whose pre-evolution is on the board, a
Meowth ex that can still be benched, the Unfair Stamp that is never discarded —
none of those is spare. When fewer than two remain, the cost cannot help but
take what the agent itself is protecting, and there the search is not paid for
at all. The worst version of that is paying for the intermediate piece of a line
with the top of the same line.

But a line protects the copies it can wear, not every copy. An evolution goes on
top of a body, and one body wears one card: with a single Applin on the bench,
the second Hydrapple ex in hand cannot reach the field by any route. It is not a
spare attacker, it is cardboard — and it is exactly what the cost should eat.
Counting pieces instead of bodies makes a hand look like it has nothing to spare
when the cheapest card in it is sitting right there, and the search gets
cancelled over a card that was never going to be played. The seats are the
bodies already in play below the card, plus the basics of that line the bench
still has room for; anything past that number is the first thing to go. A piece
in hand does not add a seat — it stacks onto a body that is already counted.

A refill Supporter is spare least of all once the Supporter slot for the turn is
already spent. The temptation runs the other way: a card that can no longer be
played today looks free, and a scorer that prices cards by what they do now will
hand it over first. But nothing can compete for that slot tomorrow, so a lone
refill Supporter with the slot gone is not a leftover — it is next turn's whole
hand, and it is the last thing a cost may take.

Even a search that is paid for out of real surplus still has to buy something.
On a turn with no attack, a basic dug out of the deck cannot swing and cannot
evolve: all it buys is a seat on the bench. That is worth two cards only while
the bench is short enough that one knockout would leave us with no body to
promote. From two bodies up, ending the turn and keeping the cards is worth
more than the seat.

**On a dead turn, ask what is missing before choosing the refill.** When nothing
of ours reaches its attack cost, the reflex answer is to refill the hand — and it
is the right one when what we are short of is a *card*. It is the wrong one when
what we are short of is *energy that is already ours*, sitting in our own
discard: there Lana's Aid recovers it, the attachment and Teal Dance put it on
the attacker, and the turn that was about to end for nothing takes a prize
instead. The agent only prefers the recovery when the arithmetic closes — the
Grass in the discard, the attach routes still alive this turn and the damage
formula have to add up to a knockout on the body in front — and it yields to a
hand of two or fewer, where the eight-card refill contains the recovery anyway
and shuffles nothing worth keeping.

A **legal retreat is not a play**, either. "The active cannot attack but it can
retreat" only rescues a turn when somebody on the bench can attack once it is up;
with every body short of its own cost, paying a retreat changes which Pokémon is
standing still.

**"The body is there" is not "the body can wear it today."** A Supporter that
fetches a Stage 2 has to pick between the tops of two lines, and both look
immediate while the pre-evolution of each is on the bench. Only one of them is:
a Bayleef that was evolved out of a Chikorita *this turn* cannot take a Meganium
until tomorrow, so the search that names it buys a card that sleeps in hand,
while the Hydrapple ex over a Dipplin that has been there since last turn would
have been on the board the same turn. Reading a field count answers "is the body
there"; what the rung claims to ask is whether the evolution lands today, and it
is one ceiling over every candidate rather than a condition repeated per card.
The exception is the stadium that lifts the restriction — and **a Forest in hand
is a Forest**, because the one-turn chains the same table prices are exactly the
ones it enables.

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

The Grass that is *not* spent today is not free either. Teal Dance and Ripening
Charge attach **from hand**, so once no charging ability can still fire this turn
the last Grass in hand is what makes tomorrow's charge — an attachment *and*,
with Teal Dance, a card — payable at all:

- with a route to a Lillie's Determination tomorrow (the Supporter itself, a
  Meowth ex or an Ultra Ball in hand), or with a second Grass, the energy is
  spent today **on the Teal Mask Ogerpon ex that is still short of its cost** and
  not on a body that will not attack. Holding it would not even be holding: the
  refill shuffles the hand — Grass included — back into the deck;
- without that route, the last Grass stays in hand and pays tomorrow's Teal
  Dance;
- against Crustle and Cornerstone none of the above applies. Our ex does not
  damage the wall: there the Chikorita is the first rung of the Meganium line,
  Tapu Bulu is the plan, and the energy belongs to the bench.

**And "Tapu Bulu is the plan" is a claim about THIS turn, not about the plan in
the abstract.** Two ordering rules written with no matchup inside them were
deferring it, and each one was invisible from the other's file:

- **the body waited behind the items.** "Tapu Bulu is only put down once every
  worthwhile item is played" is right in an ordinary game and wrong in front of
  the wall, where it dropped the matchup's only attacker from 22000 to 8900 —
  under everything else on the menu. The turn after a knockout that handed the
  bench slot to **Fezandipiti ex**: two prizes, and it cannot damage Crustle
  either. The wait is now lifted for the whole wall family. Only the clamp is
  lifted, not the ordering: an item the turn genuinely values above Tapu's own
  band still goes first;
- **the charge only knew about the ACTIVE Tapu.** The Crustle band that says
  "every turn its climb to four energies is deferred is a turn the wall lives"
  was gated on being the active, because that is the board it was measured on. A
  benched Tapu below four is the same answer to the same wall, one retreat away,
  and it was losing the turn's energy to the Applin line. It earns the band too,
  while no Tapu in play can already swing.

Together they are one turn: Tapu comes down, the manual attachment goes to it,
Hydrapple ex's **Ripening Charge** — whose target is decided by the same
`energy_score` — goes to it as well, and under Wild Growth those two Grass are
the four effective Wood Hammer needs. Today, instead of a Grass held in hand for
a Tapu that is still in there with it.

Measured over the 22 `crustle_wall` lists with paired seeds at 1500 games each:
mean **+0.21 points**, 15 up / 2 flat / 5 down (sign test p=0.041), prize
differential flat, and ten non-wall lists at delta *exactly* zero.

**A half-built body is not an empty body.** The development band that hands out
the attachment on a turn whose attack is already decided used to look only at
bodies with *zero* energy, on the reasoning that an empty body is the one that
needs starting. What that misses is the body one card from its own cost — the
second Teal Mask Ogerpon ex on two Grass, which is also the body that takes the
front the moment the one in front dies. Priced as "not empty" it fell to the
generic tail and lost the Grass to a Bayleef that cannot attack at any amount of
energy. Asked honestly — through the body's own effective cost — the band keeps
its measured order between species and gains a step in each direction for the
copy: up if this Grass leaves it *at* its cost, down if it does not. Both steps
are half a rung, so **which species** deserves the energy is still decided
exactly as before; what the steps decide is **which copy**. A body already at its
cost is still refused (that is the overcharge every cap in the file exists to
stop) and so is one whose twin already sits on the bench charged — tomorrow's
attacker exists, and finishing the second copy is not finishing the first.

## 8. Evolving is not healing: which body takes the evolution

Damage carries over when a Pokemon evolves — only the maximum goes up. That
makes the choice of body, when two copies of the same pre-evolution are in play,
a real decision and not a formality:

- the **wounded** copy is the one that gains from evolving: the counters it
  already carries stop being lethal inside a bigger pool, and the intact copy
  is the one that can wait on the bench;
- evolving the healthy one instead leaves the wounded one sitting there as a
  prize that any automatic snipe cashes in for free, without the opponent
  spending an attack on it;
- the exception is a body the evolution cannot rescue: if it stays inside the
  window the opponent can cash before our next turn **and** the evolution hands
  over more prizes than the pre-evolution, evolving there does not save a body,
  it upgrades their prize.

This orders bodies only. It never decides which card is played, which line is
assembled, or whether evolving is worth it at all — those are settled first.

## 9. Retreating is a real play, not an admission of failure

Retreat is how a stuck position becomes a winning one, and the agent treats it
as a scored option like any other:

- pivot away from a doomed active into a body that survives the incoming hit;
- retreat a fragile ex to give up one prize instead of two;
- put the body that **endures** in front, not the one that merely looks strong;
- retreating costs cards, so the energy budget must cover it — sometimes the
  attachment for the turn exists purely to pay a retreat, and the bill is
  counted in **cards**: the cost is printed in energy symbols but paid by
  discarding whole energies, so while our accelerator is doubling every Grass
  one card settles two symbols. A rule that finances a retreat by subtracting
  cards from symbols asks for twice the energy it needs, and goes quiet on
  exactly the boards it was written for;
- play the Supporter **before** retreating when the retreat would end the turn;
- don't swap an ex for a worse body, and don't pivot into a body that is doomed
  anyway — but "worse body" is measured against a body that is doing something.
  An ex we never attack with (the draw engine) is not a wall: the HP it endures
  buys nothing but the two prizes it eventually hands over, and a one-prize
  relay that can actually hit is an improvement on both counts. Getting that
  backwards costs the whole turn, because it vetoes the attachment that pays
  the retreat **and** the retreat itself.
- **Two copies of the same card are not the same body.** When the one in front
  and the one on the bench take the *same* knockout, the front spot goes to the
  one with more life **left** — printed HP says nothing about the damage already
  on it. The rule that used to decide this asked "is the active the small card",
  which is the right answer for four of our five ex and silently wrong for the
  fifth: the wounded copy of the biggest card we own reads as the wall it no
  longer is.
- **The retreat chooses who pays the prize the opponent is about to collect.**
  Handing the front spot to a body that hands over *more* prizes only makes
  sense if the body buys something with them: a hit this turn, or enough HP to
  live through the reply. When the relay does neither — it cannot pay its attack
  and their projected attack knocks it out anyway — the swap changes nothing
  about the knockout and doubles its price, so the cheap body stays in front and
  attacks for whatever chip it has.

Two things are easy to get wrong, and both were paid for in the same turn:

- **A pivot pays for its own retreat before it is allowed to promise anything.**
  Our big attack scales with the energy on the field and the retreat cost is
  discarded off it, so the body coming up hits a field one card smaller than the
  one the projection is reading. A knockout believed on the pre-retreat count
  can miss by exactly that margin — and, worse, it points the plan at the bench
  and silences the attack the active already had.
- **Hiding a doomed ex on the bench only denies prizes if it survives down
  there.** What reaches it is the snipe of the attacker in front, the drip of
  the abilities that fire on every checkup, and the counters the opponent can
  aim at it. That last term is measured after **our own** attack lands: damage
  we deal is the ammunition their movers use, so a board that looks harmless
  before we attack is not the board that will be there when they play. When
  they can cash the ex on the bench, staying is better — their attack is spent
  on a body that was already lost, and the wall behind it stays whole.

## 10. After a knockout, promote for tomorrow

The choice of who comes up is not about who is strongest today. It is about who
can attack **next** turn, who survives the projected hit, and who gives away the
fewest prizes. A wall pinned in place with no attack is worse than a mobile body
that can act. And the bench is never left empty: ending a turn with an empty
bench loses the game outright.

**Two menus ask this question, and they are not the same question.** After a
knockout the choice is resolved on the opponent's turn: the body that comes up
attacks *tomorrow*, today's damage says nothing, and survival is what matters.
After a voluntary retreat the choice happens on our own turn, seconds before we
attack — so "this body hits for X" is a fact, not a forecast, and a body that
finishes the opposing active is worth more than one that merely endures.

The distinction is not only about timing; the boards differ too. **A retreat
swaps two bodies, a knockout removes one.** When we retreat, the body coming up
leaves the bench and the retreating active takes its slot, so the bench is the
same size as before. After a knockout nothing replaces the body that comes up
and the bench is one smaller. Any projection that counts our bench — the attack
that does twenty damage per benched Pokémon is the one in our deck — has to use
the right number, or an attacker that really does finish the job looks like one
that falls short.

### 10.1 What the promotion is actually buying

Four autopsies in two days all landed on the same sentence from different sides:
**the promotion is not a card, it is a seat**, and what the seat is worth is
everything the body can still do once it is in it. Each of the four is a switch
of its own, each was invisible to the winrate, and each was graded by the rules
oracle instead — see [The instruments](instruments.md).

- **The seat brings its ability.** *Teal Dance* reads "if this Pokémon is in the
  Active Spot": on the bench it is dead wood, and the promotion is the act that
  switches it on. A Teal Mask Ogerpon ex two Grass short of Myriad Leaf Shower
  is **one** short the moment it takes the seat — attach by hand, dance the
  other — so a body every projection priced as mute was in fact a 240 over a 210
  HP ex. Read with one route it never reaches its cost, damage returns zero by
  contract, and the menu falls through to ordinary survival points where a 40 HP
  basic conceding one prize outranks a 210 HP ex conceding two. Two guards keep
  it from becoming an investment rule: the charge is claimed only while the body
  is still mute without it, and only on the **forced** promotion, because a
  voluntary retreat happens mid-turn where the Grass in hand may be owed to a
  play this projection cannot see.
- **The seat is what a search completes.** When nothing on the bench survives
  their next hit, the block that looks for an evolution to promote used to read
  the hand as a set of cards. The hand can also be a **route**: with the
  evolution still in the deck and a Pokémon-search Supporter in hand, the seat is
  one Supporter away. The correction is narrow on purpose — the cheapest body is
  not the answer, the cheapest body that is a *seat* is.
- **The promotion can bet the turn's own draw, if the body can walk back.** With
  no energy in hand the agent promoted a 0/4 body with a retreat of 3 over an ex
  one attachment from a lethal through weakness. What was being paid was never a
  guarantee, it was the **exit**: a body that can pay its own retreat costs a
  turn's tempo if the draw misses and wins the game if it hits. The same reading
  is why the match-point veto yields — that veto removes a 2-prize ex because it
  is their whole remaining pile, but their blow arrives a turn of ours later, and
  a body that can step aside is not there to receive it.
- **The fee that decides is next turn's rotation, not this turn's retreat.**
  Against a lock that re-mutes whatever is in front of it every turn, promoting
  the knocker that costs three to rotate out buys the same prize today for three
  times the fee tomorrow. The retreat veto and the promotion tie-break now read
  **the same number** — the cheapest body that cashes the prize — so the menu
  that pays the fee and the menu that picks who receives it cannot disagree about
  which body they are paying for.

### 10.2 The seat at match point — either pile

Everything in §10.1 is an argument about the turns that come **after** the
promotion. At match point there are none, and four boards in one day showed the
ordinary reading losing to that:

- **When our own pile is at one, the seat that closes the game is not a
  tie-break.** The body one charge from the finish beat a last-stand tank by 300
  points of *ornament* — out of an adornment bounded to 0..450 whose own comment
  says it stays far below any decisive rule — and three discounts further down
  could have sunk it, all three arguments about surviving a reply that never
  arrives, because the promotion resolves at the end of *their* turn and ours
  goes first. The rung that guarantees it is bounded on both sides: above the
  last stand plus its whole tie-break, below the body that knocks out **today**.
- **When their pile is at one, the seat goes to whoever survives the reply.** If
  their answer onto the body in front takes the game and the bench holds one that
  outlasts it, the seat belongs to that one. It does not buy a better turn: it
  buys that there **is** a turn — and a reserve rule that vetoes the survivor is
  an argument about turns that are not coming. This is a floor and not an
  assignment, so a knockout of ours still keeps the last word.
- **A body that CAN attack, WILL attack.** The deferred-sacrifice doctrine —
  promote the body closest to attacking that keeps its exit — only covers the
  body that cannot attack *today*. If it can, it attacks, and the exit is never
  used; two wider versions were written and each loses a board already paid for.
  The deferred attacker is therefore never bought with prizes and never steps
  over a survivor.
- **And the almost-ready finisher is offered where nobody KNOCKS OUT**, not only
  where nobody can attack. A body that already hits for less than lethal is the
  same almost-ready body, one charge earlier.

**One more thing at match point, and it is about the plan rather than the
menu.** A pivot that trades the winning blow for a tougher body is arguing about
a turn that does not exist. Durability, prize denial and mismatch all belong to
the **next** turn, so the winning attack is captured before the pivots run and
restored after them — for **both** ways a turn closes a game: their bench empty,
*and* the ordinary one where the knockout simply cashes the prizes we are short
of. With two brakes kept: the knockout must be guaranteed, and it must not be the
suicidal finisher that hands them their last prize.

**And the turn that takes the prize still owes the turn after it.** When our
attack knocks their body out, everything else the turn does is buying the turn
our nearly dead active will not see: the last bench seat belongs to the body
whose ability draws on *that* turn. The condition for playing it is not "the
ability is live now" but "it will be live on our next turn", and an active that
is doomed is exactly the board that says so — after the promotion the seat it
wanted is gone.

## 11. Disrupt on the right order

Hand disruption is cheap value against decks that hoard cards, but the order
matters: strip cards permanently first, then shuffle the hand away. The reverse
order throws away the cards the first effect would have removed for good. Both
also step aside when refilling our own hand is worth more.

Two disruptors in the same turn is one too many. The second one lands on a hand
the first one already emptied, and what it denies there is a card or two — while
the price is the same as always. That price is highest for the one-shot card:
the copy that shuffles both hands is a single copy, and its value scales with
the hand it lands on, so the turn to spend it is the one where the opposing hand
is fat, not the one right after we capped it ourselves. Waiting costs almost
nothing when the card's own condition — one of our bodies knocked out last turn
— reopens every turn against a deck that is knocking us out.

Measure the disruption in cards denied, not in hand size. The shuffle leaves the
opponent at two, so a hand of three gives up one card, and one card is what any
draw engine hands back without noticing. When a body on their board draws them
three the moment we take a knockout — and taking a knockout is exactly what we
are doing on the turn this card is legal — the floor has to be higher still.

And it shuffles OUR hand too. A card in that hand that cannot be played today
because its slot is spent is not a spare: if it is the last copy of the answer
to their main attacker, five fresh cards do not pay for burying it. The refill
is worth its price only while it is not the price.

Disruption is worth nothing on our own first turn going second. The opponent has
just opened, their hand is the smallest it will ever be, and the attacker that
would punish a big hand is not on the board yet — while our refill supporter is
at its maximum, drawing eight with all six prizes untouched into an empty bench
that has room for everything it finds. The refill takes that turn's supporter
slot; disruption only outbids it once the opposing hand is inflated and the
threat behind it is real. The exception is having nothing else: no refill in
hand and no search that brings one.

### 11.1 Being discarded is a decision too, and it happens on their clock

The opponent's hand-cutter takes us to three cards and hands **us** the choice of
which three survive. That is not the mirror image of playing one: it is a
different question, asked at a different time.

**The turn's resources are free, because the turn has not started.** The
Supporter slot and the energy attachment are turn-scoped flags, and on a forced
discard they describe what the *opponent* spent. Their hand-cutter is itself a
Supporter, so "the Supporter slot is already gone" is true on every forced
discard it can ever produce — which made the protection of our last playable
Supporter unreachable code for as long as it existed. The rule that comes out of
it generalises past any one card: **read a turn-scoped flag through the horizon
of whose turn it is**, and when there is no effect to attribute, fall back to
today's reading. It is now checked by the architecture lint (R8).

**The hand that survives is the hand our next turn opens with**, so what it is
worth is what it can do then: attack, unblock, take a prize. Pricing each card
in isolation against static proxies — copies in hand, copies in play, size of
the discard pile — answers a question nobody asked.

**A protection meaning "this is our only out" cannot be handed to two copies.**
A discard menu prices cards one at a time, so both copies of a card receive it,
and only one of them can be the out. The fix shape is a latch — protect once,
then let the second copy be priced on its own merits — and
`utils/duplicate_protection_audit.py` finds where it is missing.

**The last bridge of a line is not fodder, and the asymmetry is the whole rule.**
Every reader of an evolution piece in hand prices it against the board: a link
with no body under it has zero usable copies, and once there is more than one
copy the surplus band makes them the cheapest cards in the hand. Both readings
are right about a copy **the deck can replace** and wrong about the last ones. A
missing seat is a card a search still buys; a bridge in the discard is beyond
every search in the deck, and the top of its line becomes cardboard in every zone
at once. So a cost paid in cards — the Ultra Ball's two, a forced discard —
refuses to price the last bridge as fodder, and keeps exactly one copy while the
surplus falls. The four questions that separate the two cases are: is it a middle
link, is it still unworn, are its copies in hand the last ones any zone a draw or
a search reaches, and are the line's top and Basic both still live. No card is
named — the stages come from the evolution table, so the Dipplin of the Applin
line is covered on identical terms.

This is not the circularity the search rules already refuse ("the deck is not a
seat"): that one vetoes the search that would un-orphan a piece, and no search
un-orphans what it has just thrown away.

The full analysis, the criterion meant to replace the price list, and which
waves have shipped, are in [Discarding well](discard-plan-2026-08.md).

## 12. Walls: the immune body in front

Several meta decks put a body in front that our ex attackers simply cannot
damage. This is the strategic problem the agent invests most in.

**The agent knows six shapes of wall, and only the first three are a body of
theirs that is simply immune.** They are listed in the order the agent learned
them, because what separates them is not the play — that is the same for all
six — but **where the board is read from**, and the later ones read backwards
from the first ones:

| Wall | Where the agent reads it |
| --- | --- |
| Crustle | Their card's own ability: an ex-immune body, by card ID. |
| Cornerstone | Same shape, a different ability list. |
| Milotic ex | Same shape again, and a **third question about the attacker**: not “is it an ex” nor “does it have an Ability” but **“is it Tera”**. It blanks exactly one body of ours — the Teal Mask Ogerpon ex — and lets our other two ex through. See [The wall that reads our Tera](milotic-the-wall-that-reads-our-tera-2026-08-16.md). |
| Neutralization Zone | A **stadium anyone can see**, plus the **absence** of a Rule Box on the body in front — so it comes and goes with *their* promotion. |
| Acerola's Mischief | Nothing on the board at all. The only evidence is the `PLAY` log of their previous turn, and what it pins is a **serial**. |
| The coin dodge (§12.1) | Their previous turn's `ATTACK` log followed by a `COIN_FLIP`. |

Recognising the board is where each of them cost us a game. Once recognised, the
plays are the same for all five:

- promote a **non-ex** attacker that can hit it;
- a wounded wall is not a wall — the agent reads current HP, not printed HP;
- kill the wall before spending Boss's Orders behind it;
- don't feed energy into an attacker the wall is immune to;
- don't fill the bench with bodies the wall cancels. At most **two** Teal Mask
  Ogerpon ex are ever in play, the setup bench included. The bench has five
  slots and against a wall they belong to the pieces that still deal damage —
  Tapu Bulu, the Meganium line, Dipplin — plus room for a Meowth ex. The cap
  also applies at setup, where the opponent has not revealed anything yet:
  there is no cost to holding the third copy in hand, and a benched body can
  never be taken back.

### 12.1 The wall that lasts one turn: the coin of the dodge

Not every untouchable active is a wall we can see on the board. Twelve attacks
in the environment carry the same sentence word for word — *"Flip a coin. If
heads, during your opponent's next turn, prevent all damage from and effects of
attacks done to this Pokémon"* — on bodies as small as a 70 HP Marill (Hide) or
a Hop's Phantump (Splashing Dodge). On heads, nothing we own damages that body
for one turn. There is no marker on the board: the only evidence is **the
opponent's previous turn**, an `ATTACK` log followed by a `COIN_FLIP` log.

The agent reads that pair, and reads it by **attack id**, never by card id: the
effect belongs to the attack, and the same sentence appears on Hide, Splashing
Dodge, Dig, Fly, Dive, Agility, Undulate and Swift Flight
(`COIN_DODGE_ATTACK_IDS`). On heads, and only while that same body is still
active, the turn is replanned exactly as it is against a Cornerstone or a
Crustle:

- **the attack is vetoed** — it resolves for zero and ends the turn for nothing;
- **Boss's Orders becomes the turn**, gusting an attackable body off their
  bench; it outranks a refill, and a refill that would burn the Supporter slot
  yields to it;
- **if the Boss's is not in hand but is alive in the deck**, the routes to it
  are, in order: a Meowth ex from hand (its Last-Ditch Catch fetches the
  Supporter without spending the slot), an Ultra Ball that digs the Meowth ex
  out, or a Night Stretcher that brings it back from the discard;
- **on tails, none of this fires.** Nothing about the board changed; only the
  coin did.

The failure this was written from is worth keeping: with a Lillie's in hand the
agent refilled, drew the Boss's Orders one card too late — the Supporter slot
already spent — and then attacked the hidden body for zero. A refill is not an
answer to a body that cannot be touched.

### 12.2 Neutralization Zone: the wall is the missing Rule Box

Under their Neutralization Zone every ex of ours does **zero** to a body without
a Rule Box. The damage model always knew this; what did not ask was the **energy
routing**, and that is where the turn is given away: against five 70 HP bodies
with no Rule Box between them, both our Teal Mask Ogerpon ex and our Hydrapple ex
are mute, and the only body that can still take a prize is the Meganium sitting
at zero energy on the bench. The single Grass in hand went to a mute ex.

Every per-matchup cap that would have caught it — Cubchoo, Alakazam, Crustle,
Cornerstone — is keyed to a matchup or to a body of theirs, and this wall is
neither, so the question has to be asked of the **current active** every turn.

**The turn is two halves and there is no shipping one of them.** Teal Dance joins
the wall rung it already had for the other walls, with the widest creditor list
of the three (this wall filters by Rule Box, not by our abilities, so every
non-ex of ours is owed, Meganium included); and the **bench** halves of the
stadium's own energy bands stop counting as development while the front is mute.
Without the second half the Grass simply moves from the mute benched ex to the
mute *active* one, which is not a fix.

### 12.3 The shield they buy for one turn, which is not on the board

Acerola's Mischief says the same sentence the Neutralization Zone says — our ex
do zero to the body it protects, effects included — for **one turn**, on **one
body**, and it leaves nothing behind to read it off. No tool, no ability, no
stadium: the protected body looks exactly like the body it was, and the only
evidence is a `PLAY` entry in the log batch of *their* turn, which goes past
once. Its own precondition ("only if your opponent has 2 or fewer Prize cards
remaining") means it lands exactly on the turns that end the game: the loss it
was found in was held at one prize while the opponent never left six, our ex
attacking into a zero every turn from turn 13 to the end.

**It is a serial, not a spot.** The shield travels with the body — gust it to the
bench and the mute goes with it, while whatever comes up in its place is fair
game. A reading keyed on "their active" would mute the wrong body one action
after our own Boss's Orders, which is precisely the answer to the card. Four
places read that serial: the damage model, the veto on swinging into it (an
attack **ends the turn**, and snipers that pick their own target are exempt),
Teal Dance's wall rung, and the forced discard, where the hand stops being priced
for the deck-out race alone.

It is also the clearest case of an instrument being blind by construction: the
differential oracle attributes a prediction to the opposing body whose HP
**changed**, and an attack the shield zeroes changes nothing. Pointed at the deck
that runs the card it reports nothing at all, with the reading on or off.

## 13. The first turn: the body that costs one prize

The first turn does not attack, and often cannot. What it decides is what the
opponent has to chew through next, and what that costs us when it falls.

### 13.0 Who starts in front

Every body in this deck is a basic, the ex included, so "start with a basic"
means **start with a basic that is not an ex**. That is the whole difference the
setup decides: when the opponent takes their first knockout, it pays one prize
or it pays two — and most of the field reaches a 210 HP ex on its *second* turn,
which, if they go first, is our second turn, before we have attacked once.

The order among the non-ex basics is **Tapu Bulu, Applin, Chikorita**, and it is
not "sturdiest first". Tapu Bulu (140 HP) is the only one-prize body that both
endures a turn and is a real attacker afterwards, and it has no ability, so the
decks that cancel ex or abilities cannot switch it off. Applin (60 HP) goes
ahead of Chikorita (70 HP) because what the active spot buys on turn one is not
survival — both are donkable and both pay a single prize — it is which line
starts developing, and Applin opens Dipplin → Hydrapple ex, the attacker the
deck is built around.

Only a hand with none of the three reaches the ex, and there the order is **Teal
Mask Ogerpon ex, Fezandipiti ex, Meowth ex**: it is a fallback, not a
preference, so what ranks them is which of them the first turn can still use.
Teal Dance develops from the active spot; Flip the Script only pays out after a
knockout; Last-Ditch Catch works from the *bench*, so the active spot wastes the
Meowth ex outright.

No ex ever outranks a non-ex basic, not even one the order does not name.

### 13.1 …and what the first turn does about it

The body we want in front is a **basic worth one prize that is hard to remove**
— in this deck Tapu Bulu, but the agent recognises it by its properties (basic,
one prize, high HP, and a real attacker), so another deck's equivalent inherits
the rule. Three things follow from that:

- it goes on the bench **before the hand refill**. A Supporter that shuffles the
  hand into the deck takes it with it, and it is the one card in that hand that
  drawing more cards cannot replace;
- the energy for the turn goes to the **active**, up to its retreat cost, when
  the plan is to swap: the engine only offers a retreat once the cost is already
  on the body;
- if the turn has no attack in it, the active retreats and the wall takes the
  front. Fewer prizes when it falls, and turns spent on it are turns we spend
  building the bench.

There are two reasons to make that swap, and they are not paid for in the same
way. One is a **threat**: their projection, counting the attack they have and
the one it becomes in a single step, takes the body in front down and does not
take the wall down. The other is the **prize count** on its own — an ex in front
is a two-prize body standing where a one-prize body could stand, and waiting
until the threat arrives is waiting until the swap is no longer cheap, because
an ex with its energy on it cannot be pulled back for a single attachment.

The difference is what each is worth. A threat is worth **buying** the retreat:
the turn's energy goes to the active, up to its retreat cost, because the engine
only offers a retreat once the cost is already on the body. Denying a prize is
not worth that — the energy would be leaving an attacker half assembled to pay
for walking away — so it only fires when the cost is already sitting on the
active. Going first on turn one neither applies: the opponent has not played a
card, so there is nothing to answer and nothing to deny.

The rule stands down completely against a deck whose active makes our ex do
**zero** damage. There the one-prize body is not a shield we spend, it is the
only attacker we have, and hiding an ex behind it would be hiding an ex behind
our own plan.

### 13.2 When the setup could not seat a basic

A hand that only had ex in it puts a two-prize body in front, and the first turn
tries to buy that back. Two plays, and then the swap:

- the single attachment of the turn goes to the **active ex**. It is not
  overcharging an opening attacker: the engine only offers a retreat once the
  cost is on the body, so an unpaid fee means the ex simply ends the turn in
  front;
- a one-prize body is produced for it to retreat into — from hand, and failing
  that with a **Poke Pad**, searching in the same order (Tapu Bulu, Applin,
  Chikorita). Tapu Bulu is claimed even when the bench already holds a one-prize
  body, because it improves a swap that was going to happen anyway; the other
  two only when the bench has nothing to promote, since a second body benched on
  top of the first is a second prize given away for one swap.

Then, at the end of the turn, **the ex retreats and the one-prize body takes the
front**. That is the *default*, not a list of decks, and the reason is the shape
of the mistake it fixes: the damage projector is honest about what an opponent
can pay today and blind to what their line becomes in one card, and the lines
that turn a harmless opener into a 200-plus body on their second turn are most
of the format. Naming them would default an unknown deck to the wrong answer —
and an unknown deck is exactly the one whose evolution we cannot project.

What *is* named is the short list of openings where hiding the ex is wrong:
**Marnie's Grimmsnarl, Cynthia's Garchomp, Crustle Wall, Sylveon, Cubchoo,
Comfey, Ralts/Gardevoir** — none of them can cash the ex in early, so a retreat
fee out of the turn's only attachment buys nothing — plus **Cornerstone**, which
is the same sentence as Crustle Wall. Against those eight the ex stays in front
and the second turn picks the matchup plan back up with the board intact.

Two more guards keep the default honest. It is an *opening* rule — stated for
any turn it fires ten times a game, because "we cannot attack" is the ordinary
shape of a developing turn, and each firing discards an energy and hands over a
cheap body for nothing. And it stands down when the projector **already** sees
the knockout: a wounded ex in front of an attacker that reaches it belongs to
the pivots built on that projection, which know that a benched body surviving
the reply hands over *zero* prizes — and no rung of a one-prize order beats
zero.

## 14. Play order

Two plays can both be right and still lose the turn if they happen in the wrong
order. The agent enforces a sequence: energy that enables a knockout, then the
stadium, then evolutions and development, then searching, then ordinary energy,
then the rest. Ordering never overrides a veto — it only sorts plays that were
already worth making.

**And a play the scorer never learned is not "worth making" by default.** The
ABILITY scorer dispatches by card id and gives everything it does not name a
generic 29000 — the band of a real play. Stadiums are **shared**, so the
simulator offers us the ability of *their* stadium too, and each of those landed
on that fallback above the Supporter in hand: on one turn it beat playing a
Lillie's Determination, fired, and its sub-selection buried that same Lillie's in
our deck. An unscored effect must not be paid for with a card from hand, so the
stadium slot is vetoed by **area** with the one ability this deck actually
plans around (Grand Tree) decided above it by id. See [the
write-up](academy-at-night-a-stadium-ability-nobody-scored-is-not-a-free-play-2026-08-16.md).

**The attack goes last, because it is the play that ends the turn.** When the
attack and something else are both worth doing, comparing what they are worth
is the wrong question: the attack does not consume the supporter, the ability or
the attachment, and none of them consume the attack — but the turn's supporter
slot, its ability and its attachment do not carry over to tomorrow, and the
attack takes them all with it. So the question is not "which is worth more", it
is "which of the two can still be played afterwards", and the answer is only
ever the attack. Every non-accumulating resource is sorted above it: the
attachments and abilities by their tier, and the turn's supporter by a net that
lifts it just over an attack about to win the menu. Two limits keep it from
burning cards: a supporter scoring in the last-resort band is saying it has no
useful effect today, and a gust is excluded because it rewrites *who* the attack
hits — gust and attack really are alternatives. The one attack that is never
delayed is the one that wins the game: nothing survives the turn if the turn is
the last one.

**What the hand pays goes before what spends the hand.** A play that empties the
hand — any refill that shuffles it into the deck — destroys every card still
sitting there, so whatever was going to spend one of those cards happens first.
An Ultra Ball is the same destroyer with a smaller mouth: its cost is two cards
it *chooses*, and a spare Basic Energy is exactly what a discard scorer reads as
surplus. So the free ability that pays with a card from hand goes ahead of it —
and Teal Dance is the case where the order is not even a trade-off, because it
takes one card and draws one back. The hand is the same size afterwards, so the
search is just as legal, is decided with one more card of information and one
more candidate to pay its cost with, and the Grass lands on the attacker instead
of in the discard pile. The draw can even be the card the search was digging
for.

The other half of that sentence is where the rule stops. Ripening Charge
attaches and *heals*: it hands nothing back, so playing it first leaves the hand
one card smaller, and an Ultra Ball with fewer than two cards to discard is an
Ultra Ball that dies in hand — the failure that put the whole UB→Meowth→Lillie's
engine ahead of the attachments in the first place. There the order buys a card
on the board and pays for it in fodder, which is a trade-off, and this rule only
claims the half that is free. Both halves are read off the printed text of every
card in the environment, so they hold for whichever search and whichever
charging ability a deck ends up running.

**A rule and its own special case have an order too, and the general one goes
first.** `_attach_enable_retreat_ko` -- energy onto the active so it can retreat
towards a benched attacker that finishes the job -- generalises an older rule
that said the same thing about one body in particular (a Tapu Bulu with four
Grass). The `elif` chain tested the special case first, and its band was fitted
back when its only competition was bench *development*, so on exactly the boards
the special case covers the lethal line scored below a routine bench *charge* and
lost. The agent declined a knockout it had already found. When a rule is
generalised, the general one takes the chain's first seat and the special case
keeps its own band for whatever the general one does not claim.

**And a reservation cannot veto the body it is reserving for.** *The active
needs the energy and the hand holds one card of it, so don't spend it charging
the bench* is a rule about where the card goes, and it was being applied to
the active's own Teal Dance — the ability that attaches to *itself*. On the
active that ability is not competing with the reservation, it *is* the
reservation being honoured, with a card drawn on top. Meanwhile the manual
attachment to that same body yields to the ability by an older rule, so between
the two of them the energy every rule agreed belonged to the active had no way
of reaching it: it sat in hand priced as a reserve, under the ceiling that
decides play order, until an Ultra Ball discarded it as surplus. The guard is
the one the sibling rule for Ripening Charge had carried all along, and it
subsumes what used to be an opening-turn exception — the same sentence, gated
on turn one. The bench half of the reservation stands: a benched body dancing
really would eat what the active is waiting for.

---

## How these rules get added

A rule is not added because it sounds right. It gets proposed from a real loss,
implemented, and then **measured**: if it does not change decisions, or it
changes them without winning more games, it is reverted. See
[Improving the agent](improving-the-agent.md).

One qualifier the measurement discipline had to learn about itself: **"neutral"
sometimes means "below the instrument's resolution", not "no effect".** A change
that alters one decision in 3 580 cannot be separated from noise by any
affordable number of games — the confidence interval is two orders of magnitude
wider than the effect. There the call is made on correctness, not on the
winrate, and the census that measured how rare the change is has to be run
*before* the games, not after. See [The instruments](instruments.md).

Since 14 August 2026 that call has a second instrument behind it rather than a
judgement call alone. The **rules oracle** rolls the engine's own rules forward
from the disputed board and reports who wins and by how many prizes, so a change
the scoreboard cannot resolve can still be graded against something other than
another heuristic. Most of §10.1 and §12 above entered on exactly that evidence:
**neutral in winrate, positive under the rules, and a census showing the board is
not a corner case.** Every one of them is marked as such where it shipped.

Next: [Matchups](matchups.md) · [Improving the agent](improving-the-agent.md) · [The instruments](instruments.md)
