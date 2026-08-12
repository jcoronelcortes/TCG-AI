# The engine source — what it unlocks, and the plan to use it

[← Documentation index](README.md)

**Status: written 12 August 2026. Every number below was measured on this machine
today, not estimated.** The engine source arrived as `ptcg_engine/ptcgProgram 22/`
(gitignored, and it must stay that way — see §6). This page is the analysis and
the work plan that follows from it.

---

## 0. The evidence, before the plan

Eight probes were run before a line of this plan was written. They are what the
plan rests on, so they come first.

| # | Question | Answer | How it was measured |
| --- | --- | --- | --- |
| P1 | Does the source build on this machine? | **Yes — 10.6 s** | `clang++ -std=c++20 -O2 -shared -fPIC`, Apple clang 21, arm64. Two harmless `-Wswitch` warnings, exit 0. Output 1 280 544 B vs shipped 1 245 544 B. |
| P2 | Is the local build the *same engine*? | **Yes** | `AllCard()` returns 459 888 bytes with SHA-256 prefix `d7e29c6284bdb4d3` from **both** the shipped `libcg.dylib` and our build. Identical card data. |
| P3 | Can the engine be seeded? | **Yes — 3 edits + 1 new export** | `GameConfig` already carries `seed`; `ApiBattleStart` throws it away (`deviceRand = true` routes every shuffle to `std::random_device`). Patched, rebuilt, tested. |
| P4 | Does seeding actually reproduce a game? | **Yes, byte-for-byte** | SHA-256 over *every* observation JSON of a full game: seed 12345 twice → identical trace, 178 steps. Seed 99999 → different trace, 182 steps. |
| P5 | Is *our agent* deterministic? | **Yes** | Same engine seed, `PYTHONHASHSEED` ∈ {1, 2, 999} → identical 115-decision trace, same winner, all three runs. No `random`, no hash-order dependence. |
| P6 | Can one process run several battles at once? | **Yes** | Two `BattleStart` calls, two distinct `battlePtr`, played interleaved without interference. The single-battle limit is in `cg/sim.py`, **not** in the engine. |
| P7 | What is the real throughput? | **12.5 games/s → 74.4 at 10 workers** | Full agent-vs-agent games. 1 worker 12.5, 6 workers 62.9 (5.0×), 10 workers 74.4 (5.95×). Machine has 12 logical / 6 performance cores. |
| P8 | How many decks does the top-300 actually contain? | **88 distinct lists** | All 300 files load into `battle_start` without error. Deduplicated by sorted card multiset: **88 unique**, 212 exact duplicates. |

---

## 1. The premise, corrected: the top-300 is 88 decks, and we already have them

The request was to test against the top-300 lists. Measured, that corpus is
smaller than its name:

* 300 files → **88 unique 60-card lists**; 212 files are byte-equivalent copies.
* 87 of those 88 are **already in `deck/real_opponents/`**. The 88th is the one
  list `pesos.csv` marks `no_pilotable` ("no arranca (gana 10%)").
* The duplicate count *is* the meta weight, and `pesos.csv` already encodes it:
  multiplicities 92, 45, 24, 9, 7, 7, 6, 5… map exactly onto `peso_meta`
  0.3067, 0.15, 0.08, 0.03…
* The admitted 87 cover **99.47 % of meta weight**.

**So there is no deck-harvesting work to do.** Running 300 files instead of 88
would cost 3.4× the compute for exactly zero additional information. The corpus
is finished; what is not finished is how we *spend* games on it.

### Where the budget actually leaks

Of the 88 unique lists, **66 appear exactly once** in the top-300 — 0.33 % of the
meta each. Meanwhile the top three lists are 53.7 % of the meta between them.

> At equal games per deck — which is what `utils/matchup_matrix.py` does by
> default — **75 % of the compute buys 22 % of the meta.**

That is the real corpus finding, and it is a scheduling fix, not a data-gathering
one. It is Phase C.

---

## 2. What the source unlocks that the shipped binary cannot

### 2.1 Seeded determinism — the variance killer

This is the headline. `docs/simulator.md` and `utils/selfplay.py` both state, as a
standing constraint, that *"the simulator's internal randomness (shuffles, coin
flips) cannot be seeded through the API"*. Every gate in the project is built
around compensating for that with sample size and seat alternation.

It is no longer true. `Game` already holds an `std::mt19937 rng` seeded from
`GameConfig::seed`; `ApiBattleStart` simply overwrites the decision by setting
`config.deviceRand = true`, which routes `ShuffleDeck`, the target shuffle in
`EffectInstant.h`, and both coin paths in `SelectProc.h` to a fresh
`std::random_device` instead. The patch is three edits in `Api.h` plus one new
exported symbol.

Why this matters more than the speedup: `utils/matchup_matrix.py` documents,
from direct measurement, that at 200 games per matchup the **control group** —
decks running behaviourally identical code in both arms — drifts between **−6.5
and +7.5 points**. That is a pure noise floor, and it is why `--games` had to
rise to 400 and why `--control-card` exists at all.

Under common random numbers, a behaviourally identical arm plays *the same game*,
so its delta is **exactly 0**. The control group stops being a noise estimator
and becomes an assertion.

**The honest limit:** common random numbers collapse to exact zero only while the
two arms make identical decisions. The moment a candidate chooses differently,
the RNG stream desynchronises and variance returns for that deck. So this does
not make affected matchups free — it makes the *unaffected* ones free, which is
what turns a ±7 reading into a decidable one.

### 2.2 The Search API — a forward simulator we have never touched

`Search.h` exposes a branching what-if tree, and **`grep` finds zero references
to it in `main.py`, `ptcg/`, or `utils/`.** It is a first-class capability that
has sat unused for the life of the project.

What it does: `SearchBegin` takes the serialized state plus a **determinization**
— you supply the hidden information (your deck order and prizes, the opponent's
deck, prizes, hand and active) — and returns a state id. `SearchStep(id,
selection)` *forks* a new state from that one and returns a new id; states are
pooled 128 at a time. `manualCoin` lets the caller dictate coin flips instead of
rolling them.

That is precisely the machinery for a **ground-truth decision oracle**. Today
`utils/differential_oracle.py` grades the agent's plan against another heuristic,
and memory records that half its residue turned out to be the opponent deck's
fault rather than a real defect
([[el-oraculo-es-un-espejo-y-la-mitad-de-su-residuo-es-del-mazo-rival]]). Rollouts
would settle those arguments against the rules instead of against another
opinion. This is Phase D and it is the highest-ceiling item on the page.

### 2.3 Instrumented builds

With source we can compile a tracing variant that logs every RNG draw, coin flip
and shuffle. That answers "was this loss variance or a bad decision?" directly,
which is currently the most expensive question in the project to answer — memory
says all thirteen defects of 12 August were found by a human reading a lost game
([[el-canal-de-descubrimiento-es-un-humano-leyendo-una-partida-perdida]]).

---

## 3. What does *not* need the source: parallelism

Worth separating, because it is the cheapest win and it was available all along.

`utils/matchup_matrix.py` and `utils/selfplay.py` contain **no** `multiprocessing`,
`Pool`, `concurrent`, or thread usage — they are entirely sequential on a 12-core
machine. And P6 showed the engine happily runs concurrent battles; the
single-battle restriction is `Battle.battle_ptr`, a *class attribute in the Python
wrapper*.

One measured detail decides the shape of the fix. With the agent driving,
throughput is 1 710 steps/s; with a trivial policy the engine alone does 11 281
steps/s. **The agent is ~85 % of wall time, and it is pure Python** — so the GIL
binds, threads will not help, and the answer is processes. Confirmed: 5.0× at 6
workers, 5.95× at 10.

Concretely, a weighted matrix with `--base` (87 decks × 400 games × 2 arms ≈
70 000 games) goes from **~1.5 hours to ~18 minutes**.

---

## 4. The plan

Phases A and B compose and are independent of each other; do both before C and D.

### Phase A — Parallel harness (no engine source required) · ~1 day · 6× everything

| Step | Work | Done when |
| --- | --- | --- |
| A1 | `cg/battle.py`: a `Battle` handle object replacing the `Battle.battle_ptr` global. `GameInitialize()` stays once per process; the handle carries the pointer. | Two battles run interleaved in one process from Python (P6 proved the engine allows it). |
| A2 | `utils/parallel.py`: a process pool mapping job → result. Each worker imports `cg` once and loads its agent instances once, then drains a **chunk** of games — agent load is ~0.3 s and must be amortised. | 100 games/worker shows ≥4× at 6 workers. |
| A3 | Rewire `selfplay.py` and `matchup_matrix.py` onto it behind `--jobs N`, default = performance-core count. | Both tools accept `--jobs` and default to sequential-equivalent results. |

**Acceptance criterion:** mirror self-play at `--jobs 1` and `--jobs 6` must agree
within the Wilson interval, and wall time must drop ≥4×. If the winrates disagree,
a worker is sharing state it should not — stop and fix before Phase B.

### Phase B — Seeded determinism · ~1 day · removes the noise floor

| Step | Work | Done when |
| --- | --- | --- |
| B1 | Version **`cg/engine_patches/0001-seeded-battle-start.patch`** and `cg/build_local_engine.sh`. Never version the engine source, never version the built binary (§6). | A clean checkout + the engine package reproduces the local build from the script alone. |
| B2 | `BattleStartSeeded(cards, seed)` as a **new** symbol; `BattleStart` keeps its exact signature and behaviour. `deviceRand` is disabled only when a non-zero seed is passed. | P4's test passes: same seed → identical trace hash, different seed → different. |
| B3 | `cg/game_local.py`, gated behind `TCGAI_LOCAL_ENGINE=1`, used only by tools under `utils/`. Add rule **R11** to `utils/lint_architecture.py`: nothing in `main.py` or `ptcg/` may reach the local engine. | R11 fails on a deliberate violation. |
| B4 | Give `matchup_matrix.py` a `--seeds` mode: both arms replay the same seed list. | See criterion. |

**Acceptance criterion — the one that matters:** run `matchup_matrix --base HEAD`
(candidate behaviourally identical to base) under seeds. Every one of the 87
matchups must report delta **exactly 0.000**, not "within noise". Any deck that
moves is a determinism leak; find it before trusting a single seeded measurement.

### Phase C — Spend the budget by meta weight · ~half day

| Step | Work |
| --- | --- |
| C1 | Record in `docs/simulator.md` that top-300 = 88 unique lists and that `deck/real_opponents/` already *is* that corpus. Stop anyone re-harvesting it. |
| C2 | Decide the 88th list: repair the bot so it can pilot it, or accept a documented 0.33 % blind spot. Cheap either way — just make it a decision instead of an accident. |
| C3 | Allocate games ∝ `peso_meta` with a floor, replacing the uniform default. The 66 singleton lists keep a floor for regression coverage; the weight goes where the meta is. |

**Acceptance criterion:** at equal total compute, the weighted schedule must
shrink the confidence interval on the *weighted* winrate versus the uniform
schedule. If it does not, keep uniform and say so.

### Phase D — The Search API as a decision oracle · weeks · highest ceiling

Research, not a checklist. Ordered so each step pays for itself:

* **D1 — Oracle.** At a recorded turn, enumerate our menu, roll each option
  forward over K determinizations, score by outcome. Replaces heuristic-vs-heuristic
  grading with rules-based ground truth.
* **D2 — Validate the projectors.** Point D1 at the damage projector,
  `op_wins_after_ko` and the PHANTOM_KO residue. Memory already says
  `op_wins_after_ko` is a coin flip on 94 % of its shelf
  ([[op-wins-after-ko-es-una-moneda-al-aire-el-94-por-ciento-de-su-estante-ya-esta-perdido]]);
  rollouts can confirm or kill it outright.
* **D3 — Search-backed tiebreak** for the top-N options when heuristic scores are
  close.

**Constraint to respect from the start:** D1 and D2 are *local instruments* with
no time limit. D3 runs at play time and must fit the competition's clock
(`GameConfig::timeLimit`). Do not let D3 pull D1's design toward premature
optimisation.

### Phase E — Instrumented builds · opportunistic

A tracing build that logs every RNG draw, coin and shuffle, wired into
`utils/autopsy.py`. Pick this up when a specific investigation needs it, not
before.

---

## 5. Recommended order

1. **Phase A** — best value-to-effort on the page, needs nothing new, 6× today.
2. **Phase B** — turns the ±7 point control-group drift into an assertion. A and
   B compose: 6× more games *and* each game worth more.
3. **Phase C** — pure reallocation, half a day.
4. **Phase D** — start once A+B make measurement cheap enough to iterate on.

---

## 6. Risks, and the one that could poison everything

**R1 · Licence and competition rules.** `ptcg_engine/ptcgProgram 22/README.md` is
explicit: the package is shared **for competition use only**, is not open source,
must not be shared or republished, and should be deleted when the competition
ends. Therefore:

* `ptcg_engine/` stays gitignored — already done.
* We version **patches and build scripts**, never engine source, never a built
  binary.
* The submission always uses the official `cg/` binaries. The local engine is a
  measurement instrument and never ships.

Building a modified copy locally to test our entry reads as squarely inside
"build and test your entries", but **this is a call for the user to make against
the Kaggle rules, not one this document should make.** Phases A and C do not
depend on it; only B, D and E do.

**R2 · Instrument drift — the dangerous one.** A locally built engine that
silently diverges from the official one would make every local measurement lie,
and we would not notice. P2 showed the card tables are identical *today*. That
must become a test, not a one-off:

* a check that `AllCard()` and `AllAttack()` hashes match the shipped binary;
* a distribution check that unseeded games from both libraries agree.

Both run in seconds and must gate every rebuild.

**R3 · Determinism is only as strong as its weakest side.** P5 shows the agent is
deterministic today. Nothing enforces that it stays so — one `set` iteration or
one `random` call in a future rule silently breaks common random numbers, and
Phase B's guarantees decay into ordinary noise without any error. Phase B's
acceptance criterion (§4, B) is exactly this test; **run it on every change**, not
once.

---

## 7. What this plan deliberately does not do

* **No deck harvesting.** The corpus is complete (§1). Running 300 files instead
  of 88 is 3.4× the compute for zero information.
* **No replacing `cg/` for submission.** The official binaries remain the only
  thing that ships.
* **No engine modifications that change game rules.** Seeding and tracing change
  *how randomness is drawn and observed*, never what is legal. Any patch that
  alters a rule makes every measurement taken with it worthless.

---

Next: [The simulator layer](simulator.md) · [Tools](tools.md) · [Contributing](../CONTRIBUTING.md)
