# The night of 14 August 2026 — the list changed, and nothing on record describes it

[← Documentation index](README.md)

**Status: written 13 August 2026 (night), before anything runs.
Branch `main`, HEAD `5ee49b1`, `main.py` and `ptcg/` **clean against HEAD**.
The working tree is **RED**: `7 failed, 2565 passed, 23 skipped` in 23 s.
The uncommitted change is `deck.csv` itself.**

This night is not like the previous ones. Every night before it graded either the
agent's code or the meta. **Tonight the thing that moved is the sixty cards**, and
that single fact invalidates, or at least re-labels, every number this project has
on record — the 94.50 % headline, the card census, the frozen corpus, the
fixtures, `pesos.csv`, all of it.

So the night has one spine and it is not a new idea: **re-establish the ground,
separating the two things that moved today**, and only then spend what is left on
the pending list.

It is written to run **autonomously, end to end, while the user sleeps.**
Everything it needs is asked in §0, once. If §0 is answered *"todo por defecto"*,
the recommended column applies and nothing stops until the morning report. §8 is
what makes that safe.

---

## 0. START HERE — the eight questions, asked before anything runs

The executor asks these **once, in a single message**, and does not stop again
until the morning report.

| # | Question | Recommended default | What changes if the answer differs |
|---|---|---|---|
| **Q1 · The list** ⚠️ | `deck.csv` changed today and is uncommitted. Tonight measures it (§4). What happens to it in the morning if the measurement comes out **neutral**? | **Nothing. It is kept and reported.** The list is a decision of the deck's owner, not of the gate. [[politica-neutro-se-revierte-salvo-valor-ilegal]] governs *rules the agent proposes*, not a change the user made deliberately — and reverting sixty cards at 04:00 unattended is exactly the kind of act that needs a human awake ([[un-override-del-usuario-no-es-una-excepcion-de-la-politica]]) | "Revert if neutral" makes the night's headline binding and the morning shorter. "Do not measure at all" frees ~2 h and forfeits the only chance to know what the swap bought |
| **Q2 · The red tree** ⚠️ | Seven tests fail, and §3 shows all seven trace to the list. How is the tree greened? | **(a) Adapt the tests, and re-freeze the corpus *after* reading its single flip.** The flip is one decision in `registro_035` and it must be read before `freeze_corpus.py --snapshot-only` runs ([[corpus-dorado-resnapshot-silencioso]]) | **(b)** Adapt tests only, leave the corpus test red and reported — cheapest, but a red gate that stays red stops being a gate. **(c)** Pin every record and fixture to *the list it was played with* — the durable fix (§3.4), ~2 h, and it retires this whole class of failure forever |
| **Q3 · Agent edits** | May behaviour change tonight, under criterion? | **Yes**, branch per hypothesis, merge only on its written criterion, revert anything measured neutral | "Measure only" is legitimate and cheap here: G, L and C are all instruments; only P writes rules |
| **Q4 · Budget** | Hours, workers, games per matchup? | **~7 h, `JOBS=6`, 400 games/matchup**, seeded, `--allocation peso` | A 4 h night keeps §0, G and L and drops C, P and S entirely |
| **Q5 · The deep block** | After L, which pending axis gets the executor's attention? | **S first** (§5: the list change *created* a strategy hole — the Cornerstone whitelist now reaches one card), then **P1/P2** (the two unmodelled cards) | "Hard-matchup starvation" (playbook P2a/P2b/P2c) is the alternative and it is a list question, which is precisely what tonight cannot answer until L lands |
| **Q6 · Network** | May the executor download more real ladder games? (`~/.kaggle/access_token`; there is no `kaggle.json` and the SDK authenticates anyway) | **Yes.** 106 real games is the only unsaturated signal this project has ([[el-bot-generico-tasa-como-muertas-las-cartas-de-remontada]]), and 36 % of them are losses against 6 % simulated. On any failure: skip silently, report it, continue | "No network" costs the only measurement that can judge Unfair Stamp, Fezandipiti ex and the recovery package |
| **Q7 · Commits** | May the executor commit? | **Yes to `main`, in the house style, never on a red tree, never `push`.** Branches for anything under criterion | "No commits" means the morning inherits a large uncommitted diff on top of an already-uncommitted list change |
| **Q8 · Finding budget** | A block returns a worklist of N items; how many get fixed tonight? | **Zero fixed in flight**, except the seven of §3, which are the night's own ground. Each finding gets a fixture, a memory and a rank | Fixing in flight is how a night loses its baseline: L would measure a moving tree |

Three things the executor must **not** ask, because they are already decided:

* the local engine is legitimate for measurement — what is forbidden is
  redistribution, enforced by lint **R11** and `.gitignore`;
* logs go to `log/noche-2026-08-14/`, never `/tmp`
  ([[corridas-largas-loguean-en-log-no-en-tmp]]);
* **census before winrate** ([[el-delta-de-el-coste-y-la-busqueda]]), any
  self-play number needs n ≥ 1000 ([[selfplay-gate-tamano-de-muestra]]), and
  **prizes rank, winrate does not** — 18 of 22 archetypes sit above 92 %
  ([[el-playbook-del-meta-de-500-mazos]]).

---

## 1. What moved today, in one table

Thirteen rule commits and one merge, and then the sixty cards.

| When | What | Where |
|---|---|---|
| 11:33–12:10 | Census of what every card in the pool does · the measuring instrument kept out of the submission · the retreat bill counted **in cards** · what the hand *pays* before what *spends* it · the 500-deck corpus de-versioned · the forced discard asks **whose** card, not which | `d1dbe3c` … `1814ff5` |
| 18:00–18:23 | An energy that reaches **no cost** is worth less than a card · the answer to a menu stored on the next step (×2) · a finisher the front cannot let through · the evolution we fetch brings its own attachment · a number that moves when turn quality does · the prize the agent cannot see, written down | `6da9197` … `e81fd32` |
| 20:19–22:13 | A guard on one rung does not forbid the card · the gust is worth only the attack behind it · the wall that blanks abilities leaves one answer · the reservation is owed one step **later** · **the Cornerstone branch merged** | `9912965` … `5ee49b1` |
| after that | ⚠️ **`deck.csv`**: −1 Tapu Bulu (920), −1 Night Stretcher (1097), +1 Poké Pad (1152), +1 Basic Grass (1). Still 60. **Uncommitted** | working tree |

Two of those carry a debt into tonight:

* **`5ee49b1` entered by decision, not by measurement.** Its own census recorded
  0.89 decisions changed per game and the gate measured NEUTRO; it was kept
  because the user judged the four Crustle routes right
  ([[estrategia-vs-cornerstone-ogerpon]]). It has never been measured against the
  meta. Tonight is the first opportunity, and it costs nothing extra: it is
  inside L's code arm.
* **The list change has no measurement at all**, and it is the larger of the two.

---

## 2. Why every number on record is now suspect — and the trap that would hide it

**The baseline of record is 94.50 % ±0.19 (field) / 95.81 % ±0.25 (top-100),
prizes +4.063**, measured at HEAD `8192c22` on the **old list**. Since then, two
independent things changed: **thirteen rule commits** and **four cards**. A single
re-measurement tonight would produce one delta and attribute it to whichever of
the two the reader already believed in. That is the exact mistake last night's
plan had to cut out of M3 when the corpus and the seat policy moved together.

So L runs **three arms**, and never adds two deltas (§4).

> ### ⚠️ The trap, found while writing this plan — and it would have produced a wrong headline
>
> The obvious way to A/B two lists is `selfplay.torneo(deck_candidate=…)`, and the
> plan of 13 August named a missing `--our-deck` flag on `matchup_matrix` as "the
> one real integration task". **That flag, built as specified, would measure
> something that is not a game.**
>
> `main.py:165` reads `deck.csv` **from the process's working directory, at import
> time**, and the agent derives its whole deck belief from it. `deck_candidate`
> changes only what the **engine deals**. Hand the engine the old list while
> `deck.csv` on disk holds the new one and the agent believes a deck it is not
> playing — which is precisely the failure §3 shows on two of tonight's red tests,
> where the tracker believes **8 prizes with 6 face-down**.
>
> `selfplay.checkout_tree` already says so out loud: it deliberately does **not**
> take the deck from the ref, so both arms of a `--base` comparison pilot the
> same sixty cards. That makes `--base` the right tool for a **code** A/B and
> useless for a **list** one.
>
> **The correct harness needs no new code at all**: give each arm its own
> exported tree with its own `deck.csv` on disk, and run the matrix inside it.
> `main.py` and `ptcg/` are clean against HEAD, so the two trees differ in exactly
> the four cards. `--our-deck` is not built tonight; it is recorded as
> **mis-specified** in the pending list.

---

## 3. Track G — the seven red tests (blocking for every commit)

They are the night's ground: no commit happens over them, and §8's rule about a
red tree is absolute. **All seven are consistent with the list change**, and the
executor's job is to prove that one at a time rather than assume it. The default
finding for each is *stale artefact*; the alarming finding is *a rule that reads
the list and now reads it wrong*, and that one is ranked above every winrate in
the report.

| # | Test | What it says | First reading |
|---|---|---|---|
| G1 | `test_ld_committed_supporter` ×2 | `_score_lillie_determination_play` returns 5000 where `SCORE_VETO` is expected; a PLAY resolves to 1227 instead of 1231 | The scenario's deck no longer holds the card the veto was about. **Check the rule, not only the fixture** |
| G2 | `test_real_opponents_mirror` | `alakazam_1` overlaps **10** with `deck.csv`, pinned at 9 | Mechanical: overlap is a function of the list. Re-pin, and re-check the 60/60 mirror class of `festival_lead_5` — it may no longer be a mirror |
| G3 | `test_the_card_census_closes_on_sixty` | `92492874.json` closes on **62** rows, not 60 | The episode was played with the old list. The census must resolve fates **against the list of the episode** |
| G4 | `test_the_frozen_corpus_runs_on_a_clean_checkout` | one flip: `registro_035_dragapult_3` t6 a2, `[0,1] → [0,2]` | **Read it before re-freezing.** One decision, and Q2(a) requires a human-legible reason in the report |
| G5 | `test_the_ultra_ball_in_flight_becomes_a_prize` ×2 | belief says **8 prizes with 6 face-down** | The invariant `believed ≤ face_down` is violated **by a list mismatch alone**. Ask whether live play can reach it (it should not — `deck.csv` is always both) and whether the clamp should exist anyway |

### G6 · The durable fix, if Q2 answers (c)

Every record and fixture carries the list it was played with, and the replay
harness loads *that* list rather than the current `deck.csv`. It retires this
entire failure class — which will otherwise return on the next list change — and
it is the honest reading of [[el-corpus-grabado-es-de-la-lista-vieja]]. Time-box
**120 min**; if it overruns, fall back to Q2(a) and record the attempt.

Then: `python utils/lint_architecture.py` and the full suite, both green, before
any commit. Time-box for G as a whole: **90 min** under (a), **150** under (c).

---

## 4. Track L — the headline: three arms, two deltas, never their sum

Two trees are exported into the run directory, and **the pool touches neither the
working tree nor anything the executor is editing**:

    D=log/noche-2026-08-14
    git archive 8192c22 | (mkdir -p $D/tree_ayer && tar -x -C $D/tree_ayer)
    git archive HEAD    | (mkdir -p $D/tree_hoy_lista_vieja && tar -x -C $D/tree_hoy_lista_vieja)
    git archive HEAD    | (mkdir -p $D/tree_hoy_lista_nueva && tar -x -C $D/tree_hoy_lista_nueva)
    cp deck.csv $D/tree_hoy_lista_nueva/deck.csv     # the ONLY difference between the last two

`deck/real_opponents_500/` is **gitignored** (`7d8f0f4` de-versioned it), so it is
absent from every exported tree: `--opponents` takes an **absolute** path into the
repository. Same for `pesos.csv`, which `--weights` reads from that directory.

Each arm, from inside its own tree, identical seeds:

    python utils/matchup_matrix.py \
        --opponents /ABS/PATH/deck/real_opponents_500 \
        --weights --allocation peso --games 400 --seeds 400 --jobs 6

| Arm | Tree | Code | List | Answers |
|---|---|---|---|---|
| **A0** | `tree_ayer` | `8192c22` | old | Is the 94.50 % of record reproducible? A seeded re-run should land on it. **This is the control, and if it fails, nothing else tonight means anything** |
| **A1** | `tree_hoy_lista_vieja` | `5ee49b1` | old | **What the day's thirteen commits are worth** — and the first measurement the Cornerstone merge has ever had |
| **A2** | `tree_hoy_lista_nueva` | `5ee49b1` | **new** | **What the four cards are worth** |

**A1 − A0 is the code. A2 − A1 is the list. Their sum is not reported anywhere.**

Report per arm, in this order: **prize differential** with its interval, then
winrate with its interval, then the seat split (`matchup_matrix` prints it per
matchup since last night), then forfeits. Rank archetypes by prizes, never by
winrate.

**Both halves of the harness, mandatory** ([[validar-el-arnes-son-dos-mitades-sensibilidad-y-especificidad]]):

* *Specificity* — A0 must reproduce the number of record within its interval, and
  the seat counters of every row must sum to that row's decided games.
* *Sensitivity* — before A2, one throwaway run of ~200 games against
  `crustle_wall_1` from a tree whose `deck.csv` has been **deliberately crippled**
  (four Grass removed) must come out clearly worse. A harness that cannot see a
  broken list cannot see a four-card swap.

⚠️ **The caveat that must appear in the report:** common random numbers collapse
to zero only where the change cannot act. Two different *lists* desynchronise the
stream from the first shuffle, so A2 − A1 keeps real variance and its interval is
**not** the seeded floor of a code A/B. Do not quote the ±0.19 of a same-list
comparison for it.

Time: three arms × ~35 min ≈ **105 min**, plus the sensitivity run. It starts at
00:20 and it is the only thing that may not be cut.

---

## 5. Track S — what the four cards cost the strategy (Q5)

The list change did not only move a winrate; it **narrowed a rule that is already
written**. This is the one place tonight where a strategy hole is known in advance
rather than hunted for.

**S1 · The Night Stretcher whitelist against Cornerstone now reaches one card.**
`_ns_crustle_allowed_basics` is `(Tapu_Bulu, Pinsir)`; Pinsir is not in the list,
and Tapu Bulu is now a 1-of that is usually the active. The test that pinned this
behaviour says so in its own docstring after today's edit: *"the Cornerstone case
no longer separates the whitelist from the generic scorer"*. So:

1. census how often the whitelist fires at all on the frozen corpus and on
   self-play against `cornerstone_*` and `crustle_wall_*`;
2. if it fires below the 0.5 % floor, **say the rule is now inert** and propose
   its retirement rather than leaving a rule nobody can reach
   ([[una-clausula-de-criterio-puede-ser-imposible-de-cumplir]]);
3. if it fires, decide what the second member should be with **one Tapu Bulu** —
   the four routes of [[estrategia-vs-cornerstone-ogerpon]] are the map.

**S2 · The recovery package is a 1-of now.** One Night Stretcher and one Lana's
Aid against a matchup whose losses are **starvation, not misplay**
([[las-derrotas-de-los-matchups-duros-son-hambre-no-mala-jugada]]) is a
prediction, not a neutrality: Crustle Wall loses 28 % of its games to **deck-out**
and our own deck is the clock ([[el-mazo-es-el-reloj-de-la-carrera-de-premios]]).
A2's Crustle and Cornerstone rows are the direct test, and S2's job is to read
them **as a resource race** — deck-out rate and turn of loss, not winrate.

**S3 · Two Poké Pad and fourteen Grass.** The fishing probabilities moved
(`test_probabilistic_finisher_fishing` already re-pinned 11 outs → 12, 0.5976 →
0.6543 in today's diff). Check that no other probability, threshold or count in
the code was calibrated against **13 Grass** and left behind. `grep` for the
constants; a threshold tuned to the old list is a rule that now fires at the wrong
time.

Time-box **90 min**, executor side, while the pool runs L.

---

## 6. Track C — the census, re-run on the sixty we actually play

`utils/card_census.py` exists as of today and its numbers describe the **old**
list. Re-running it is cheap and it is the only instrument that can say what the
two new cards *do*:

    python utils/card_census.py --games 80 --opponents deck/real_opponents_500 \
        --allocation peso --out log/noche-2026-08-14/censo_lista_nueva.csv

Read three things and nothing more elaborate:

1. **The two arrivals** — Poké Pad's second copy and the fourteenth Grass:
   conversion, dead-in-hand, fodder rate. A second copy that converts like the
   first is a good swap; one that sits in hand is the swap paying for itself in
   the wrong currency.
2. **The two departures** — does Tapu Bulu's remaining copy convert *better*
   (fewer dead draws) and does the single Night Stretcher get used *earlier*?
3. **Whether the four flagged converters moved**: Xerosic's Machinations at
   19.6 %, and the five worst converters declined ~30 % of the time in search.

**Not** on simulated numbers: any judgement about Unfair Stamp, Fezandipiti ex or
the recovery package. Those go to the real-ladder run of Q6 or they do not get
made ([[el-bot-generico-tasa-como-muertas-las-cartas-de-remontada]]).

Time-box **60 min**, pool side, after L.

---

## 7. Track P — the pending list, ranked, with what closes each one

Everything below is already written down; the ranking is by *evidence standing
behind it* × *population*, and nothing here is allowed to eat L, G or S.

| # | Pending item | Population | What closes it | Box |
|---|---|---|---|---|
| **P1** | **Deluxe Bomb (1167) is not modelled anywhere** — 12 counters on the **attacker**, so it is a veto on *who attacks*, not on whom to promote. `grep 1167` → zero hits ([[pendiente-modelar-deluxe-bomb-12-contadores-al-atacante]]) | Inert in self-play by construction (no corpus deck plays it); the bar is the frozen corpus + a fixture on step 84 of episode 92355371 | Model it as a cost paid by the attacker, the way Wood Hammer's self-damage already is. Fixture first | 60 min |
| **P2** | **Promoting the Tera holder surrenders immunity for free** — the retreat branch prices it (`main.py` ~6103), the promotion branch does not ([[pendiente-promover-un-tera-saca-un-cuerpo-inmune-de-la-banca]]) | Same episode; it is a **price**, never a veto, and it enters below the reasons that already rule | Fixture at step 62, then the price, then the corpus | 60 min |
| **P3** | **Festival Lead's negative seat gap** (−1.1 pp at 11.1 % of the top-100), confounded by the mirror class: `festival_lead_5` overlaps 60/60 with our list — **and after today's change it may not any more** (G2 checks it) | 2.8 % of the meta | Re-measure the seat gap with the mirror lists excluded, using A2's rows | 30 min |
| **P4** | **A5 holdout** — `competitor_decks_500/adicionales/`, 370 unlabelled lists, never classified | The honest test of anything fitted to the 500 | Nearest-neighbour classification via `real_opponents.overlap_with`; **classify only** | 30 min |
| **P5** | **`--our-deck` is mis-specified** (§2) | — | One paragraph in `docs/tools.md` and a memory, so nobody builds it as written | 10 min |
| **P6** | **Phase D — the rules oracle** (`Search.h`, the wrapped Search API, a full rollout at 0.02 s) ([night-plan-2026-08-13.md](night-plan-2026-08-13.md)) | The largest open item in the project | **Explicitly not tonight.** It is a night of its own and it is CPU-bound on the same six workers as L | — |

Cut order if late: **P4, then P3, then P2, then P1.** S is cut before P1 only if L
is at risk, and L is never cut.

---

## 8. Schedule

Two lanes. The pool runs from the exported trees; the executor works in the
working tree; **they never touch the same files**. While any pooled block is
alive, **no swap-based harness runs** — `utils/mutation_probe.py` above all, since
it *is* the tree for the length of a run
([[no-editar-lo-que-un-job-en-segundo-plano-intercambia]]).

| Window | Executor | Pool (exported trees) |
|---|---|---|
| 00:00–00:20 | §0 answers applied · run dir · **both lists snapshotted into it** · `local_engine --verify` · trees exported | — |
| 00:20–00:35 | G1–G2 | **L sensitivity** (crippled list, 200 games) |
| 00:35–01:50 | G3–G5 (and G6 if Q2 = c) | **A0** control → **A1** |
| 01:50–02:30 | Lint + full suite; commit G if green (Q7) | **A1** finishes → **A2** |
| 02:30–04:00 | **S1–S3** | **A2** finishes → **C** census |
| 04:00–05:10 | **P1** Deluxe Bomb, **P2** Tera promotion | gates for P1/P2 as they land |
| 05:10–05:50 | **P3**, **P4** — *cut first if late* | — |
| 05:50–07:00 | Report, memories, `MEMORY.md`, pending list | — |
| 07:00 | **Hard stop.** Anything unfinished is reported as unfinished | |

Every block is time-boxed. A block that overruns is killed, its partial output
kept, and it is reported as *not finished* — never allowed to eat the blocks after
it. The boxes are ceilings, not estimates.

---

## 9. When something breaks at 03:00

The executor never asks a question after §0. It takes the rule, records which one
it took, and continues.

| If | Then |
|---|---|
| ⚠️ **A0 does not reproduce 94.50 % ±0.19** | **Stop track L and report it first, above everything.** Either the corpus moved under us (it is derived and gitignored), the engine drifted, or a number of record was never reproducible. Do not compute A1 or A2 deltas against a control that failed |
| ⚠️ **The sensitivity run (crippled list) does not come out worse** | The list harness is blind. **A2 is void**; report the list as unmeasured and say why. Do not fall back to `deck_candidate` — §2 explains why that is not a game |
| ⚠️ **A red test turns out to be a rule reading the list wrongly** (not a stale fixture) | That is the night's top finding, ranked above every winrate. Fixture, memory, and the fix on a branch — merged only if the suite is green |
| `local_engine.verify()` raises (engine drift) | **Every seeded block is void.** Do not fall back silently: re-run unseeded and label every number `SIN SEMILLA — suelo de ruido ±6,5` |
| The local engine is not built / `ptcg_engine/` absent | Run `cg/build_local_engine.sh`; if that fails, apply the row above |
| `deck/real_opponents_500/` is missing or its `pesos.csv` does not sum to ~1.0 | Rebuild it with `utils/real_opponents.py --source competitor_decks_500 --output deck/real_opponents_500` **before** L, and report the rebuild. It is derived and de-versioned; its absence is expected, not an error |
| G6 (Q2 = c) overruns 120 min | Fall back to Q2(a), keep the partial work on a branch, report the attempt |
| Kaggle download fails (Q6) | Skip silently, report it, continue. No real-ladder claim is made from zero games |
| A block crashes | Traceback to `log/noche-2026-08-14/<block>.err`, mark it failed, **move on.** Never retry more than once |
| Suite or lint red at a commit point | **Do not commit.** Keep the branch, report it blocked. A red tree is never merged unattended |
| A criterion is ambiguous on its own terms | Treat as NOT passed, revert, record the ambiguity |
| Disk/RAM pressure from the pool | Halve `JOBS` once and continue. A slower night is a night; a killed one is not |
| Behind schedule at 05:00 | Cut in the order of §7. **Never cut G or L** |
| Anything at all wants to `git push`, touch `submission.tar.gz`, or overwrite `deck.csv` | **Forbidden without a human.** Q1 already settled the list; the rest is outward-facing |

---

## 10. What the morning gets

1. ⭐ **`docs/history/night-2026-08-14.md`** — the write-up, with **A1 − A0 and
   A2 − A1 reported separately and never added**, every failed block and why,
   and the seven red tests each with its verdict (stale artefact / real defect).
2. **The verdict on the four cards**, in prizes first and winrate second, with
   the Crustle and Cornerstone rows read as a **resource race** (S2), and the
   explicit note that a two-list comparison does not enjoy the seeded floor.
3. **The first measurement the Cornerstone merge has ever had** (`5ee49b1`),
   inside A1 — kept, or recorded as a decision the meta does not pay for.
4. **A green tree**, committed, or a precise statement of what is still red.
5. **The pending list**, re-ranked, with `--our-deck` marked mis-specified and
   phase D named as the next night.
6. **Memories** for anything non-obvious, linked into `MEMORY.md`: the
   list-vs-belief trap of §2 above all, the S1 whitelist narrowing, and an update
   to [[el-corpus-grabado-es-de-la-lista-vieja]] with what tonight actually found.
7. **`log/noche-2026-08-14/`** — every raw run, plus **both lists**, so any number
   here can be re-read against the sixty cards it was measured on.

---

## 11. Judging the premise — how this night can be found to have been wrong

The premise is: *the sixty cards moved, so the ground has to be re-established
before anything else is worth measuring, and the two things that moved today can
be separated cheaply.*

It is falsified if, in the morning:

* **A1 − A0 and A2 − A1 are both inside their intervals.** Then thirteen rule
  commits and a four-card swap are jointly worth nothing the meta can see, the
  saturation of the reference bot is the whole story
  ([[el-playbook-del-meta-de-500-mazos]]), and the next night should stop
  measuring against this bot and go to **phase D — a grader against the rules**
  rather than against a bot we beat 94 % of the time.
* **All seven red tests are stale artefacts and nothing else.** Then G was
  bookkeeping, the durable fix (G6) is the only thing worth having from it, and
  the honest conclusion is that a list change costs this project a night of
  re-labelling — which is itself the argument for pinning records to their list.

Both outcomes are worth the night. The report must say plainly which one
happened.

---

Next: [the playbook](playbook-vs-meta-2026-08-13.md) · [the card census](card-census-2026-08-13.md) · [Matchups](matchups.md) · [Tools](tools.md) · [The instruments](instruments.md) · [the deck](deck-and-engines.md)
