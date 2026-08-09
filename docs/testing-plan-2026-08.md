# Testing strategy review — August 2026

A review of what the test estate measures today, what it structurally cannot
measure, and a phased plan to close the gap. Every number below was measured on
the working tree of 2026-08-08, not estimated.

---

## 1. What we have, measured

| Signal | Value |
|---|---|
| Suite | **1 784 passed, 13 skipped, 11 s** (`pytest -q tests/`) |
| Test code | 45 073 lines, ~300 files |
| Source under test | 12 724 statements (`main.py` + `ptcg/`) |
| **Statement coverage** | **52 %** (6 166 statements never executed by the suite) |
| Frozen fixtures | 279 |
| Golden corpus | **11** records |
| Property-based tests | **2 properties, 1 file** |
| Metamorphic probes | 2 (menu permutation, decision grid) |
| Mutation | tool exists, run ad-hoc, not a gate |
| A/B (self-play) | manual, minutes per run, not in CI |
| Gates in CI | 2 of 4 (suite + architecture lint) |

### Coverage where the code actually is

The suite is thinnest exactly where the code is densest. The ten biggest
decision modules and what the suite executes of them:

| Module | Statements | Coverage |
|---|---:|---:|
| `ptcg/turn/options/card.py` | 1 093 | **27 %** |
| `ptcg/turn/options/retreat.py` | 840 | **42 %** |
| `ptcg/turn/supporters.py` | 719 | 62 % |
| `ptcg/decision/ultra_ball.py` | 681 | **45 %** |
| `ptcg/turn/energy.py` | 669 | **26 %** |
| `ptcg/turn/options/play.py` | 529 | **36 %** |
| `ptcg/turn/finalize.py` | 440 | **40 %** |
| `ptcg/calc/damage.py` | 323 | 57 % |
| `ptcg/decision/night_stretcher.py` | 303 | **28 %** |
| `ptcg/turn/options/evolve.py` | 199 | **6 %** |
| `main.py` | 3 688 | 55 % |

Six of the seven files modified in the current working tree (`evolve.py`,
`card.py`, `retreat.py`, `finalize.py`, `ultra_ball.py`, `damage.py`) sit in
that low-coverage band. **New rules are being written into the least-watched
part of the tree**, which is the opposite of where a suite should be strong.

### What the mutation probe already proved

The sweep of 2026-08-07 (`log/night_2026-08-07/10_mutation_sweep.log`) mutated
only the lines the recent diffs had *added* — lines that each came with a new
test:

```
ptcg/turn/options/card.py : killed 4, SURVIVED 6
ptcg/turn/options/play.py : killed 1, SURVIVED 3
```

**Ten of fourteen mutations of freshly written, freshly tested code survived.**
A threshold written as `>=` can be rewritten as `>`, a `1` as a `2`, an `and`
as an `or`, and the whole suite stays green. That is the single most important
measurement in this document, and section 3 explains why it happens.

### What the permutation probe already found

18 174 decisions over 150 games, **101 order-dependent (0.56 %)** — including
`ATTACK:195` vs `RETREAT`, which is not a cosmetic tie but a strategic fork
resolved by the position the simulator happened to emit.

### One broken thing, right now — ~~broken~~ **FIXED, commit `d14179e`**

`python -m pytest -q` from the repository root — the command `CONTRIBUTING.md`
and `docs/testing.md` both name as the *first gate* — **failed on this machine
with 294 collection errors**. `log/*/base_tree/tests/` and
`log/*/cand_tree/tests/` are full copies of the suite left behind by self-play
gates, and pytest collected them and hit basename collisions. CI did not see
it because `log/` is git-ignored. Locally, the documented first gate was red.

Closed by T0.1: `testpaths` + `norecursedirs` in `pytest.ini`. Same 1784
passed / 13 skipped from the root as from `tests/`.

---

## 2. The three structural weaknesses

Everything in section 4 follows from these. They are not "we need more tests";
they are properties of the *kind* of testing being done.

### W1 — The suite is a memory, not an explorer

Almost every test file is named after a game that was lost:
`test_do_not_retreat_the_healthy_for_the_wounded_wall.py`. That is a genuinely
excellent discipline — it is why fixed mistakes do not come back — but it has a
hard ceiling: **it can only cover situations that have already cost a game.**
The 48 % of statements never executed is the set of boards no lost game has yet
produced. Every one of those is a rule nobody has ever confirmed fires
correctly.

### W2 — The oracle is the *choice*, not the *reason*

The typical assertion is "on this board the agent picks option X". That pins
the output of a long chain of thresholds, tiers and tie-breaks, and it pins it
at exactly one point of that chain's input space. Move the threshold by one and
the same board still produces the same choice — which is precisely why 10 of 14
mutants survived. The test is watching the answer, not the mechanism that
produced it.

This is fixable and cheap, because the machinery already exists:
`ptcg/engine/rules.py::_resolve_with_trace` already returns a named trace
(`rule_name=score`, `adjustment:score->score`) of which rule fired and which
adjustment moved it. It is only wired into the piloted subset.

### W3 — "Is it better?" rests on one untested opponent

Self-play is the only gate that answers the question the project actually cares
about. It is:

- **manual and slow** — minutes per run, never in CI, so a regression in
  playing strength can only be caught by someone remembering to look;
- **measured against `utils/opponent_bot.py`**, a greedy bot with *no tests of
  its own*. Its own docstring records the cost of that: until 2026-08-02 it did
  not use abilities, which made the harness structurally blind to Marnie's
  Munkidori engine — an engine that took 5 of the 7 prizes we lost to in real
  games. **Every axis measured against that bot before that date came out
  NEUTRAL by construction.** The infrastructure that decides what ships is the
  least tested code in the repository.
- **judged with fixed-N frequentist reads** (400 / 1 000 / 6 000 games) with
  ±6.5 points of noise at 200, which is a lot of compute spent to resolve small
  effects.

---

## 3. Direct answers to the six questions

| Question | Verdict | Why |
|---|---|---|
| More **unit** scenarios? | **Yes, but targeted** | Not more of the same — the marginal example-based test on an already-covered path buys almost nothing. Aim them at the 26–45 % modules, and write them as *boundary pairs* (§ T1.3), not single points. |
| More **integration** tests? | **Yes — highest structural gap** | Every test today asserts *one* decision. The audit calls sequencing "the densest part of the code" (Supporter before retreat, search before the item lock, Teal Dance before the attachment) — and nothing tests a *sequence*. |
| More **A/B**? | **No more volume — more validity** | Adding games to an invalid comparison buys precision, not truth. Fix the opponent model, add a second policy, and switch to sequential stopping (§ Phase 3): same confidence for ~40–60 % of the compute. |
| More **hypothesis**? | **Yes — biggest ratio gap** | 2 properties for 12 724 statements. Property tests are the only tool here that reaches boards no game produced *and* needs no human to know the right play. |
| **Mutation** testing? | **Yes — promote from tool to gate** | It is already built, already ran, and already found that most new code is unwatched. The missing piece is not the tool, it is making it block a merge. |
| Other strategies? | **Yes — three** | (a) a **differential oracle** against the simulator, (b) **assertion-driven exploration** inside self-play, (c) **fuzzing** the observation for robustness. All three find boards nobody has looked at. |

**If only three things get done: T0.3 (mutation gate), T2.2 (differential
oracle), T2.1 (invariant monitor in self-play).** Those three find *new* defects
rather than re-confirming known ones.

---

## 4. The plan

Effort is in focused working days for one developer with agent assistance. Each
phase is independently useful; nothing later depends on all of something
earlier.

### Phase 0 — Unblock and instrument · ≈1 day

**T0.1 · Fix suite collection** — ✅ **DONE, commit `d14179e`** (15 min, as estimated)
*Why:* the documented first gate was red locally (294 collection errors from
self-play tree copies under `log/`).
*Benefit:* the command in `CONTRIBUTING.md` works on a machine that has ever
run a gate. Removes a trap that silently trains a contributor to distrust the
suite.
*As shipped:* `testpaths = tests` plus a `norecursedirs` that keeps `.*` in
front — overriding `norecursedirs` discards pytest's default, which is the only
thing excluding `.venv-1/`. Verified to lose nothing: all 153 test files of the
project are in `tests/`, and 1784 passed / 13 skipped is identical from the
root, from `tests/`, on one file, under `-k` and with an explicit `.`.

**T0.2 · Coverage ratchet in CI** — ✅ **DONE, 2026-08-09**
`utils/gate_coverage.py` + `coverage-floors.json` (37 modules, seeded at
today's measurement) + the `coverage` job in `.github/workflows/gates.yml`.
Validated in both directions, which is the house rule for a detector: it stays
quiet on the real report and fails with exit 1 on a synthetic 7-point drop in
`retreat.py`. Tolerance 0.5 points, so a refactor that deletes covered
statements does not cry wolf; modules under 40 statements are not floored
because their percentage moves in whole digits.
*Original estimate below, kept for the record.* — 2–3 h
Publish per-module coverage in the CI job and fail when any module drops below
its recorded floor (a checked-in `coverage-floors.json`, raised as it improves;
never lowered without a comment).
*Why:* `evolve.py` reached 6 % without anyone noticing, and the current diff
touches it.
*Benefit:* new code can no longer land unwatched. Cheap, permanent, no
judgement calls.

**T0.3 · Mutation as a pre-merge gate** — 🔶 **BUILT 2026-08-09, not yet in CI**
`utils/gate_mutation.py`, which is the narrowing this task turned out to need.
The unquantified risk in the paragraph below was measured on the night of 8–9
August: the raw `--changed` sweep of a five-commit diff was heading for ~90
minutes, because every one of ~100 mutants re-ran all 1 800 tests. The gate now
builds a line→test map once with coverage CONTEXTS and runs each mutant only
against the tests that execute its line; a changed line NO test executes is
reported as `UNCOVERED` without spending a mutant at all, and a line carrying
`# mutation: <reason>` is skipped before it is mutated rather than after.
**The runtime, measured end to end on the four-commit diff of this morning:
8.6 SECONDS** (six files, 74 added lines), against the ~90 minutes the raw
sweep was heading for. It fits in a pre-merge hook with room to spare.

Its first run is also its own justification: the Full Metal Lab fix that landed
this morning — found by a night of self-play — came back with **15 surviving
mutants and 6 ranges no test executes at all**, including both wave-2 copies in
`supporters.py` and `play.py`. The canonical copy's three survivors are now
killed by `tests/test_the_stadium_takes_thirty_in_the_canonical_model.py`
(verified: 3 SURVIVED → 3 killed); the rest are the standing work list.
*Still open:* the CI job.
*Original text.* — 4–6 h ⭐
Wire `utils/mutation_probe.py --changed <base>` into the pre-merge script and a
CI job on pull requests. Budget: **zero surviving mutants on added lines**, or
an explicit `# mutation: <reason>` waiver on the line.
*Why:* 10 of 14 mutants survived on code that had just been written *with* a
test. That is the measured failure rate of the current discipline.
*Benefit:* the strongest single quality lever available, because it measures
the suite instead of the agent. Every survivor is a one-line prescription for
the test that is missing.
*Risk:* runtime. Mitigate by mutating only diff lines and running the mutant
against a `-x -q` subset selected by coverage of that file.

### Phase 1 — Fix the oracle · ≈4–6 days ⭐

**T1.1 · Generalise the rule trace and assert on it** — 🔶 **HALF DONE**
`tests/rule_trace.py` hands back the trace the engine already builds, with
`assert_reason(trace, "winning_gust")` and `assert_adjusted`, validated in both
directions and demonstrated on a real ladder of the agent. What remains is the
judgement half: deciding WHICH rule name each board ought to name.
*Original text.* — 2–3 days
Extend `_resolve_with_trace` coverage beyond the piloted subset to the five
hottest decision paths (gust ranking, promotion, retreat, attachment, Ultra
Ball), expose the trace through a test helper, and add
`assert_reason(choice, "prize_dominance")`.
*Why:* W2. A test that pins the *reason* dies when the threshold moves; a test
that pins the *choice* does not.
*Benefit:* mutation score on those paths should move from ~30 % to ~80 %
without writing a single new board. It also makes every future test cheaper to
write and far easier to review — the assertion states the rule by name.

**T1.2 · Retrofit the 30 highest-value existing tests** — 1 day (incremental)
Add a reason assertion to the tests guarding rules that have been re-broken
before (the Boss's-gust family, promotion, retreat).
*Benefit:* converts the most valuable part of the regression memory from
point-oracles to mechanism-oracles.

**T1.3 · Boundary pairs from `decision_grid.boundaries()`** — 1–2 days
For every numeric threshold the grid reports, generate the *pair* of tests —
one board on each side of the boundary — instead of the single board the rule
was fitted on.
*Why:* an off-by-one in a fitted threshold is the defect class the mutation
probe reports most.
*Benefit:* kills the entire `boundary: 1 -> 2` and `GtE -> Gt` mutant families
by construction, and documents the thresholds the code *really* has rather than
the ones its comments claim.

### Phase 2 — Explore what nobody has looked at · ≈6–9 days ⭐

**T2.1 · Invariant monitor inside self-play** — ✅ **DONE, 2026-08-09**
`utils/invariant_monitor.py`. Six of the seven invariants below are in, and the
seventh is refused in writing: "never retreat into a body that cannot act next
turn" is not an invariant — measured, `not can_attack` holds 9.8–11.4 times per
GAME, so a turn without an attack is the ordinary shape of a development turn,
and judging it needs the agent's own energy model, i.e. a second copy of it.
Two findings so far, and the second is real: the empty-bench one was correct
play (pinned), and `DECK_BELIEF` caught the card tracker filing the Ultra Ball
it is CURRENTLY PLAYING as a prize — see
`tests/test_the_ultra_ball_in_flight_becomes_a_prize.py`.
*Original text.* — 2–3 days ⭐
Run the existing harness with a checker on **every** decision, not just the
final score. Violations dump the full observation to `log/violations/` in
fixture format, ready to be pinned. Starting invariant set:

- never END a turn with an empty bench;
- never exceed a documented energy cap (Applin 1, the Ogerpon caps);
- never retreat into a body that cannot act next turn;
- the tracked belief (`ACTIVE_CARDS_IN_DECK`) must reconcile against the
  simulator's ground truth at every reveal;
- never return an out-of-range or illegal option index;
- energy accounting: attachments this turn ≤ 1 manual + granted.

*Why:* W1. Thousands of games per hour produce boards no human will ever
construct, and an invariant needs no human to know the right play.
*Benefit:* this is the highest-yield source of *genuinely new* edge cases in
the plan. It converts compute into fixtures automatically, which is exactly the
loop the project already runs by hand after every loss.

**T2.2 · Differential oracle: our model vs the simulator** — ✅ **DONE, 2026-08-09**
`utils/differential_oracle.py`. It found the real defect the plan hoped for
(Full Metal Lab, unmodelled: the agent's own damage projection was 30 too
generous) and it cost three corrections of the DETECTOR to get there, which is
the lesson worth keeping: v1 reported 16 764 findings that were its own bugs.
*Original text.* — 2 days ⭐
At every attack, retreat and knockout in self-play, compare what the agent
*predicted* (`_our_effective_damage`, the KO prediction, retreat cost, prize
count) against what `libcg` actually *resolved*. Any mismatch is dumped.
*Why:* this is a defect class with a documented history in this project —
"the promotion believed a 30 that the engine resolves at 210" (commit 682ef74).
A wrong belief produces a legal, plausible, losing play, and **no example-based
test can find it**, because the test asserts the same wrong belief the code has.
*Benefit:* the simulator is a free, perfect oracle that is currently unused as
one. Highest confidence-per-day ratio in the plan.

**T2.3 · Hypothesis: 2 → ~15 properties, with a nightly soak** — 2–3 days
Candidate properties, all of which need no expected answer:
never raises on a legal board · returns a legal index · the documented caps
hold across the whole generated space · a strictly better board never produces a
strictly worse plan mode · adding a copy of a card to hand never *removes* a
legal play the agent takes · removing an opposing threat never makes the agent
more defensive (monotonicity, the grid property generalised) · the same
observation twice gives the same answer (determinism).
Run the nightly soak with a large example budget and a persistent Hypothesis
database, with `derandomize` in the PR job so the suite never flakes.
*Benefit:* covers the shrinking-input path — when it breaks, it hands back the
*minimal* counterexample, which is the expensive part of every autopsy today.

**T2.4 · Observation fuzzing for robustness** — ✅ **DONE, 2026-08-09**
`tests/test_the_agent_survives_a_board_it_has_never_seen.py`: 12 real boards x
8 structural mutations (every zone emptied in turn, the stadium removed, a card
id in no table, `minCount` 0, their bench swept). Zero exceptions, zero illegal
answers. The legality checker is itself checked in both directions.
*Original text.* — 1 day
Mutate real observations structurally (empty zones, absent stadium, unknown
card id, a zone at maximum, a select with `minCount` 0) and assert only "does
not raise, returns something legal".
*Why:* an exception in the container is an instant loss, and the agent runs
against decks it has never seen.
*Benefit:* cheap insurance on the only failure mode that costs a whole game
regardless of strategy.

### Phase 3 — Make the "is it better?" verdict trustworthy · ≈5–7 days

**T3.1 · A test suite for `opponent_bot.py`** — 1–2 days
Pin its documented policy — attach priority, ability cap, retreat condition,
gust target, effective-damage attack choice — with the same `StateBuilder` the
agent tests use.
*Why:* W3. It has none, and its one known defect invalidated whole axes of
measurement.
*Benefit:* protects every A/B number the project will ever produce. The
cheapest high-leverage task in the plan.

**T3.2 · A second opponent policy** — 2 days
Add one distinct policy (e.g. prize-greedy, or a shallow lookahead) and report
the matrix against both.
*Why:* a single fixed opponent is an overfitting target — a rule can win
against one greedy bot's specific mistakes and lose to a real deck.
*Benefit:* a change that wins against both is far more likely to be real. A
change that wins against one and loses to the other is a finding, not noise.

**T3.3 · Sequential stopping (SPRT) for A/B** — 1–2 days
Replace fixed-N reads with a sequential test at a declared effect size, keeping
seat alternation.
*Why:* fixed 400/1 000/6 000-game runs spend the same compute on an obvious
result as on a marginal one.
*Benefit:* typically **40–60 % fewer games for the same error rates**, which
directly converts into more axes measured per night. Also removes the "peek at
the running number and stop when it looks good" bias, which fixed-N reads
invite and which inflates false positives.

**T3.4 · Grow and freeze the golden corpus** — 1 day
11 records is thin for a net whose job is "which decisions did your change
flip". Harvest to ~50 nightly, and check in a compressed frozen subset so CI
can run the comparison instead of skipping it.
*Benefit:* the flip-diff — the single most useful review artefact this project
produces — starts working on a clean checkout and on every pull request.

### Phase 4 — Sustain · ongoing

**T4.1 · One nightly script** — 0.5 day
The `log/night_2026-08-07/` run already is this pipeline, executed by hand.
Turn it into a committed script: suite → lint → corpus → mutation sweep →
permutation → hypothesis soak → matrix, one report file.

**T4.2 · Test-suite hygiene, mutation-informed** — 0.5 day + ongoing
45 073 lines of tests is an asset with a maintenance cost. Use the mutation
probe in reverse: a test that kills no mutant that another test does not
already kill is a candidate for deletion. Publish an index from rule name →
test file so a contributor finds the guard before rewriting the rule.

---

## 5. Summary

| Phase | Focus | Effort |
|---|---|---:|
| 0 | Unblock and instrument | ≈1 day |
| 1 | Assert the reason, not the choice | 4–6 days |
| 2 | Explore boards nobody has seen | 6–9 days |
| 3 | Trustworthy A/B verdict | 5–7 days |
| 4 | Sustain | ~1 day + ongoing |
| | **Total** | **17–24 days** |

The ordering is deliberate. Phase 0 makes quality visible, Phase 1 makes the
existing 1 784 tests *mean* more without writing new boards, Phase 2 finds
defects that no example-based test can reach, and Phase 3 makes the verdict
that decides what ships something worth trusting.

The recurring theme: this project is excellent at *remembering* every mistake it
has made, and has almost no machinery for *finding* a mistake it has not made
yet. Phases 1 and 2 are that machinery.
