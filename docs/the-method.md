# The method

[← Documentation index](README.md)

This page is the **long form of how work actually gets done here**, written so
that someone starting from a different deck — a different sixty cards, a
different metagame, possibly a different card game — can rebuild the same
process from scratch.

[Improving the agent](improving-the-agent.md) is the six-line summary of the
loop. [The instruments](instruments.md) is the catalogue of the measuring
apparatus. This page is the part neither of them holds: **the anatomy of one
finding from the moment a game is lost to the moment a rule is merged or
buried** — how a board is described, how it is reproduced, what the menu of
possible fixes looks like, how each one is tested, and what the number at the
end is allowed to mean.

Nothing on this page is about our particular list. Where a concrete card
appears, it is an illustration; the sentence around it is the reusable part.

---

## Part 0 — The two facts the whole method is built on

Everything below follows from two things that were measured, not assumed.

### 0.1 The discovery channel is a human reading a lost game

On 12 August 2026 the thirteen defects fixed that day were traced to their
source. **All thirteen came from a person reading the JSON of a game that was
lost.** Zero came from the 2 400-test suite, zero from the 3 580-decision frozen
corpus, zero from the differential oracle, zero from the invariant monitor, zero
from self-play.

This is not a complaint about the tools. The entire apparatus is built to answer
*"did this change something we already knew?"* — that is a **regression net**, and
it is excellent at it. Nothing in it answers *"what is wrong that we do not know
about yet?"*

Two consequences that shape every step below:

- **Losing games is the raw material.** Play, record, read the losses. A day
  that produces no read-through of a real loss produces no findings, however
  many tests it runs.
- **When a day produces N defects, the highest-value work is not fixing the
  N+1st.** It is grouping the N into **classes** and building the detector that
  finds the class without a human in the loop. That is how every census and
  audit in `utils/` was born, and each one is named after the class it hunts.

### 0.2 The winrate instrument saturates, so it cannot be the referee

Against a generic scripted opponent the agent wins about nineteen games in
twenty however it spends a turn. Consequences, each one measured:

- A rule that changes **one decision in 3 685** cannot be separated from noise
  by any affordable number of games. Six changes in a row in August 2026
  measured neutral for exactly this reason.
- The per-matchup noise floor at 200 games is ±6.5 points; a mirror run with
  *identical code* on both arms has come back at 57.0 % with an interval that
  excluded 50 %.
- Even at n=5 000 per arm, one deck's control row — **the same code in both
  arms** — separated by +1.50 points with z=3.13, p=0.002. A naive significance
  test called that significant.

So the method never asks the winrate to arbitrate quality. It asks it one
question — *did this cost anything?* — and gets its verdicts from three cheaper,
sharper places: **the population** (a census), **the flips** (the corpus), and
**the rules themselves** (the oracle).

---

## Part 1 — The apparatus you need before step 1

You cannot run the cycle without these. Build them in this order; each one is
useful on its own, and each later one assumes the earlier ones.

| # | Piece | Answers | Deck-specific? |
| --- | --- | --- | --- |
| 1 | **A harness that plays whole games** headlessly with two independently loaded agents | "does it still run" | No |
| 2 | **A record splitter**: one game log → one file per turn | "which turn was it" | No |
| 3 | **A single-decision replayer**: feed one recorded observation to the agent, get the choice back | "what does it pick *today*" | No |
| 4 | **A scenario builder** with strict card accounting | "what would it pick on a board that never happened" | The card pool, yes; the builder, no |
| 5 | **A frozen corpus**: N recorded games, committed, replayed on every change, diffing every decision | "what did this change flip" | The recordings, yes |
| 6 | **An opponent corpus** harvested from the real ladder, with a meta weight per list | "who do we actually play against" | Entirely |
| 7 | **A behaviour suite**, one file per mistake, each carrying the game it came from | "did this come back" | The boards, yes |
| 8 | **An architecture lint** with a rule per class of defect that once shipped green | "is this the shape of a bug we already had" | No |

Two design decisions in that list are load-bearing and easy to get wrong:

**The frozen corpus must be committed and unable to heal itself.** A corpus that
reads a git-ignored scratch folder will silently re-snapshot when the data
underneath changes, and then report *no changes* forever while your change flips
decisions. This happened here. Keep two: a **local** one over transient records
(convenient, self-healing, not a gate) and a **frozen** one that is committed and
only ever updated through an explicit, reviewed command.

**The opponent corpus is numbered by meta share, so a name is a position, not a
deck.** Re-harvest the ladder and `<archetype>_6` lands on a different list.
Match findings to lists **by content**, never by name.

### The bootstrap order, if you are starting today

1. Harness + replayer + splitter. Until you can reproduce one decision on
   demand, you have stories, not findings.
2. Play a few hundred games against whatever opponent you have, record them,
   and **read three losses by hand**. That is your first backlog.
3. Suite + frozen corpus, seeded from those three.
4. Harvest real opponents. Everything before this is measured against a
   strawman.
5. Censuses and gates, one per candidate rule, from then on.

---

## Part 2 — The cycle

```text
1. FIND       a weakness that costs real games
2. DESCRIBE   the board, the menu, and the arithmetic — before touching code
3. REPRODUCE  the exact decision, today, on the current tree
4. DIAGNOSE   which sentence in the code is wrong, and why it survived
5. DESIGN     choose among the shapes a fix can take
6. PIN        a test that fails before the change and watches the new lines
7. MEASURE    population → flips → cost → grade, cheapest first
8. DECIDE     ship, ship-marked, or bury — and write down which, with numbers
```

Steps 2 and 4 are the ones usually skipped, and they are where the method earns
its keep. Roughly half the entries in this project's memory are cases where the
board was real and **the first diagnosis was wrong**.

---

### Phase 1 — FIND

Five channels, in descending order of how much they have actually produced.

**1. A human reads a lost game.** The only discovery channel (§0.1). Look for
turns that ended without attacking, prizes that were never taken, a body that
sat in hand for a hundred steps. Pick losses, not wins.

**2. Ask which matchup is genuinely hard.** Not by name and not by winrate —
**by prize differential**. Two lists that shared a name and 28 differing cards
were the only two negative-differential decks out of forty, and their winrates
differed by twelve points. We win some games without winning the prize race;
that is the deck acting as a clock, and the differential is what exposes it.

**3. Run the censuses that ask "is there anything to write a rule about".**
Resources declined per turn, rules that never fire, turns that ended sterile
while a scoring line existed, menus where an ordering beat a value, ties where
the scorer has no opinion. Each of these is a *worklist*, not a finding.

**4. Audit the tables of card IDs, in both directions.** An ID in the table
whose card does not say that thing, **and** a card that says it and is in no
table. The second direction is the one that finds new mechanics: a wall that
blanks exactly one of our attackers went unnoticed for weeks because the audit
only ever read cards that appear in a corpus deck, and that card is in **0 of
408** lists.

**5. Look for collisions.** A rule written for matchup A vetoing the play
matchup B requires. Measure the resolution rate of the *same* canonical
situation across every opponent: a rate that collapses for **one** deck accuses
the code; a rate that is low across **all** decks accuses the detector.

> **The trap at this phase.** A worklist item is a candidate, not a finding.
> Half of them evaporate at Phase 2 or 3. Budget for that.

---

### Phase 2 — DESCRIBE the scenario

This is a written artifact, produced **before any code is touched**. It is what
makes the rest reproducible by someone else, and writing it kills a good share
of candidates on its own.

#### The anatomy of a board write-up

Every finding here is described with the same eleven items:

1. **Identity** — episode ID, record file, step, turn. This is the primary key.
   A board's identity is *episode + step*, never a filename: the files are
   regenerated by tools and the names move.
2. **Result and score** — won or lost, prizes on both sides. "Lost with one
   prize left" is a different problem from "lost at six".
3. **The opponent** — the archetype *and* the actual list, since two lists of an
   archetype can carry different tech.
4. **Our board** — active, bench, energy on each body (**effective**, if
   anything doubles it), hand, discard, stadium.
5. **Their board** — same, plus current HP, not printed HP. A wall at 110 of 270
   that heals is a different sentence from one at full.
6. **The menu** — every option the engine actually offered, in order, with the
   one that was chosen marked. This is non-negotiable: if the play you think
   should have happened is **not in the menu**, the problem is not the scoring
   and the whole analysis changes.
7. **The arithmetic** — the damage sum, spelled out, with weakness *and*
   resistance. "30 + 30 × 7 = 240 over 210" is what makes a claim checkable.
8. **What it chose, and what it should have chosen.**
9. **What that cost** — a prize, a turn, the game.
10. **The sentence** — one line, deck-agnostic, that states the general rule the
    board teaches. This becomes the title, the test name, the switch name and
    the memory entry.
11. **The controls** — the neighbouring boards where the *old* behaviour is
    right. Every rule needs at least one, or you have written an unconditional
    preference.

#### Three checks that must happen before designing anything

**Resolve the IDs.** The log carries numeric IDs. Twice, a diagnosis named cards
that were not on the table — three 60 HP bodies read as one species were another
entirely, and the rule would have arbitrated the wrong flag. Dump active, bench
(with pre-evolutions), discard and stadium **by name**, from the card table.

**Age the log.** A recorded game was played by whatever version was deployed that
day, and this project merges a dozen rule commits daily. A defect read off a
record can already be fixed. Date the episode against the fix commit and, if in
doubt, bisect **over the record itself**: replay that one observation on each
candidate commit. On 16 August a promotion defect had been repaired hours earlier
by an unrelated commit — what was still broken was not the choice but *what the
choice depended on*, which was a different and much smaller rule.

**Read the menu, not the story.** The engine's own offer is the ground truth. An
option that is absent was illegal, and no amount of scoring will produce it.

---

### Phase 3 — REPRODUCE

A weakness you cannot reproduce is a story. Three ways in:

**From a record.** Split the game into per-turn files, take the item that is
*active*, belongs to *our* seat and carries a decision request, and feed it to
the agent.

Four mechanical traps, all of which have cost hours here:

- **The recorded `action` is offset.** In this log format the `action` on an
  entry is the action taken on the **previous** entry's observation. Read it
  without correcting the offset and you attribute the decision to the wrong
  step. A replay tool that got this wrong reported 35 divergences of which 32
  were its own artefact.
- **One process per file.** The agent carries per-turn state between calls, so
  replaying several records in one process gives different answers than
  replaying them one at a time. Only the latter is comparable.
- **Replay only our own active frames.** Passing the opponent's frames through
  the agent pollutes its card tracking, and the decision you reproduce is not
  the one that happened.
- **Our seat is not always seat 0.** Detect it, and verify the detection: a
  corpus once voted for the wrong seat in a mirror game and replayed **zero** of
  our decisions while reporting "no changes" for weeks.

**Synthetically.** If the position is hypothetical, or if the record is not on
disk, build the board with the scenario builder rather than editing JSON. Strict
accounting — every card in some zone, the leftovers equal to the face-down
prizes, an exception otherwise — is what stops you from testing an impossible
board.

**Then get the reason, not the score.** A score tells you how much; it does not
say which rung of which ladder produced it. If the rule chains return a trace,
assert against the **trace**: a test pinned to a number dies when a band is
renumbered and survives when the wrong rule fires at the right number — exactly
backwards.

**Finally, classify the failure:**

- the play you wanted scored **negative** → a **veto** fired; find the flag and
  the precondition that turned it on;
- it scored **positive but lower** → it lost on **value** or on **order**. If it
  never reaches the top of the menu, check the ordering tier before touching any
  number.

---

### Phase 4 — DIAGNOSE

The board tells you the agent was wrong. It does not tell you which sentence in
the code is wrong. These are the shapes that have recurred often enough to check
by name — a triage list, roughly in order of how often each one has been the
answer.

| # | Shape | Signature |
| --- | --- | --- |
| 1 | **The mechanic is not modelled at all** | The card is nowhere in the code and the fallback band paid it like a real play. *Absence of a rule is itself a price.* |
| 2 | **A twin hole** | The correct guard exists — on the *other* menu that does the same thing. Promotion vs retreat, fetch vs play, offensive chain vs jam chain. **Whenever you fix one, grep for its twin.** |
| 3 | **The reading is by card ID where it should be by property** | A guard closed on a specific card excludes exactly the body it should protect. Ask by *rule box*, *ability*, *type*, *can it attack* — not by name. |
| 4 | **The reading is one question too coarse** | "It is on the board" is not "it can be evolved today". "It is ready" is not "it can reach the front". "The bench is full" is not "there is a second attacker". |
| 5 | **A veto priced against something that cannot happen** | It defers to an Item under a lock, to a search that reaches a discard, to a reply that arrives a turn too late. A veto that yields to nothing yields nothing. |
| 6 | **Order beat value** | The tier decided before the score did, and the tier has no matchup inside it. |
| 7 | **A cap or reservation outliving its turn** | Something priced for this turn was still held tomorrow, or a reserve vetoed the very body it was reserving for. |
| 8 | **The plan points somewhere and suppresses the menu** | Pointing the plan's attacker at the bench removed the attack option entirely. Check what a plan field *disables*, not only what it enables. |
| 9 | **A flag with no premise** | It was raised on a condition that has since died and nothing lowers it. |
| 10 | **A shared resource counted twice, or a cost double-charged** | The turn's attachment already spent, an ability already used, a copy already discarded. |
| 11 | **The turn that ends the game reasoned about the next one** | Durability, prize denial and reserve are all arguments about a turn that will not happen. |
| 12 | **The instrument is wrong, not the agent** | See Part 3. Check this *first* if the finding came from a detector rather than from a human. |

Two habits that make diagnosis converge:

- **Find the asymmetry.** When one half of a card is right and the other is
  wrong — the fetch prices it at 1400 and the play vetoes it — the difference
  between the two halves is the bug, and it hands you the fix.
- **Ask why it survived.** A defect that lived for weeks usually had a *hider*:
  a corpus that labelled the decision with the wrong card name, a test that
  skipped itself, a census whose denominator was wrong. **Fix the hider in the
  same change**, or the next one hides too.

---

### Phase 5 — DESIGN the fix

There is a small, finite menu of shapes a fix can take. Choose deliberately; the
shape decides how it will be measured.

| Shape | Use when | Cost |
| --- | --- | --- |
| **Model the missing mechanic** | Shape 1 above. A term in the canonical damage/threat model. | Must be added to *every* inline copy of that arithmetic — there are usually more than you think. |
| **New named rule with its own constant** | The board is a real, recurring sentence. | Needs a census and a band argument. |
| **Widen or narrow an existing guard** | A twin hole, or a reading one question too coarse. | Cheapest and most often correct. |
| **Turn a preference into a veto** | The option must *never* be chosen. | Scoring it low and hoping is not a fix. |
| **Change the ordering tier** | It lost on order, not value. | The most dangerous: reorders everything. |
| **Fix the instrument only** | The finding came from a detector. | Frequently the whole change. |
| **Do nothing, and write down why** | The population is below your criterion, or the fix loses controls. | **A measured "no" is a deliverable.** |

Five placement rules, each from a defect that shipped:

1. **Caps and ceilings go in the wrapper, not at the end of the function.** A
   ceiling applied last silently overrides every rule above it.
2. **A scorer prices an option; it does not write state.** A flag assigned while
   scoring takes the value of whichever option was scored last.
3. **The general rule goes before its special case**, and **a new reading is
   asked second, never as a replacement.** Replacing a ballot swallows every
   question the old one asked — that is exactly how a lethal-energy scenario
   disappeared behind an archetype whitelist.
4. **Give every new rule its own named constant and its own switch.** The
   constant is what lets you neutralise the rule to measure it without touching
   git; the switch is what lets you ship it off. Both have paid for themselves
   many times.
5. **Bound the new band on both sides**, and say what it must beat and what must
   still beat it. A number with no neighbours stated is a number nobody can
   review.

And the rule that makes the work portable:

> **Write the sentence, not the card.** The rule that came from one stadium is
> phrased about *any unscored ability in the stadium slot*; the rule from one
> wall is phrased about *the attacker property that wall reads*. A rule phrased
> about a card is re-broken by the next set; a rule phrased about a property is
> not.

---

### Phase 6 — PIN it with a test

**The test is written to fail before the change**, and the failure is checked.

- **Real board → fixture.** Hypothetical board → scenario builder.
- **Assert the reason, not the score** (Phase 3).
- **Every test carries a control**: the neighbouring board where the old
  behaviour is still right, in the same file.
- **Kill the mutant.** Remove the new reading — empty the table, flip the switch
  off — and the test must go red, and the old decisions must come back. If the
  test passes with the change disabled, it watches nothing.
- **A test may never hang off transient data.** A test reading a git-ignored
  scratch folder skips itself when the folder is regenerated, and `1 skipped`
  reads exactly like a pass in a summary line. Derive the board from a committed
  fixture instead. This has silently disabled five tests mid-session.

---

### Phase 7 — MEASURE

Run in this order. **Cheapest first, and each row can end the exercise.**

| Order | Question | Instrument | Ends the exercise when |
| --- | --- | --- | --- |
| 1 | Does the situation even happen? | **A census of the rule's own predicate** | Population below your written criterion → stop, record the number. |
| 2 | What historical decisions did it flip? | **Golden + frozen corpus** | An unintended flip → the change is wrong. |
| 3 | Do my new lines have a watcher? | **Mutation over the changed lines** | A survivor → the test is decorative. |
| 4 | Does it cost anything? | **Two-arm gate with a control arm** | A loss that clears the control's floor → revert. |
| 5 | Was it the better play? | **The rules oracle, on the board it came from** | Negative over the board's own floor → revert. |
| 6 | Is a gain here paid for elsewhere? | **Matchup matrix, weighted, with a control card** | Collateral outside the noise floor → narrow it. |

#### The census comes first, always

It costs minutes; 200 games does not. Several rules here were written, measured
neutral and reverted for a population under a tenth of a per cent of decisions.
Ninety thousand games were once spent confirming what a census had said three
days earlier.

Four things a census must do, each learned from one that lied:

- **Count the right unit.** Count **distinct turns**, not valuations: one board
  can be priced eleven times inside a single turn, which inflates exposure by an
  order of magnitude.
- **Neutralise its own switch**, so it always measures the *exposure* — the
  world the rule was written for — rather than the post-fix world where the
  population no longer exists. When the fix deletes its own population outright,
  **give the baseline its own games and print both rows**: the baseline row is
  what proves the instrument can produce a non-zero before you report the
  candidate's zero.
- **Report the denominator and split the flips.** A flip count with no shape row
  cannot tell *never happens* from *never measured*.
- **Include a leakage row**: the same count on lists the rule cannot legally
  fire against. Zero there is what proves the rule stayed inside its matchup.

#### The two-arm gate, and its control

A gate is written **per candidate rule**, not per project. Three requirements:

1. **Export both trees**, package included. A gate whose arms share modules from
   the working tree measures exactly zero — and zero orders a revert here.
2. **Print provenance.** Each arm must state what it actually is; verify the two
   arms resolve to **disjoint paths**.
3. **State its own control**: an opponent the rule *cannot* fire against, run in
   the same session. **A delta that does not clear the control's floor is not a
   delta.**

Three refinements that matter more than sample size:

- **Seed the engine if you can.** With paired seeds, two identically-executable
  arms come back at delta **exactly 0.0000** across every matchup. The control
  group stops being a noise estimator and becomes an assertion. It only holds
  while both arms *decide* the same — once the candidate diverges, variance
  returns in that deck alone, which is still most of the corpus for free.
- **Spend the budget by meta weight.** Same games, weighted allocation: the
  interval on the weighted figure went from ±1.50 to ±0.46. Keep a floor per
  list so the tail retains regression coverage.
- **If the rule has two consumption points, measure each half separately.** The
  halves are **nested** inside the total, so they cannot straddle it. When the
  full rule read −1.10 and its two halves read −0.20 and −0.10 — and in one deck
  both halves were *worse* than the whole that contains them — the contradiction
  is internal and refutes the loss without appealing to a second roll of the
  dice. This is cheaper and more conclusive than another control run.

#### Isolating one rule when the tree is dirty

Do not use a git ref: it exports the whole tree, so the candidate arm carries
every uncommitted change you have. Instead **set the rule's own constant to 0**,
which makes it a no-op while everything else stays identical, run one arm,
restore, run the other. That is the practical reason every rule gets its own
constant.

#### The rules oracle: the only instrument that does not grade against a heuristic

It opens a search from a real observation, forces one option, plays to the end
and reports who won and by how many prizes. Four properties that are part of the
instrument, not caveats:

- **It reads hidden information and can therefore never be a play-time policy.**
  It is a grader for games you already hold both sides of.
- **It is an estimator, not a replay.** The search API is not seeded, so the same
  option graded twice disagrees with itself: at K=20 the worst pair of batches
  differed by **30 points**. Use K≥50, quote the **worst** floor, and read the
  **prize margin** before the win flag.
- **K is a resolution setting, not a cost setting.** One board had both options
  at 100/100 at K=100 — saying nothing — and separated only at K=500.
- **The opponent's rollout policy can flip the sign.** Driving *both* seats with
  our own agent out of one belief state gave +32 points to the wrong play on one
  board; a **mixed** policy — our seat on our agent, theirs merely legal — gave
  +6 the other way. Grade with the mixed policy, in independent batches, and
  accept the finding only if the ranges **do not touch**.

#### What "measured" means, per verdict

| Result | Meaning | Action |
| --- | --- | --- |
| Positive, clears its control floor | A real gain | Ship. |
| Negative, clears the floor | A real loss | Revert. Then check whether it is the *band*, not the sentence. |
| Neutral, **population real** | Below the instrument's resolution | May ship **marked NEUTRAL**, with all three of: census, oracle grade over the board's floor, and the winrate stated as measured — including when negative. |
| Neutral, **population ~zero** | The instrument is **blind**, not saturated | The revert policy does not apply. Decide on the board and say so. |
| Neutral, population real, no oracle support | Complexity nobody can validate | Revert. |

The distinction in the last three rows is the single most valuable thing on this
page. **"Neutral" and "invisible" produce the same winrate and demand opposite
decisions**, and only a firing census tells them apart. Instrument the branch
itself: one counter for *reached*, one for *produced a value the old code would
not have*. The second is the number that answers the question.

---

### Phase 8 — DECIDE and record

**Write down what you measured, including the reverts.** A rule that was tried,
measured neutral and removed is worth as much as one that shipped: it stops the
next person spending the same week. Roughly a third of this project's written
history is negative results, and they are consulted as often as the positive
ones.

Where each thing goes:

- **The commit message** carries the numbers, and says explicitly what is *not*
  being claimed.
- **A page per finding** carries the board, the arithmetic, the fix, the
  measurements and the controls — dated, and append-only. Later pages say when a
  finding was closed or reversed; earlier pages are not edited to match.
- **A memory entry** carries the one-line sentence, the identity of the board,
  the switch name, and the numbers — so the next session finds it by searching
  for the *symptom*, not the filename.

Two record-keeping rules that came from getting them wrong:

- **A user override is marked as an override.** When a change ships that the
  measurement said to revert, the merge title says *kept by decision, not by
  measurement*, the body carries the numbers against it, and the index line says
  so next to the link. The two readings — "this won" and "this went in because I
  asked" — lead to opposite decisions when someone later builds on top of it or
  hunts a regression.
- **A note that lies about *where* the code lives is worse than no note.** When
  the repo state changes, rewrite the affected lines in the same batch —
  including the ones you wrote an hour earlier.

---

## Part 3 — The rules that decide whether a number may be believed

> **A detector does not get to report a number until it has proved, in the same
> run, that it can catch a planted defect and stay quiet without one.**

This is not style. **Five detectors in this repository have reported their own
bugs as defects of the agent**, and in every case the output looked exactly like
a finding. One of them took the headline of an entire night.

So every instrument carries **two** self-tests, and both **abort** the run rather
than warn:

- **Sensitivity** — plant a defect, require detection. *This half is free the
  same day you fix a defect*: run the new detector against the commit before the
  fix and require the known finding, run it against HEAD and require silence.
- **Specificity** — a structural bound the detector cannot exceed, computed by a
  count **independent** of the one that produces the findings. Sensitivity alone
  is not enough: a detector that fires on everything passes it while
  over-reporting by three orders of magnitude.

Seven more rules from the same period:

1. **Compare against the finest reading the agent has, not the coarsest.** A
   detector that takes the agent's crude reading marks as defects exactly the
   places where the agent is being subtle. Five of twelve findings were the
   agent being right. The error scales with how good the agent is.
2. **Match prediction to outcome by identity, not by "the only thing that
   changed".** Attributing a prediction to whichever body lost HP made **89 %**
   of one detector's findings artefacts.
3. **Read the sign, not the rate.** The rate says where to look; the sign says
   whether to care. Optimistic drift (we predict more damage than lands) throws
   away turns; pessimistic drift only produces pleasant surprises. The deck that
   led the rate table for two nights wins 97 % of its matchups.
4. **A skewed concentration is a symptom of the detector.** Before reporting N
   findings, look at how they cluster and hand-sample 400.
5. **Count blind spots and print them.** A blind spot that is a number can be
   argued about; one that is a silence cannot.
6. **Run a deterministic instrument two or three times.** Two audits disagreed
   about how many menus a corpus holds — 90, then 98; the answer was 118 — because
   the capture keyed on object identity and the runtime recycles addresses.
   Every rate published before that had the wrong denominator.
7. **A control arm must *prove it ran the measurement***, not merely come back
   green. A worktree at the previous commit has none of the git-ignored data, so
   the tests skip themselves and the summary line looks like a pass. Assert
   `seen > 0` inside the test, or read the skip list.

And the sibling rule for behavioural claims: **the opponent has to be able to
execute the mechanism you are testing.** If the scripted bot never uses the
ability your rule counters, or cannot pilot the deck, every result comes back
neutral by construction. This has invalidated a whole batch of experiments here.

---

## Part 4 — Three worked examples

Compressed to the skeleton, to show the shape of a whole cycle.

### A — A shipped gain: a mechanic that was never modelled

- **Find.** A user reads a *won* game and notices ten turns swung into a body
  carrying no energy at all.
- **Describe.** Episode and steps; their body prevents all damage from our
  **Tera** Pokémon; ours is exactly one of our attackers, and the deck runs four
  of it. Six consecutive turns attacking for **0** with three loaded bodies on
  the bench; one forced promotion picked the blanked body over the one that
  finished the wall on the spot.
- **Diagnose.** Shape 1 + shape 3: the card was unknown, so the damage model
  priced the attack at 150 against a zero. It is a **third** question about the
  attacker — not *is it an ex*, not *does it have an ability* — so widening
  either existing immunity table would have blanked bodies that do hit it.
- **Design.** Its own term, in the canonical model **and in the three inline
  copies** of that arithmetic that do not route through it.
- **Pin.** Test with a mutant: empty the table in all four modules and the two
  old decisions must return.
- **Measure.** 7 golden flips, all that game; **0 of 3 580** frozen; gate
  n=1 000/arm **94.4 % vs 83.1 %, +11.3 points**, intervals disjoint; collateral
  clean because **87 of 87** real lists are the control group.
- **Also fixed the hider.** The immunity audit had reported *0 unmodelled*
  throughout — it had no claim for this shape *and* only ever read cards
  appearing in a corpus deck. That card is in **0 of 408** lists. The audit
  gained the claim and an all-cards sweep.

### B — Shipped marked NEUTRAL: the rule the winrate cannot see

- **Find/describe.** At our match point, the body one charge from ending the
  game lost the front seat by **300 points of an ornamental tie-break** bounded
  to 0..450.
- **Age the log first** — and the original defect was already fixed hours
  earlier by an unrelated commit. What remained broken was not the choice but
  **what it depended on**, a smaller rule.
- **Design.** A guaranteed band, bounded on both sides, exempt from the three
  discounts that argue about surviving a reply which arrives after our turn.
- **Measure.** Census 1 of 7 locally, 0 of 584 in self-play; 0 corpus flips; a
  600-game paired-seed gate with **0 divergent games**. Both arms are the same
  agent against the same bot, **so no winrate here can say anything**, and the
  write-up says that instead of quoting one.
- **Decide.** Shipped **marked NEUTRAL**, on the guarantee rather than a number.

### C — Measured and not adopted, shipped switched off

- **Find/describe.** With a full bench an evolution is the only thing the search
  Item can buy, and both evolution ladders hang off a guard that closes when a
  top-of-line copy is already on the board — so the Item scored as having no
  target at all.
- **Measure.** Census 0.09–0.16 turns per game — two to four times the
  populations this project has *closed below criterion*. Gate n=1 000 × 4 lists:
  **−0.70 points** against a control of **+0.25**. It does not clear its floor,
  but the sign does not dance the way the control's does. **Eleven pinned boards
  break.**
- **Decide.** **Switch shipped `False`**, behaviour identical, and the page
  records *why*: the suspect is not the sentence but the **band** — a live search
  Item is worth more than plays that take a prize. Re-opening the guard without
  first fixing the band loses again.

The point of C: **a candidate that is written, instrumented, measured and then
turned off is a completed unit of work.** It removes the same question from the
backlog as a merge does.

---

## Part 5 — Porting this to another deck

| Layer | Portable as-is | Needs rebuilding |
| --- | --- | --- |
| Harness, splitter, replayer, scenario builder | ✅ | — |
| Corpus machinery, gate skeleton, census skeleton, oracle | ✅ | — |
| Architecture lint rules | ✅ (they encode defect *shapes*) | — |
| The eight measurement disciplines in Part 3 | ✅ | — |
| The diagnosis taxonomy in Phase 4 | ✅ | — |
| Opponent corpus and meta weights | — | Entirely: re-harvest |
| Frozen corpus and fixtures | — | Re-record with the new list |
| Card ID tables (immunity, scaling, buffs) | The **audits** port | The **tables** do not |
| The strategy rules themselves | The *sentences* often do | The bands and constants do not |

**The order to rebuild in** is Part 1's bootstrap list. Expect the first two
weeks to produce mostly instrument fixes rather than agent fixes; that is the
normal shape, not a failure.

Four things worth carrying over verbatim, because they are about *any* deck:

- **A card's price when it is unmodelled is whatever your fallback band is.**
  Audit the fallback: it is where an opponent's new card walks in for free.
- **Every deck has "twin menus"** — two places that answer the same question
  about the same body (promotion vs retreat, fetch vs play, offensive vs jam).
  Half the findings here are one of a pair. Search for the twin on every fix.
- **Every deck has an engine and a clock.** Name them explicitly, and price every
  rule against them: *does this cost the engine a turn, or the clock a card?*
- **Weight the opponents.** Improving a matchup that is 2 % of the field moves a
  weighted mean by a fraction. That can still be the right work — but say which
  number you are reporting, and measure hard-matchup changes **on the hard
  matchups**.

---

## Part 6 — The cadence, and the method's own failure modes

**The rhythm that has produced the most findings:** play and record during the
day; read one or two losses by hand; take **one** board at a time through Phases
2–8; run the long, unattended instruments at night with a plan written in
advance that states its questions and its criteria **before** anything runs; read
the report in the morning and let it set the next day's backlog.

Three cadence rules earned the hard way:

- **One change of policy at a time, each with its own record, census, gate and a
  criterion written down before the number is looked at.** Of seven such units in
  one session, three closed without touching the agent at all — two because the
  instrument or the premise was wrong. That is exactly what the ordering exists
  to discover.
- **Re-run the matchup table before choosing what to work on.** Between batches
  the ranking reorders and a "next candidate" note goes stale. At n=200 the table
  screens; it does not rank. Re-measure the leading group at n≥800 before picking.
- **Do not mutate the tree while a background job is reading it.** The mutation
  stage rewrites files for the length of a test run; anything else reading the
  tree at that moment measures noise.

**The failure modes of the method itself**, all observed here:

| Failure | Looks like | Guard |
| --- | --- | --- |
| Instrument reports its own bug | A convincing, concentrated list of findings | Two-half self-test that aborts |
| A green control that never ran | `1 skipped` in a summary line | Assert the measurement happened |
| A corpus that heals itself | "no changes", forever | A committed corpus that cannot re-snapshot |
| A corpus that mislabels a decision | The defect is invisible, not absent | A wrong name in a diagnostic **hides** a decision |
| A gate whose arms share modules | Exactly 0.0 delta | Provenance, printed and checked |
| Asking a saturated instrument for a verdict | Endless neutrals | Census first, oracle second |
| A rule written from the story of a game | The wrong flag arbitrates | Resolve the IDs, read the menu |
| A rule written from a stale record | A second fix for a fixed bug | Age the log, bisect over the record |
| A test hanging off transient data | Five tests silently stop measuring | Derive the board from a committed fixture |

---

## The one-page version

1. **Play, record, and read the games you lost.** That is the only place findings
   come from.
2. **Write the board down** — identity, menu, arithmetic, the sentence, the
   controls — before touching code.
3. **Reproduce it today**, one process per record, our frames only, and check the
   defect is not already fixed.
4. **Diagnose against the taxonomy**, look for the twin hole, and ask what *hid*
   it.
5. **Pick a fix shape deliberately**, phrase it about a property and not a card,
   and give it its own constant and switch.
6. **Pin it with a test that fails first and dies to its own mutant**, and a
   control in the same file.
7. **Measure cheapest first**: population, flips, cost, grade. A control arm in
   the same run, always.
8. **Decide, and write down the number — including the reverts and the
   overrides.**

---

Next: [Improving the agent](improving-the-agent.md) · [The instruments](instruments.md) · [Debugging a decision](debugging.md) · [Testing](testing.md)
