# The night of 8–9 August — one execution plan

This merges two documents into a single runnable sequence:

- **[testing-plan-2026-08.md](testing-plan-2026-08.md)** — the strategy review
  (what the estate measures, three structural weaknesses, phases T0–T4).
- **The failure-class analysis of 2026-08-08** — the twenty fixes of 7–8 August
  grouped into seven recurring causes (section 2 below).

The first says *what kind of testing is missing*. The second says *which
defects this codebase actually produces*. Where they agree, the task is
prioritised. Where the second names a class the first does not, a guard is
added (the `G-*` tasks).

---

## 0. The two facts that shape everything

### Compute is not the bottleneck

Measured on this machine, tonight:

| | |
|---|---|
| Self-play | **0.10 s per complete game** (40 games in 4.03 s, single-threaded) |
| Cores / RAM | 12 / 36 GB |
| One core, one hour | ~36 000 games |
| Mutation | ~3.4 s per killed mutant, ~11 s per survivor (full suite, no `xdist`) |
| Suite | 1784 passed, 13 skipped, 11.0 s |

A thousand-game gate costs **100 seconds**, not a night. So the night is not
bounded by how many games can be played. It is bounded by **how much detector
code gets written**, and by what is safe to do unattended.

That reframes the whole plan: the job of the night is to **convert CPU into
pinned findings**, and the compute to do it is essentially free.

### The safety rule: nothing behavioural ships while you sleep

Every task here is classified **ADDITIVE** or **BEHAVIOURAL**.

- **ADDITIVE** — adds tests, tools, monitors, censuses, CI config. Cannot change
  a single decision the agent makes. Worst case it is deleted in the morning.
- **BEHAVIOURAL** — changes `main.py` or `ptcg/`, i.e. changes what the agent
  plays. The gate that validates one of these is self-play plus corpus flips
  plus *your judgement about the game*, and the third of those is asleep.

**Only ADDITIVE tasks run unattended.** This is not caution for its own sake:
it is the same doctrine the project already applies to its own rules — measure
before shipping, and a number nobody read is not a measurement.

The consequence is a clean split:

> **NIGHT** builds the detectors and runs them.
> **MORNING** you read what they found and decide the fixes.

---

## 1. What is in and what is out

| Task | From | Class | Tonight | Why |
|---|---|---|---|---|
| T0.1 fix collection | plan | ADDITIVE | ✅ **done** `d14179e` | |
| T0.3 mutation gate | plan ⭐ | ADDITIVE | **yes — block 1** | measures the suite, not the agent |
| T2.2 differential oracle | plan ⭐ | ADDITIVE | **yes — block 2** | the only detector for failure class B |
| T2.1 invariant monitor | plan ⭐ | ADDITIVE | **yes — block 3** | the only detector for failure class A |
| G-A stale-flag invariant | classes | ADDITIVE | **yes — inside T2.1** | class A is 5 of the last ~20 fixes |
| T3.1 `opponent_bot` suite | plan | ADDITIVE | **yes — block 5** | protects every A/B number we will ever produce |
| T2.4 observation fuzzing | plan | ADDITIVE | **yes — block 5** | an exception costs a whole game |
| G-C score↔fetch seam test | classes | ADDITIVE | **yes — block 5** | class C, doctrine exists with no executable guard |
| G-E unmodelled-card census | classes | ADDITIVE | **yes — block 5** | class E, omission projects 0 silently |
| T0.2 coverage floors | plan | ADDITIVE | **yes — block 6** | `evolve.py` reached 6 % unnoticed |
| T2.3 hypothesis properties | plan | ADDITIVE | **yes — block 6** | 7 candidates already named in the plan |
| T3.4 grow golden corpus | plan | ADDITIVE | **yes — block 6** | 11 records is thin |
| T1.1 / T1.2 assert the reason | plan ⭐ | ADDITIVE\* | **no** | \*additive in code, but choosing *which rule to name* is game judgement |
| T3.2 second opponent policy | plan | BEHAVIOURAL | **no** | designing a play policy |
| T3.3 SPRT | plan | ADDITIVE | **no** | solves a compute problem we measured we do not have |
| Cornerstone in both halves | classes | **BEHAVIOURAL** | **no** | morning — changes charging |
| Ultra Ball link vs `+150` | classes | **BEHAVIOURAL** | **no** | morning — changes fetch |
| Bellibolt `Thunderous Bolt` | classes | **BEHAVIOURAL** | **no** | morning — changes the damage projector |

T1.1 deserves a note, because it is the plan's own ⭐ and it is being deferred.
`ptcg/engine/rules.py::_resolve_with_trace` **already returns** the named trace;
T1.1 is wiring, not building. But an `assert_reason(choice, "prize_dominance")`
is only worth writing if the name asserted is the rule that *should* have
decided — and that is exactly the judgement that is asleep. Block 6 therefore
does the mechanical half: **expose the trace through a test helper and print
it**, so that in the morning writing the assertions is typing, not archaeology.

---

## 2. The seven failure classes, and which task catches each

From the twenty fixes of 7–8 August 2026:

| Class | Count | Example | Caught tonight by |
|---|---:|---|---|
| **A** · a turn flag that outlives its premise | **5** | `_ub_engine_pivot_turn` armed with bench 4, consumed with bench full | **T2.1 + G-A** |
| **B** · the same quantity computed in N places | 4 | "believed a 30 the engine resolves at 210" (`682ef74`) | **T2.2** |
| **C** · a rule that does one of its two halves | 3 | the charge veto without its destination (`fe94b77`) | **G-C** |
| **D** · a dead second copy of the rules | 1 | `feb1746` deleted 969 lines | lint R5 (exists) + T0.2 |
| **E** · omission projects 0, not an error | 2 | their bench buff; Bellibolt | **G-E** |
| **F** · order and sequencing | 3 | 0.56 % of decisions decided by menu order | permutation probe (exists) |
| **G** · detect ≠ execute | 1 | `d37e459` | T2.1 (an armed plan that never fires is a violation) |

Class A is the largest and the plan does not name it. It has one shape every
time: a boolean on `AGENT_STATE` that is only cleared **between turns**, while
the premise that armed it can die **within** the turn. G-A makes that an
executable invariant instead of a discipline.

---

## 3. Block 0 — what I need confirmed before you sleep

**These are the questions the plan asks at the start**, and the answers given
on 2026-08-08 at 21:20. They are the standing orders for the night.

| # | Question | **Answer** |
|---|---|---|
| 1 | **Write scope** | **ADDITIVE ONLY.** `tests/`, `utils/`, `docs/`, CI config. **Zero lines of `main.py` or `ptcg/`.** The three behavioural fixes wait for the morning. |
| 2 | **Git** | **A new branch**, `night/2026-08-09`. Nothing lands on `main` tonight. |
| 3 | **Horizon** | **~8 h**, read on waking. All seven blocks plus the long soak. |
| 4 | **On failure** | **Skip and continue.** Record the failure with its trace, mark the block as partial, move to the next. The dawn report says exactly what was skipped and why. |

Answer 1 is the load-bearing one, and it makes the success criterion in § 5
literal: **the diff of this night must not touch `main.py` or `ptcg/`.** If it
does, something went wrong regardless of how good the change looks.

### Assumptions I will run on unless told otherwise

- **No new dependencies.** `pytest-cov` 7.1.0 and `hypothesis` 6.161.1 are
  present; `pytest-xdist` is not, and the measured 3.4 s per mutant does not
  need it.
- **Nothing is pushed.** Local commits only.
- **`log/` for everything long**, per house rule — `log/night_2026-08-09/`,
  one numbered file per block, violations under `log/night_2026-08-09/violations/`.
- **Every block starts and ends with the four gates** (suite, lint, corpus,
  submission smoke) so a break is attributed to the block that caused it.
- **The baseline is recorded first** (block 0) and every number in the morning
  report is a delta against it.
- **A run that finds nothing is reported as finding nothing.** No block gets
  quietly dropped.

---

## 4. The blocks

### Block 0 · Preflight — 20 min

Record the baseline the whole night is measured against: the four gates, the
per-module coverage table, `git rev-parse HEAD`, the working-tree state. Create
`log/night_2026-08-09/`. Confirm the machine will not sleep.

*Exit:* `00_baseline.log` exists and the four gates are green. **If any gate is
red at the start, the night stops here and reports** — a night built on a red
baseline attributes its own damage to the wrong block.

### Block 1 · T0.3 — the mutation gate — ~1.5 h

The plan flagged runtime as the unquantified risk, so it is measured first.

1. Run `utils/mutation_probe.py --changed HEAD~5` and time it. **Decision
   point:** if the full-diff sweep exceeds ~20 min, narrow to a coverage-selected
   test subset per file before wiring anything.
2. Wire it as a script (`utils/gate_mutation.py` or a flag on the existing
   probe) with the budget the plan names: **zero surviving mutants on added
   lines**, waivable with an inline `# mutation: <reason>`.
3. Add the CI job to `.github/workflows/gates.yml`, marked non-blocking on the
   first night so a noisy first run does not wedge the repo.
4. **Free output:** every survivor on recent code is a one-line prescription for
   a missing test. That list goes in the report.

*Exit:* the gate runs, its runtime is a number, and the survivor list is written.

### Block 2 · T2.2 — the differential oracle ⭐ — ~2 h

The highest confidence-per-hour task in either document, and the only thing
that can catch class B.

Built on `utils/permutation_probe.py`, which already drives games with two
agent instances, compares per decision, and dumps whole observations. The hook
is `utils/selfplay.py:189-195` — `choice = agentes[yi].agent(obs)` then
`obs = game.battle_select(choice)`, which is exactly *before* and *after* one
decision.

At every attack, retreat and knockout, compare what the agent **believed**
against what `libcg` **resolved**:

- `_our_effective_damage` vs the HP actually removed;
- the KO prediction vs whether the body actually left the field;
- the retreat cost vs the energy actually discarded;
- the prize count vs the prizes actually taken.

Any mismatch dumps the observation in fixture format.

*Why it cannot be replaced by unit tests:* an example-based test asserts the
**same wrong belief the code has**. The simulator is a free, perfect oracle that
is currently unused as one.

*Exit:* the oracle runs over a short soak; every mismatch is a file.

### Block 3 · T2.1 — the invariant monitor + G-A ⭐ — ~2 h

Same hook, a checker on **every** decision. Violations dump to
`log/night_2026-08-09/violations/` in fixture format, ready to be pinned.

From the plan:
- never END a turn with an empty bench;
- never exceed a documented energy cap (Applin 1, the Ogerpon caps);
- never retreat into a body that cannot act next turn;
- `ACTIVE_CARDS_IN_DECK` must reconcile against the simulator's ground truth at
  every reveal;
- never return an out-of-range or illegal option index;
- attachments this turn ≤ 1 manual + granted.

**G-A, the new one — the largest failure class has no guard today:**
> every turn flag on `AGENT_STATE` that is *armed* under a premise must still
> satisfy that premise when it is *consumed*.

Implementation, cheapest first: register each flag with the predicate that armed
it, and check it at the read. If registering all of them is too broad for one
night, start with the family that has already failed — `_ub_engine_pivot_turn`,
the plan pointer, the cession, the rate, the Last-Ditch commitment — and report
how many flags remain unregistered.

*Exit:* the monitor runs; every violation is a fixture; the count per invariant
is in the report.

### Block 4 · The soak — unattended, hours

Both monitors on, across the 19 decks in `deck/opponents/`, seat alternation,
parallel across cores. At 0.1 s/game this is thousands of games per deck.
Findings accumulate as files; nothing is decided.

This block runs **concurrently with blocks 5 and 6** — it is CPU, they are
typing.

*Exit:* `04_soak.log` with games played per deck, violations per invariant,
oracle mismatches, and any forfeit.

### Block 5 · The additive guards — ~1.5 h

- **T3.1 · a suite for `utils/opponent_bot.py`** (427 lines, zero tests). Pin
  its documented policy with the same `StateBuilder` the agent tests use.
  Cheapest high-leverage task in either document: its one known defect made
  whole measurement axes come out NEUTRAL by construction.
- **T2.4 · observation fuzzing.** Structurally mutate real observations (empty
  zones, absent stadium, unknown card id, a zone at maximum, `minCount` 0) and
  assert only *does not raise, returns something legal*.
- **G-C · the score↔fetch seam.** One parametric test over every item with two
  menus (Ultra Ball, Night Stretcher, Bug-Catching Set, Poké Pad, Meowth
  Last-Ditch): **the target the item was scored for is the target it fetches.**
  The doctrine is already written in the project's memory; it has no executable
  guard.
- **G-E · the unmodelled-card census.** Walk `competitor_decks/indice.csv` and
  `records/` and list every opposing attack the projector prices at **0 with a
  cost of ≥3 energies**. Bellibolt's 230 would have appeared without losing a
  game first.

### Block 6 · Instrumentation — ~1 h

- **T0.2 · coverage floors** — `coverage-floors.json` from tonight's measured
  per-module numbers, CI fails on a drop. Note honestly in the file that the
  52 % is the **unit** net: the golden corpus and self-play exercise more, so
  the floor is a ratchet, not a claim about total exposure.
- **T2.3 · hypothesis** — transcribe the 7 properties the plan already names
  (never raises, legal index, caps hold, determinism, monotonicity…), with
  `derandomize` for the PR job.
- **T3.4 · corpus** — harvest toward ~50 records and freeze a compressed subset
  so CI can run the flip-diff.
- **T1.1 half** — expose `_resolve_with_trace` through a test helper and print
  the trace, so the morning's assertions are typing.

### Block 7 · The report — at dawn

One file, `log/night_2026-08-09/REPORT.md`, and a summary in the chat:

1. What ran, what did not, and why — including anything skipped.
2. **Findings, ranked**: oracle mismatches, invariant violations, surviving
   mutants. Each with the fixture that reproduces it.
3. Every number as a delta against block 0's baseline.
4. The morning decision list: the three behavioural fixes, plus whatever the
   night turned up.
5. What I would do next, and what I would not.

---

## 5. Success criteria

The night is a success if, in the morning, there is a **pile of reproducible
findings and a set of detectors that keep working**. It is *not* measured by
lines changed in `main.py` — that number should be **zero**.

Concretely, the night has earned its keep if:

- the mutation gate has a measured runtime and a survivor list;
- the differential oracle ran and its mismatch count is a number (zero is a
  perfectly good answer, and a strong one);
- the invariant monitor ran and every violation is a fixture;
- `opponent_bot.py` has tests;
- the four gates are as green at dawn as they were at midnight.

The failure mode to avoid is the one this project already knows by name: a
number nobody read, or a rule shipped on a board nobody measured.
