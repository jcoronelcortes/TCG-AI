# The night of 13 August 2026 — the forward simulator nobody has ever called

[← Documentation index](README.md)

**Status: written 12 August 2026 (evening), on branch `main`, HEAD `5b064f2`.
Suite 2440 pass / 15 skip in 23 s, `lint_architecture` clean. The working tree
carries the WHOLE of phases A, B and C of
[the engine-source plan](engine-source-plan-2026-08-12.md), uncommitted** —
5 new files, 8 modified. That tree is the first thing §0 asks about.

This plan is written to be executed **autonomously, end to end, while the user
sleeps**. Everything it needs is asked in §0, once, before anything runs. If §0
is answered *"todo por defecto"*, the recommended column applies and the night
proceeds without another question. §7 is the part that makes that safe: what the
executor does when something fails at 03:00 and there is nobody to ask.

---

## 0. START HERE — the seven questions, asked before anything runs

The executor asks these **once, in a single message**, and then does not stop
again until the morning report.

| # | Question | Recommended default | What changes if the answer differs |
|---|---|---|---|
| **Q1 · Baseline** | Phases A/B/C are uncommitted (`cg/battle.py`, `utils/parallel.py`, `utils/local_engine.py`, `cg/build_local_engine.sh`, `cg/engine_patches/`, plus 8 modified). Commit to `main` first, branch it, or export the dirty tree as-is? | **Commit to `main`** — suite green, lint clean, acceptance criteria all passed and recorded | A branch means every M block measures a tree the morning may not keep. A dirty export loses `git archive`, and with it the M/D isolation of §2 — and tonight *depends* on `--base`, so this is not cosmetic |
| **Q2 · Autonomy** | Branch per change, merged to `main` when its written criterion passes? Left unmerged for review? Or measurement only? | **Branch per change + merge on criterion**, auto-revert anything measured neutral ([[politica-neutro-se-revierte-salvo-valor-ilegal]]) | "Unmerged" turns the morning into a review queue. "Measure only" drops track B and frees ~2 h for track D |
| **Q3 · Scope** | Which blocks? D0–D3 (the oracle), M1–M3 (what seeding made affordable), B-list items? | **D0–D2 mandatory, D3 if D0's cost holds; M1 + M2; B2 census only** — M2 is the one with the largest expected surprise | Dropping M2 frees ~1.5 h for D3 and the B list. Dropping D entirely makes this an ordinary measurement night |
| **Q4 · Budget** | Hours and concurrent processes? | **~8 h, `JOBS=6`** (M1 at 400/matchup weighted+seeded, M2 at 1000/arm per revert, oracle at K=20 rollouts) | A 4 h night drops M2 to the three highest-weight reverts and D3 entirely |
| **Q5 · Agent edits** | May the agent's behaviour change tonight, or is tonight instruments-only? | **Yes, under Q2's criteria** — but note D0–D3 build a *grader*, not a policy; the only agent edits tonight would come from what M2 resurrects | Instruments-only is a legitimate and fully unattended night, and costs almost nothing here because D is a grader by construction |
| **Q6 · Finding budget** | When a block returns a worklist of N items, how many get fixed tonight? | **Zero fixed in-flight.** Each finding gets a fixture, a memory and a rank; fixes come from the B list only | Fixing in-flight is how a night loses its baseline: the M blocks would be measuring a moving tree |
| **Q7 · Determinization** ⚠️ | The oracle must fill in hidden information (opponent hand, both decks, prizes). May it **read the true hidden state** (omniscient — valid only for grading), or must it **sample a legal world** from what has been observed? | **Omniscient, and labelled as such.** For "was this decision right?" the true world *is* the ground truth, and it removes sampling noise from a first result | Legal sampling is strictly harder, needs a consistency model, and is only required if the oracle ever becomes a play-time policy. **It never can be while omniscient — that must be written into the module docstring, not just here** |

Three things the executor needs and must **not** ask, because they are already
decided:

* the local engine is legitimate for measurement — the package README says *"use
  it just to build and test your entries"*; what is forbidden is redistribution,
  which rule **R11** and `.gitignore` already enforce;
* the opponents corpus is `deck/real_opponents/` (87 lists, 99.47 % of meta),
  and in matchup mode **our agent never goes first**
  ([[en-modo-matchup-nuestro-agente-nunca-sale-primero]]);
* logs go to `log/noche-2026-08-13/`, never `/tmp`
  ([[corridas-largas-loguean-en-log-no-en-tmp]]).

---

## 1. What tonight inherits

Yesterday's engine work shipped three things, each with a passed criterion:

| Shipped | The number |
|---|---|
| Parallel harness (`--jobs`) | 5.06× at 6 workers, 6.76× at 10, winrates agreeing |
| Seeded engine (`--seeds`) | **87/87 matchups at delta 0.0000** — the control group's noise floor is now zero, against ±6.5/+7.5 before |
| Weighted allocation (`--allocation peso`) | Weighted interval ±1.50 → **±0.46** at equal compute |

Those are not the point. They are the *prerequisites*, and tonight is the first
night that can spend them. Two consequences drive everything below:

1. **Measurement got ~5× cheaper and ~3× sharper**, so questions previously
   priced out are now affordable — above all, re-asking the ones that were
   answered "neutral" inside a ±6.5 noise band.
2. **Phase D is unblocked**, and it turns out to be far cheaper than the plan
   assumed.

### The four facts that make phase D a night, not a month

All four measured while writing this plan, on this machine:

| # | Fact | Measured |
|---|---|---|
| S1 | `cg/api.py` **already wraps the Search API** — `search_begin`, `search_step`, `search_end`, `search_release`. Nothing had ever called them | Read + called |
| S2 | `search_begin` accepts a determinization and returns a root state | `searchId 0`, first try |
| S3 | It is a **tree, not a line**: stepping the same root twice returns two distinct ids | ids 1 and 2 from root 0 |
| S4 | **A full rollout to game end costs 0.02 s** — 117 steps at 6850 steps/s, 0.15 ms/step | Random policy, one core |

S4 is the go/no-go number and it is not close: 11 200 rollouts (280 ties × 2
options × 20) is **~4 minutes on one core** with a random policy. With our own
agent as the rollout policy — the agent being ~85 % of wall time — call it
~15 minutes. The oracle is not the expensive part of this night; it is the cheap
part.

---

## 2. Two tracks, and why the tree is exported

Track **M** is CPU: it answers questions already written down, from an
**exported tree**. Track **D** is the executor: it builds the oracle and commits
to the working tree. They run at the same time and must not touch each other.

    git archive HEAD | (mkdir -p log/noche-2026-08-13/tree && tar -x -C log/noche-2026-08-13/tree)

**Hard rules, every one of them already paid for:**

* while any M block is alive, **no swap-based harness runs** —
  `utils/mutation_probe.py` above all: it *is* the tree for the length of a run
  ([[no-editar-lo-que-un-job-en-segundo-plano-intercambia]]);
* a two-arm gate must define **and call** `provenance()` (lint R7);
* **every instrument ships with both halves** — it catches a planted defect *and*
  stays quiet without one — or it does not ship and does not print
  ([[validar-el-arnes-son-dos-mitades-sensibilidad-y-especificidad]]);
* **census before winrate**, always ([[el-delta-de-el-coste-y-la-busqueda]]);
* any self-play number needs n ≥ 1000 ([[selfplay-gate-tamano-de-muestra]]);
* **every seeded run re-checks the engine first.** `utils/local_engine.py`
  verifies `AllCard()`/`AllAttack()` against the shipped binary on every load; if
  it ever raises, §7's abort rule applies.

---

## 3. Track D — the oracle (this is the axis)

The argument for it in one line: **every instrument this project has grades the
agent against another heuristic, including the differential oracle itself** —
and memory records that half that oracle's residue turned out to be the opponent
deck's fault rather than a defect
([[el-oraculo-es-un-espejo-y-la-mitad-de-su-residuo-es-del-mazo-rival]]). A
rollout grades against **the rules**. That is a different kind of answer.

### D0 · The harness — `utils/search_oracle.py`

**What.** `rollout(obs, forced_choice, seed, policy) -> {"won": bool,
"prizes_taken": int, "steps": int}`: open a search from the agent's observation,
force `forced_choice` as the first selection, then play the rest to the end.

**The one real integration task, named because it is the only thing here that
can surprise:** `api.search_step` returns an `ApiResult` **dataclass**, and our
agent takes a raw **dict**. The JSON is right there before conversion
(`json_to_dataclass(bs, ApiResult)`), so the fix is a thin wrapper that keeps the
dict. Budget 45 minutes; if it is not working in 90, §7 applies and the night
falls back to `policy="random"`, which S4 already proved works end to end.

**Policy.** Default `policy="agent"` — our own agent drives both sides after the
forced choice. This makes the question *"is this choice better given how we
actually play afterwards?"*, which is the right question for a heuristic agent
and a strictly easier one than optimal play. `policy="random"` stays available
as the fallback and as a variance check.

**Both halves (mandatory).** Sensitivity: on a board with a known winning attack,
forcing that attack must beat forcing END at K=20 with a wide margin. Specificity:
two rollouts of the *same* choice with the *same* seed must return the same
result — if they do not, the oracle is measuring its own noise and nothing below
it is valid.

**Deliverable:** the module, both halves passing, and **the measured cost per
rollout under `policy="agent"`** written into the docstring. That number sets
K for D2 and is the input to §7's fallback.

### D1 · The determinizer — `utils/search_oracle.py::determinize`

Under Q7's default this is small and must be *honest about being small*: read
the true hidden state from the battle we are driving and hand it over. Two
requirements:

* the module docstring states, in the first paragraph, that the oracle is
  **omniscient and therefore can never be a play-time policy** — a grader that
  quietly became a policy would be cheating at the competition;
* the signature already takes the alternative (`mode="sampled"`), unimplemented,
  raising `NotImplementedError` with a pointer to this section. A door left
  visibly unbuilt, not invisibly missing.

### D2 · Where the heuristic admits it has no opinion — the tie census

**Why ties first.** A tie is where the agent's own scoring says the two options
are worth the same. The oracle does not have to replace the scorer, only to break
ties — the cheapest possible first job, and there is already a **measured
population**: 280 Ripening ↔ Teal Dance ties ([[el-adjunte-del-turno-y-la-habilidad-empatan-sobre-el-mismo-cuerpo]],
where `ABILITY:150` was made the owner, measured and **reverted**), plus C2's
TIER-vs-score rows (B7 of the pending list says to read them together — do that).

**What.** Replay the golden corpus and the recorded games; at every decision
where the top two options are within ε, roll out both K times (K from D0's cost;
20 unless that number says otherwise) and record which wins more.

**Output.** A table by tie CLASS, not by case: class, population, oracle's
preference, margin, and whether the agent currently agrees.

**Criterion, written now.**
* Agreement ≥ 55 % with a margin whose interval excludes 50 % → the agent is
  already right; the class is closed and recorded as closed.
* Disagreement ≥ 55 %, interval excluding 50 %, population ≥ 30 → **a rule to
  write**, ranked, not written tonight (Q6).
* Interval containing 50 % → the tie is a genuine indifference. **Record it as
  such and stop paying attention to it** — that is a real result and the most
  likely one for most classes.

### D3 · Settle `op_wins_after_ko` *(only if D0's cost holds)*

Memory says it is a coin flip: 54 % accurate, and 94 % of its shelf is already
lost ([[op-wins-after-ko-es-una-moneda-al-aire-el-94-por-ciento-de-su-estante-ya-esta-perdido]]).
That was measured against outcomes, not against the rules. Roll out the boards
where it is computed and compare its prediction with what the rules actually do.

**Criterion:** if rollout accuracy is < 60 %, the field is not predictive and the
morning gets a written recommendation to delete it, with the population attached.
It is one of R10's two open survivors, so this closes a standing item either way.

---

## 4. Track M — the questions seeding just made affordable

### M1 · The canonical baseline

`matchup_matrix --games 400 --weights --allocation peso --seeds 400 --jobs 6`.
One number with a real interval (±0.46 class), stored in
`log/noche-2026-08-13/baseline.txt`. Every later claim this night compares to it.
Cost ~20 min.

### M2 · The reverts that were measured inside the noise ⭐

**This is the block with the largest expected surprise, and the reason is
arithmetic.** Every rule reverted as NEUTRO was judged against a control group
that drifts ±6.5 points. A real +2 was indistinguishable from zero. The floor is
now zero.

Memory names the population — each is a commit that exists and was reverted:

| Revert | Memory |
|---|---|
| Xerosic over Lillie's with two attackers | [[xerosic-sobre-lillie-con-dos-atacantes-medido-revertido]] |
| Deckout vs Crustle | [[deckout-vs-crustle-medido-sin-culpable]] |
| Gust by candidate (KO after retreating) | [[gusteo-modo-por-candidato-ko-tras-retirar]] |
| Ripening free-heal route | [[ripening-ruta-curacion-gratis-medido-revertido]] |
| Stadium before Lillie's | [[crustle-estadio-antes-de-lillie]] |
| Archetype arbiter | [[arbitro-de-arquetipos-medido-y-revertido]] |
| `ABILITY:150` as owner (415 ties) | [[el-adjunte-del-turno-y-la-habilidad-empatan-sobre-el-mismo-cuerpo]] |

**Method.** For each: resurrect the reverted change on a scratch branch, then
`matchup_matrix --base <main> --seeds --allocation peso --games 400`.

**The honest caveat, and it must appear in the report:** common random numbers
collapse to exactly zero only for matchups the change cannot affect. A change
that *does* decide differently desynchronises the RNG stream and keeps real
variance — the gain is a much lower floor, not an infinite one. So M2 sharpens
these verdicts; it does not make them free.

**Criterion:** a revert is re-opened only if the weighted delta's interval
excludes zero **and** the `--control-card` split shows the affected group moving
where the control group does not. Anything else stays reverted, and the memory
gets one line saying it was re-asked under seeds and held.

### M3 · B2's census — the body that raises MY damage

The largest open capability hole, and the report says *census first*
([[pendiente-proyectar-el-cuerpo-que-sube-el-dano-antes-de-gastarlo]]).
Count the boards where a bench body would have raised our damage and was spent
or ignored. **Census only tonight** — no winrate on an unmeasured population.

---

## 5. Schedule

| Window | Track D (executor) | Track M (CPU, exported tree) |
|---|---|---|
| 00:00–00:20 | §0 answers applied; Q1 commit; tree exported; `local_engine --verify` | — |
| 00:20–01:30 | **D0** harness + both halves | **M1** baseline (~20 min), then **M2** starts |
| 01:30–02:15 | **D1** determinizer | M2 continues (7 reverts × ~20 min ≈ 2.5 h) |
| 02:15–04:00 | **D2** tie census + criterion | M2 continues |
| 04:00–05:00 | **D3** if D0's cost held | **M3** census |
| 05:00–06:00 | Report, memories, pending list | — |
| 06:00 | Hard stop. Anything unfinished is reported as unfinished | |

---

## 6. What "autonomous" means here

Every block is **time-boxed**. A block that overruns its box is killed, its
partial output kept, and it is reported as *not finished* — never allowed to eat
the blocks after it. The boxes are in §5 and they are ceilings, not estimates.

---

## 7. When something breaks at 03:00

The executor never asks a question after §0. It takes the rule below, records
which one it took, and continues.

| If | Then |
|---|---|
| `local_engine.verify()` raises (engine drift) | **Every seeded block is void.** Do not fall back silently: re-run M1/M2 unseeded, and label every number in the report `SIN SEMILLA — suelo de ruido ±6,5`. This is R2 of the engine plan and the failure it exists for |
| The local engine is not built / `ptcg_engine/` absent | Run `cg/build_local_engine.sh`; if that fails, apply the row above |
| D0 not working after 90 min | Drop to `policy="random"` (S4 proved it). If *that* fails after 30 more, **cancel D2/D3**, report D0 as failed with the traceback, and give the freed hours to M2's tail and M3 |
| D0's measured cost/rollout > 0.5 s | Lower K to 10 and cancel D3. Say so in the report with the measured number |
| A block crashes | Log the traceback to `log/noche-2026-08-13/<block>.err`, mark it failed, **move on**. Never retry more than once |
| Suite or lint red at a commit point | **Do not commit.** Keep the branch, report it as blocked. A red tree is never merged unattended |
| A criterion is ambiguous on its own terms | Treat as NOT passed. Revert per Q2 and record the ambiguity — [[una-clausula-de-criterio-puede-ser-imposible-de-cumplir]] |
| Disk/RAM pressure from the pool | Halve `JOBS` once and continue; a slower night is a night, a killed one is not |

---

## 8. What the morning gets

1. **`docs/history/night-2026-08-13.md`** — the write-up, including the reverts
   and the blocks that failed. A block that produced nothing is written up too,
   with why.
2. **The pending list**, replacing §8 of the 12 August report.
3. **Memories** for anything non-obvious, linked into `MEMORY.md`.
4. **Branches**, merged or not per Q2, each with its criterion and its number.
5. **`log/noche-2026-08-13/`** — every raw run, so any number can be re-read.

---

## 9. Judging the premise — how this night can be found to have been wrong

The premise is: *the oracle grades against the rules instead of against another
heuristic, and seeding makes the old neutral verdicts re-askable.*

It is falsified if, in the morning:

* **D2's classes all land on "genuine indifference"** with populations too small
  to rank. Then ties were the wrong first target, and the next version should aim
  the oracle at decisions the agent is *confident* about instead — where being
  wrong is more expensive.
* **M2 re-confirms all seven reverts.** Then the ±6.5 noise was never what was
  hiding a gain, the reverts were right on the merits, and the value of seeding
  is confined to *future* changes rather than past ones. That is a good thing to
  learn and it costs one night to learn it.

Both outcomes are worth the night. Neither is the outcome being hoped for, and
the report must say plainly which one happened.

---

Next: [The engine source](engine-source-plan-2026-08-12.md) · [Tools](tools.md) · [The instruments](instruments.md)
