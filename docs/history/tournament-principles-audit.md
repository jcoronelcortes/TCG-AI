# The five tournament principles, audited against the code

Night of 2026-08-07. The question is not "is there a bug" but "does the agent
play the way a tournament player plays". Each principle is answered with the
place in the code that implements it, or with the reason nothing does.

---

## 1. Prize mapping — *plan how the six prizes are taken*

**Implemented, for ONE turn.** `ptcg/turn/game_plan.py` builds a `TurnPlan` per
observation and answers three questions before the first decision: is there a
route that closes the game today (`win_route`, one of ACTIVE / PROMOTE / GUST /
RECOVER), how many prizes can we take today (`prizes_today`), and how many they
take on the reply (`op_prizes_next`, `op_wins_next`). The four modes
WIN_NOW / DENY / RACE / DEVELOP are that sentence.

The prize *value* of every body is priced everywhere: `prize_count` for ours,
`prize_count_op` for theirs (with Pecharunt and Mega Gengar denial), the gust
target ranked by prizes, the promotion preferring the cheaper corpse, the
retreat choosing who pays the bill (3d75c40).

**The gap: nothing maps a route longer than one turn.** There is no "I am on
four prizes, their board offers a 2 + 2 and then a 1, so the 2-prize bodies come
first while they are reachable". Two concrete consequences:

- *the last prize can become unreachable*. Taking the cheap knockout first can
  leave a board where only 1-prize bodies remain while we still owe three, and
  the deck clock (`the deck is the clock`, strategy §3) runs out first.
- *`prizes_today` is a count, not a route*. A turn taking one prize and a turn
  taking two rank the same in the mode.

**Candidate (queued as F4-a): the prize ledger.** Sum the prizes reachable on
their whole board against the prizes we still owe, and let a knockout that keeps
the route feasible outrank one that does not. Cheap to compute, and it plugs
into the existing `prizes_today` rather than replacing anything.

## 2. Deck checking — *know what is in the prizes*

**Implemented, and better than the principle asks.**
`ptcg/state/tracking.py::_identify_prizes` reconciles the whole deck on every
COMPLETE reveal (Ultra Ball always reveals it): any copy that is not in deck,
hand, play or discard is in the prizes. There is no one-shot lock, so the belief
corrects itself all game. `ACTIVE_CARDS_IN_DECK` keeps the per-zone census that
the search cards read, `ptcg/calc/probability.py` turns it into draw odds
(`_p_at_least_one`, and the "all copies prized" branch), and
`ptcg/turn/options/card.py` already downgrades a search whose target is prized
with no accessible copy left.

**No gap found.** This principle is the one the agent is strongest at.

## 3. Sequencing — *the order inside the turn changes the result*

**Implemented, and it is the densest part of the code.** The order rules are
explicit and each came from a lost game: the Supporter goes before the retreat,
the attack goes LAST because it closes the turn, Xerosic before the Unfair
Stamp, the search is spent BEFORE the item lock lands (Dragapult), Bug Catching
Set before benching, Teal Dance before the manual attachment, the gust waits for
the charge when the knockout is one energy away (`win_needs_charge`).

**One structural note rather than a gap**: the ordering vetoes are pairwise
("A yields to B"), and the turn plan exists precisely because a pairwise veto
could not see that the turn was about ending the game (registro_013). That is
the right fix and it is in place; new order rules should hang off the plan's
mode rather than adding another pair.

## 4. Resource management and board symmetry — *do not over-commit*

**Implemented per card, not as a principle.** "Do not bench a body you will not
use, it is a free Boss's target" exists as a dozen local rules -- do not expose a
second Meowth ex, do not pay an Ultra Ball for a bench slot worth less than two
cards, the bench cap of two Ogerpon, the bench slot reserved for the Last-Ditch,
never end a turn with an empty bench. Energy has caps per body and per matchup
(Applin max 1, Ogerpon caps vs Crustle and vs Hop's, Cubchoo reserve).

**The gap is a general reading**: there is no single number for "how many prizes
are sitting on our bench that their gust can reach". Each rule re-derives it in
its own context. Not obviously worth a rule of its own -- the local versions are
the ones that were measured -- but it is where a general one would go.

## 5. Reading the opponent — *archetype early, and their tempo*

**Half implemented.**

*The archetype half is done, and early.* `main.py` infers the archetype from
their DISCARD two or three turns before the board shows it, and only the
strategic flags are inferred that way -- the positional ones ("there is a wall in
front") still come from the board. There is an explicit guard against turning on
a whole matchup plan from a single tech card.

*The tempo half does not exist.* The agent never asks what the opponent DID on
their turn. Two specific holes:

- **`_op_disruption_belief(op_state, op_supporter_played)` ignores its second
  parameter.** The function computes the odds that their hand holds disruption
  from the hand SIZE alone; the caller passes `False` as a literal
  (`main.py:6129`) and the parameter is unused in the body. The signature knows
  the question and the body never asks it.
- **Nothing tracks their discard between our turns.** Their discard pile is
  fully visible in the observation. Counting the Supporters in it and comparing
  with our previous turn tells us whether they played a Supporter at all -- the
  standard read for "their hand is stuck", which is exactly when pressing and
  when NOT spending our own disruption pays.

**Candidate (queued as F4-b): the tempo tracker.** One snapshot per turn of
their discard size and Supporter count, exposed as "turns since they last played
a Supporter". It feeds the disruption belief that already has a parameter
waiting for it, and the Unfair Stamp / Xerosic decisions that currently reason
from hand size alone.

---

## Verdict

Three of the five are implemented at tournament standard (2, 3, and the
archetype half of 5). Principle 4 is implemented case by case rather than as a
reading, which is defensible because the cases are what got measured. The two
real holes are **the multi-turn prize route** and **the opponent's tempo**, and
both are cheap to compute from data already in the observation.

## Findings that came out of the audit and are already fixed

- **634 duplicated lines in `ptcg/`** (five modules carried a verbatim second
  copy of themselves, including `prize_count` / `prize_count_op`). Removed, and
  R5 in the architecture lint stops it coming back. Commit 43213fd.
- **The whole `op_scaling` table is opt-in** (`scaled=True`) and today only the
  turn plan reads it. That is documented and deliberate -- the thresholds
  downstream were fitted to the blind number and turning it on everywhere
  measured negative three times out of three -- but it means every new entry,
  Settle the Score included, is invisible to the defensive rules. Worth knowing
  before proposing "the agent should see attack X".
