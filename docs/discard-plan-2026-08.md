# Discarding well — what Xerosic asks, and what we answer

[← Documentation index](README.md)

**Status: Wave 0 and Wave 1 are done; Waves 2–5 are still plan.** This is the
analysis of the forced-discard decision, the criterion that should replace the
current one, the waves that get us there, and the testing that decides whether
each wave stays.

What running Wave 0/1 already settled — and the two things it cost that the
plan did not predict — is in [§10](#10-what-waves-0-and-1-actually-found).

---

## 0. The one-paragraph version

Xerosic's Machinations is the opponent's hand-cutter: it takes our hand down to
three cards and hands *us* the choice of which ones survive. The agent answers
that choice with a **per-card price list** — twenty-odd `elif card.id ==` branches
that price each card in isolation against static proxies (copies in hand, copies
in play, size of the discard pile). It never asks the question the choice is
actually about: *given this board, these prizes and this opponent, which three
cards let us attack — and win — on our next turn?* This plan replaces the price
list with a **keep-set planner** that reads the board, ranks what the next turn
needs in tiers, and leaves the existing price list as the tie-breaker inside each
tier.

---

## 1. What Xerosic's Machinations actually is

Card id `1197`, a Supporter, **2 copies in our deck**. Its effect: *the opponent
discards cards from their hand until they have 3 left.* The player who plays it
does not choose the cards — the victim does.

That makes it two completely different problems, and the code already treats
them as two:

### 1a. When *we* play it — offence (solved, measured, not in scope)

Lives in [`ptcg/decision/disruption.py`](../ptcg/decision/disruption.py) as
`_score_xerosic_play` over the `_RULES_XEROSIC_PLAY` rules engine. It exists for
one matchup: **Alakazam's Powerful Hand does 20 damage per card in their hand**,
so cutting an eight-card hand to three cuts 160 damage off the incoming attack.
The rule ladder is already measured and pinned by six tests
(`test_first_turn_lillie_over_xerosic.py`, `test_xerosic_before_the_unfair_stamp.py`,
`test_meowth_over_the_last_resort_xerosic.py`,
`test_the_stamp_does_not_follow_our_own_xerosic.py`,
`test_the_stamp_does_not_bury_the_last_xerosic.py`,
`test_ub_does_not_burn_the_freshly_dug_xerosic.py`).

**This half is out of scope.** It works and it is measured.

### 1b. When *they* play it — defence (the subject of this plan)

We receive a `SelectContext.DISCARD` menu whose options are *our whole hand*, with
`minCount == maxCount == len(hand) - 3`. We return the indices to throw away.
The agent scores every option and discards the highest-scoring ones — in this
context **a high score means "discard me first"**, and a negative score means
"keep me above everything".

### 1c. The third caller sharing the same code

`SelectContext.DISCARD` is *also* the menu the **Ultra Ball cost** produces
(discard 2 cards to search a Pokémon), on **our own turn**. In the frozen corpus,
of 118 discard decisions, **87 are the two-card Ultra Ball cost** and ~28 are the
larger forced cuts.

This matters more than it looks. Section 3 shows the two callers have **opposite
time horizons** and the code cannot currently tell them apart.

---

## 2. Where the decision lives today

```
agent(obs)
  └─ ptcg/turn/ctx.py            builds the turn context (prizes, plan, board reads)
  └─ ptcg/turn/scoring.py        dispatches by option type
       └─ ptcg/turn/options/card.py     ← the `elif context == SelectContext.DISCARD` block
  └─ ptcg/turn/finalize.py       sorts by (tier, score) descending, returns the top `maxCount`
```

The DISCARD block is roughly 590 lines and has four layers:

| Layer | What it is |
| --- | --- |
| **A. Per-card branches** | ~20 `elif card.id == …` blocks, one per card in `deck.csv`, each returning a fixed score from a small decision tree. |
| **B. The spare-copy cap** | `_evo_copies_usable` — an evolution line protects the *seats* it can wear, not every copy. Surplus copies fall to `DISCARD_EVO_SPARE_COPY` (55). |
| **C. The seatless-body cap** | *(added last week)* a Pokémon with no free bench seat **and** a copy already in play falls to `DISCARD_BODY_WITHOUT_SEAT` (46). |
| **D. The Supporter re-rank** | orders the Supporters in hand by `_supp_values`, the same live valuation that decides which Supporter gets *played*. Bounded to the Supporter band. |
| **E. The Comfey override** | a hard-coded score table (80…850) that **replaces** everything above when `op_is_comfey_deck`. |

Three order-dependent latches (`_lillie_protected_once`, `_evo_spare_seen`,
`_counter_stadium_kept_once`) carry state across options in a single menu, so the
result depends on the order the simulator emits the hand in.

Layers B, C and D are already the right shape — they read the board, they name no
card, and they act as **bands over** the price list rather than replacing it.
Layer A is the price list, and layer E is what we must not build more of.

---

## 3. Audit — what the current rule actually reads

Seven findings. Each is verifiable today; the ones marked **measured** were
confirmed by running the agent over the step-99 fixture.

### F1 · It prices cards, it does not choose a hand — *the structural one*

Every branch answers "how expensive is this card in the abstract?" and no branch
answers "what does this card do **next to the other two we are keeping**?" A Basic
Grass Energy is worth a great deal when we also keep the Ogerpon ex that spends
it and almost nothing on its own; a Night Stretcher is worth a great deal when
the attacker it recovers is in the discard and nothing when it is not. The scorer
cannot express either sentence.

This is why every fix so far has been a new band: a per-card price list has no
place to put a *combination*.

### F2 · **Measured** — the turn-scoped flags belong to the *opponent's* turn

At forced-discard time the observation is a snapshot of **their** turn. Running
the step-99 fixture:

```
state.supporterPlayed = True      state.energyAttached = True      turn = 6
```

Both flags describe what *they* did. But the DISCARD block reads them as if they
described us:

- `_protect_last_supporter = (not state.supporterPlayed and …)` — Xerosic **is** a
  Supporter, so `supporterPlayed` is *always* True by the time we are asked.
  **This guard is dead code on every forced discard**, and it is exactly the
  guard that protects our last playable Supporter.
- `state.energyAttached` gates the Night Stretcher branch (see F3).
- `state.turn <= 5` gates the early-game protections for Lillie's, Boss's and Dawn.

On the Ultra Ball path the same reads are correct. One block, two horizons.

### F3 · Suspected sign inversion in the Night Stretcher branch

The branch reads: if the only thing recoverable from the discard is basic Energy
we cannot use (`state.energyAttached`), then `score = SCORE_VETO` (−1). In the
*play* context a veto means "do not play this". In the **DISCARD** context a
negative score means **"keep this above everything except the Unfair Stamp"** —
the code hands its strongest protection to the card it just judged useless.

Combined with F2 the misfire compounds: on a forced discard `energyAttached` is
*their* attachment, so the branch fires on boards where the Stretcher would be
perfectly live for us next turn — and it fires with the wrong sign either way.

**No test covers this branch.** It is the first thing Wave 0 must probe: if the
reading is right, it is a one-line fix worth its own commit and its own gate.

### F4 · The prize count is invisible

`my_prize` and `op_prize` are in the context and correct at discard time (5/5 in
the fixture). **Exactly one branch reads them** — Boss's Orders, via
`op_prize <= 3`. Nothing else does.

So the hand we keep at 6-6 and the hand we keep at **match point** are chosen by
the same rules. The project already has the doctrine for this
(`plan_of` → `MODE_WIN_NOW` / `DENY` / `RACE` / `DEVELOP`, and the whole
match-point promotion family) and the discard does not consult it.

### F5 · The opponent is read as four booleans

`op_is_alakazam_deck`, `op_is_comfey_deck`, `op_has_ex_immune_active/bench`,
`op_is_crustle_deck`. That is *archetype* reading, not *board* reading. Nothing
asks: what body will be in front of us next turn, how much damage does it take to
knock it out, can they knock **us** out on their reply, is our ex mute against
what they have (`_our_effective_damage`).

The step-99 loss is precisely this gap: under their Neutralization Zone every ex
we owned did 0 damage, and the only card in the deck that lifts it was priced by
`hand_counts[Forest_of_Vitality] <= 1`.

### F6 · `plan_of` is available and unused

**Measured** at step 99: `TurnPlan(my_prize=5, op_prize=5, win_route='',
prizes_today=0, op_prizes_next=0, mode='DEVELOP')`. The plan builds fine in this
context. Two caveats before we lean on it:

- it is computed as though it were **our** turn, so `prizes_today` and
  `op_prizes_next` are shifted by one turn on a forced discard;
- `win_route` is about *this* turn's resources, and a forced discard is about
  *next* turn's.

So the discard needs a **next-turn projection**, not `plan_of` verbatim. `plan_of`
is the model to copy, not the value to read.

### F7 · Layer E is a per-matchup override, and the project has already ruled against those

The Comfey block replaces the whole computed score with a fixed table. It is the
shape that
[`bandas-por-matchup-rompen-el-invariante`](../docs/strategy.md) warns about, it
bypasses layers B/C/D entirely, and it is 850-vs-80 — a scale that has nothing to
do with the 0-100 scale everything else uses. It should end up as a *reason* fed
into the general planner, not a table.

---

## 4. The criterion — what "intelligent" means for this decision

The decision is not "which cards are worst". It is: **choose the keep-set K of
size `len(hand) − maxCount` that maximises our chance of winning**, with the
horizon set by who forced the discard.

### 4.1 Two horizons, named once

| Caller | Horizon | Question |
| --- | --- | --- |
| **FORCED** (their Xerosic, `select.effect.playerIndex != us`) | our **next** turn | what do we need to attack and take prizes next turn? |
| **COST** (our Ultra Ball, effect is ours, our turn) | the **rest of this** turn, then next | what does the turn still have to spend? |

Everything below is written for FORCED; the COST path keeps today's behaviour in
Wave 1 and inherits the planner only if the measurement says it should.

### 4.2 The tiers — strict lexicographic order

A card is kept for the **best reason it satisfies**. Reasons, most urgent first:

| Tier | Name | Sentence | Fires when |
| --- | --- | --- | --- |
| **T0** | `LETHAL` | *this card is part of a set that wins next turn* | a next-turn route takes the last prize(s) — `op_prize` reachable with what the keep-set enables |
| **T1** | `DENY` | *they close it on their reply and this card stops them* | their next attack takes their last prize(s): the card that heals, retreats, walls or takes the prize first |
| **T2** | `UNBLOCK` | *we cannot attack at all, and this card is the way out* | `not can_attack` next turn: counter-stadium under a hostile stadium, energy, a body that can attack, a recovery of the attacker, retreat fuel out of a wall |
| **T3** | `PRIZE` | *this card takes a prize next turn* | a KO is reachable but not lethal |
| **T4** | `DEVELOP` | *this card improves the board* | nothing decisive: the refill, the seat-filling body, the line piece with a seat |
| **T5** | `FODDER` | *nothing above* | ordered by today's price list |

**Two invariants that make this safe:**

1. **The planner may only demote a card into a band, never above the existing
   vetoes.** `SCORE_NEVER` (Unfair Stamp) and any negative score computed by the
   branches stay untouched. Same discipline as layer D.
2. **Inside a tier, the current price list decides.** The planner never invents
   an ordering it does not have evidence for; it moves cards *between* bands and
   leaves the branches to break ties. This keeps every measured rule alive.

### 4.3 What a tier actually needs to know

The planner needs answers the codebase already computes. Nothing here is a new
damage model — reusing the existing ones is the point
(`el-gusteo-ganador-y-su-objetivo-comparten-el-modelo-de-dano`):

| Question | Existing helper |
| --- | --- |
| Does our attacker do real damage to that body? | `_our_effective_damage`, `_attacker_base_damage` |
| Can a bench body knock it out? | `_bench_attacker_can_ko` |
| Can we pay the attack cost next turn? | `_can_attack_eff`, `_reachable_grass_for`, `_grass_mult` |
| Can we get the energy at all? | `_grass_attach_route_open`, `_grass_attach_slots_for` |
| Is their stadium switching us off? | `_counter_stadium_urgent` |
| Does that body have a seat? | `_ub_target_has_no_seat`, `_line_base_benchable`, `_evo_copies_usable` |
| How much do they hit us for? | `_op_active_attack_damage_to` |
| Which Supporter is live on this board? | `_supp_values` |
| Whose prize clock is it? | `prize_count`, `prize_count_op`, `TurnPlan` |

### 4.4 The requirement model

The planner does **not** enumerate hands (combinatorially wrong and slow). It
produces a **ranked requirement list**, then greedily satisfies it against the
keep budget:

```
Requirement = (tier, role, predicate_over_card, count_needed)
```

Example, on the step-99 board:

```
T2 UNBLOCK  role=COUNTER_STADIUM   card is Forest of Vitality     need 1
T2 UNBLOCK  role=ATTACKER_ENERGY   card is Basic Grass            need 0  (8 on field)
T4 DEVELOP  role=RECOVERY          card recovers from discard     need 1
T4 DEVELOP  role=REFILL            card is the live Supporter     need 1
```

Budget 3 → keep {Forest ×1, Night Stretcher, Lana's Aid}, discard {Meganium,
spare Ogerpon ex, spare Forest} — which is exactly what the two hand-written
bands added last week now produce. **That is the acceptance criterion for Wave 2:
reproduce the hand-written answer from the general rule, then delete the special
case.**

---

## 5. The design

### 5.1 New module: `ptcg/decision/discard.py`

Pure, no state, mirrors `ptcg/decision/ultra_ball.py` and
`ptcg/turn/game_plan.py`:

```python
@dataclass(frozen=True)
class DiscardPlan:
    forced: bool          # their effect vs our own cost
    keep_budget: int      # len(hand) - maxCount
    horizon: str          # 'NEXT_TURN' | 'THIS_TURN'
    tier_of: dict         # card serial -> tier constant
    reasons: dict         # card serial -> role, for the debug trace

def build_discard_plan(ctx, select) -> DiscardPlan: ...
def plan_of_discard(ctx) -> DiscardPlan:   # memoised per select, like plan_of
```

Consumed from the DISCARD block as a **ceiling wrapper at the end of the block**
(`techo-en-envoltorio-no-al-final-de-la-funcion`), after layers B/C/D:

```python
_dp = plan_of_discard(ctx)
_tier = _dp.tier_of.get(card.serial)
if _tier is not None and score > SCORE_VETO:
    score = _band_for(_tier, score)     # min() to keep, max() to drop
```

`_band_for` maps a tier to a narrow corridor inside the existing 0–100 scale and
**clamps** rather than assigns, so a card the branches already priced as fodder
stays fodder and a card already vetoed stays vetoed.

### 5.2 Band constants

Go in [`ptcg/cards/ids.py`](../ptcg/cards/ids.py) next to the existing
`DISCARD_*` family, documented the way those are — what is above, what is below,
and why:

```
DISCARD_TIER_LETHAL      ~  1     never discarded short of a veto
DISCARD_TIER_DENY        ~  4
DISCARD_TIER_UNBLOCK     ~  8
DISCARD_TIER_PRIZE       ~ 18
DISCARD_TIER_DEVELOP     ~ 42     above the live-utility band, below the seatless body (46)
                                  (fodder keeps whatever the price list gave it)
```

Exact values get fixed in Wave 2 against the corpus, not now.

### 5.3 What the design deliberately does **not** do

- **No hand enumeration.** Ranked requirements + greedy fill. The keep budget is
  1–10; the requirement list is short; the cost stays O(hand × requirements).
- **No second damage model.** Every "can we KO" answer comes from the existing
  helpers or it does not get asked.
- **No new per-matchup table.** F7 is the anti-pattern; the Comfey block gets
  *retired into* the planner in Wave 5, or stays exactly as it is.
- **No touching the offensive Xerosic ladder** (§1a).

---

## 6. Implementation waves

Each wave is one commit, gated independently, revertible on its own. **A wave
that measures neutral gets reverted** — the project's written rule.

### Wave 0 — Instrumentation and ground truth *(no behaviour change)*

1. Add a `DEBUG_DECISIONS` trace for the DISCARD menu: per card, the branch that
   fired, the final score, and the layers that clamped it.
2. Add `utils/discard_census.py`: replay every record and the corpus, and report
   the distribution of discard decisions — forced vs cost, hand size, keep
   budget, which cards get kept, prizes at the time.
3. Add `Scenario.forced_discard(keep=3, by_opponent=True)` and
   `Scenario.cost_discard(n=2)` to [`tests/state_builder.py`](../tests/state_builder.py).
   **This does not exist today** and every synthetic test below depends on it.
   It must build the observation on the *opponent's* turn (their `effect`,
   `supporterPlayed=True`) for the forced case.
4. Probe **F3** (the Night Stretcher sign) and **F2** (the dead
   `_protect_last_supporter`) and write the finding down either way.

**Gate:** `pytest -q` green · golden corpus **`no changes`** · architecture lint
green. A wave-0 flip means something leaked.

### Wave 1 — Separate the two horizons

Introduce `forced` / `horizon` in the context and route every turn-scoped read in
the DISCARD block through it: on FORCED, `supporterPlayed`, `energyAttached` and
`turn` are read as *next turn's* values (slot free, attachment free, turn + 1).
Fix F3 if Wave 0 confirmed it.

This is the highest-value/lowest-risk wave: it revives a protection that has been
dead code and removes a sign error, with no new strategy.

**Gate:** suite green · golden corpus flips **reviewed one by one and written up**
· `selfplay.py --games 1000 --base HEAD~1` non-negative · matchup differential vs
Alakazam (their Xerosic is what fires this path).

### Wave 2 — T0/T1: lethal and deny

The planner, with only the two top tiers wired: keep what wins next turn, keep
what stops them closing. Acceptance: reproduce the step-99 answer from the
general rule.

**Gate:** as Wave 1, plus the new scenario matrix (§7.2) and the monotonicity
assertions (§7.3).

### Wave 3 — T2: unblock

The "we cannot attack" tier. Subsumes the hand-written counter-stadium latch —
**and only then is the latch deleted**, with the existing test still green as the
proof of equivalence.

### Wave 4 — T3/T4: prize and develop

The lower tiers. Highest chance of measuring neutral; likeliest to be reverted.
Ship it last so nothing depends on it.

### Wave 5 — Retire the special cases

Fold Layer E (Comfey) and, if the measurements support it, the seatless-body and
spare-copy bands into the planner as *roles*. Pure simplification, gated on the
corpus showing **zero** flips.

---

## 7. The testing plan

Five layers. Layers 1–3 are new work; 4–5 already exist and just need running.

### 7.1 Layer 1 — Fixtures from real records *(regression)*

The two we have (`test_the_forced_discard_keeps_the_counter_stadium.py`,
`test_the_forced_discard_keeps_the_energy_recovery.py`) stay green through every
wave. Any wave that needs them changed must say why in the commit.

New fixtures come from `utils/autopsy.py` over lost games, filtered to steps with
`select.context == 8` and `effect.id == 1197`.

### 7.2 Layer 2 — The synthetic scenario matrix *(the core of this plan)*

Built on `Scenario.forced_discard()` from Wave 0. The matrix crosses the four
axes the user named:

| Axis | Values |
| --- | --- |
| **Our board** | can attack now · needs 1 energy · needs a body · active is mute (ex vs no-rule-box) · bench 2/5 · bench 5/5 |
| **Their board** | healthy 1-prize wall · wounded ex in range · ex-immune wall · hostile stadium (Neutralization Zone / Watchtower) · empty bench |
| **Our prizes** | 6 · 4 · 2 · **1 (match point)** |
| **Their prizes** | 6 · 4 · 2 · **1 (they close on the reply)** |
| **Hand** | 8 fixed compositions: energy-rich, energy-dry, two Forests, duplicate ex, recovery-only, supporter-heavy, line-in-pieces, all-fodder |

Not the full cartesian product — a **fractional design**: every axis pair covered
at least once, plus the ~20 cells the tiers are *about* (each tier's firing and
non-firing case).

**Each cell asserts the tier, not the exact card list.** "The keep-set contains at
least one card of role X" survives a band retune; "the keep-set is exactly
[a, b, c]" does not, and would make the suite an obstacle by Wave 4.

### 7.3 Layer 3 — Sweeps and invariants

Using [`tests/decision_grid.py`](../tests/decision_grid.py) (`sweep`,
`boundaries`, `monotone_along`) — built for exactly this:

- **Monotonicity.** As `op_prize` drops 4 → 1, the card that closes the game must
  never become *more* discardable. As their damage rises, the card that survives
  it must never become more discardable. A rule that switches on, off and on
  again along an axis is two rules colliding, not a strategy.
- **Boundaries.** `boundaries()` prints where the decision actually changes its
  mind. Every printed threshold must match a documented constant — an
  undocumented threshold is an accident.
- **Invariants** (`tests/test_invariants.py`, hypothesis):
  - the returned index list has exactly `maxCount` entries and no duplicates;
  - no card with a negative score is ever in it;
  - the Unfair Stamp is never in it;
  - the planner never keeps more cards than the budget;
  - a card in tier T never outranks a card in tier T−1 *after* clamping;
  - **idempotence under menu order**: shuffling the hand's emission order must not
    change the *multiset of card ids* discarded. This directly targets the latch
    fragility of §2, and is the assertion the current code would most likely fail.

### 7.4 Layer 4 — The golden corpus *(the arbiter)*

118 frozen discard decisions across 50 records. `python tests/golden_corpus.py`
after every wave. The review is per flip: *was that flip intended?* A wave that
flips a decision nobody can explain does not ship.

Re-freezing the corpus is **a separate commit from the logic**, always
(`corpus-dorado-resnapshot-silencioso`).

### 7.5 Layer 5 — Games

- `python utils/selfplay.py --games 1000 --base HEAD~1` — sample ≥1000, because
  at 200 the per-matchup noise is ±6.5 points.
- `python utils/selfplay.py --games 400 --opponent <alakazam list> --base HEAD~1`
  — the **differential** against the archetype that actually plays Xerosic. The
  bot's absolute level is not the signal; the delta is.
- `python utils/matchup_matrix.py --games 400 --weights` — at whose expense.
- Once the winrate saturates, read the **prize differential** — it is the metric
  with resolution left.

### 7.6 Validating the tests themselves

A test that cannot fail proves nothing. Before each wave lands:

- inject the bug the new test is meant to catch and watch it go red
  (`validar-el-arnes-son-dos-mitades`);
- run `utils/gate_mutation.py` over the DISCARD block — it measures whether the
  **suite** catches mutations, which is the specificity half.

---

## 8. Safety rules and rollback

1. **Bands, never overrides.** The planner clamps; it never assigns. It cannot
   resurrect a vetoed card and it cannot rescue fodder.
2. **The general rule goes before its special case**
   (`la-regla-general-va-antes-que-su-caso-especial`) — but the special case is
   only deleted once the general one reproduces its answer with its test green.
3. **One wave, one commit, one gate.** Never bundle a corpus re-freeze with a
   logic change.
4. **Neutral means revert.** Written project rule; Wave 4 is the likeliest
   candidate.
5. **No mutable-by-value imports** (`from X import` binds a copy) and no state in
   the pure subpackages — `utils/lint_architecture.py` enforces both, and the
   new module is pure by construction.
6. **Do not edit files a background job is swapping**
   (`no-editar-lo-que-un-job-en-segundo-plano-intercambia`). Check for running
   nightly jobs before starting a wave.
7. **Rollback is `git revert` of one commit.** No wave depends on a later one;
   the tiers are additive and the wrapper is a no-op when `tier_of` is empty.

---

## 9. Open questions for the first session

1. **F3** — is the Night Stretcher `SCORE_VETO` a sign inversion or intentional?
   Wave 0 answers it. It may be a one-line, high-value fix that ships before
   anything else here.
2. Should the **COST** (Ultra Ball) path inherit the planner at all, or keep the
   price list? 87 of 118 corpus decisions are on that path, so it is where the
   flips — and the risk — live. Recommendation: **leave it alone until Wave 4**,
   then measure it separately.
3. How far ahead is the FORCED horizon worth projecting — our next turn only, or
   their reply too? T1 needs the reply. `TurnPlan` already models one reply;
   reuse it rather than extend it.

---

## 10. What Waves 0 and 1 actually found

Wave 0 (probe) and Wave 1 (separate the two horizons) were run on 10 August
2026. Three of the findings above were confirmed by execution rather than by
reading, and two things came out that this plan did not predict.

### 10.1 Confirmed by measurement

**F2 was real and worse than described.** On the step-99 observation the flags
read `supporterPlayed=True`, `energyAttached=True`, and Xerosic's Machinations
*is* a Supporter — so `supporterPlayed` is True on **every** forced discard it
can ever produce. `_protect_last_supporter`, gated on `not
state.supporterPlayed`, was not merely misfiring: it was unreachable code on
that whole path.

**F3 was a sign inversion.** With the Pokémon stripped out of the discard pile,
the Night Stretcher scored **−1** — above the last playable Supporter (5) and
above the critical counter-stadium (2). The branch was deleted rather than
re-signed: its reading survives neither caller (on a forced discard the spent
attachment is the opponent's; on an Ultra Ball cost the pile it measures is
about to be fed by the cost itself).

### 10.2 What the plan did not predict

**Reviving dead code exposes what was hiding behind it.** The frozen corpus
returned three flips, and two were regressions introduced by the fix:

* `Meowth ex` was priced fodder by `bench_count >= 5 and supporterPlayed`. The
  two halves are different claims, and only the bench one — the SEAT — makes the
  copy dead. The `supporterPlayed` half had been doing the seat check by
  accident;
* the `Lillie's` and `Dawn` ladders test "the last Supporter I can still play"
  (5, 12) *before* "the last refill" (2, 3), and score it higher — so a card
  satisfying both came out **less** protected for having one more reason to be
  kept. Invisible while F2 kept the first gate dead.

Both are pre-existing defects. Neither would have been found by reading.

**One flip was left standing, and it names the next defect.** In
`registro_021_crustle_wall_18` turn 5 a second Meowth ex (2) now outranks a live
Night Stretcher (30) for keeping. Two copies of the same Basic in hand both
receive the protection of the plan — the same duplicate-pricing shape
`_evo_spare_seen` and `_lillie_protected_once` already fix elsewhere, asked of
the door a Basic walks through. That belongs to Wave 2.

### 10.3 The gate could not arbitrate, and that is the real result

Self-play, 1000 games, candidate against the same tree without the change:

    Score:          500 - 500
    Winrate:        50.0%  [95% CI 46.9% - 53.1%]
    Prizes/game:    4.35 - 4.39   (differential -0.04)

Dead neutral. But **the gate is not powered to resolve a change this small**:
across the 3 580 frozen decisions this one alters exactly **one**. At 0.03% of
decisions, no affordable number of games separates it from noise — the ±3.1
point interval is two orders of magnitude wider than the effect.

So "neutral" here means *below the instrument's resolution*, not *no effect*,
and the keep-or-revert call cannot be made on the winrate. It has to be made on
correctness: a card judged useless was receiving the strongest keep-protection
in the block, a protection gate was unreachable, and a ladder was handing out
the weaker of two applicable protections.

**The lesson for Waves 2–5:** stop expecting the winrate gate to arbitrate
single-rule changes in the discard menu. The instruments with resolution here
are the frozen corpus (which found both regressions above) and the scenario
matrix of §7.2. Reach for self-play when a wave changes a decision class
*broadly* — which is what the tier work of Wave 2 will do, and this wave did
not.

### 10.4 A tool fixed on the way

The measurement above was only possible because `--base` was fixed first. It
used to export a lone `main.py`, whose `ptcg` imports resolved to the working
tree — so both arms of every comparison shared 26 571 of the agent's 37 899
lines, and any change under `ptcg/` measured exactly zero by construction. See
`tests/test_the_gate_measures_the_package_too.py`.
