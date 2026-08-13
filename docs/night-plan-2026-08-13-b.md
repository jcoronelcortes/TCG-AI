# The night of 13 August 2026 (B) — the 500 decks, and how to pilot against them

[← Documentation index](README.md)

**Status: written 12 August 2026 (night), revised the same night for `8192c22`.
Branch `main`, HEAD **`8192c22`**, tree clean, 2454 tests pass, lint clean.
Phases A/B/C of [the engine-source plan](engine-source-plan-2026-08-12.md) are
**committed**: `--seeds`, `--jobs` and `--allocation peso` are in HEAD and
verified there. That is what this plan depends on.**

> ### ⚠️ Revision: `8192c22` moved the ground this plan stands on
>
> The in-flight work this plan first warned about landed as **`8192c22` — "Take
> the first turn when the engine asks us"** — and it is not a small change. It
> **reverses the seat policy**: the `IS_FIRST` select used to be answered NO on
> purpose (the second player may attack on their first turn); now YES scores 2
> and NO is vetoed.
>
> Three consequences, and each one edits a block below rather than a sentence:
>
> * **There is no coin flip in this engine.** Over 30 openings the select went to
>   seat 0 in all 30, and the seat that answered became `firstPlayer` in all 30.
>   What is random is the seat assignment, not anything inside the engine.
> * **The reference bot also answers YES.** Under the old veto it took the first
>   turn in 60 of 60 games, so *every figure on record describes the
>   going-second half*. Now that both say YES and `torneo` alternates seats, a
>   run splits the first turn **~50/50** (measured 100/100 over 200 games vs
>   `crustle_wall_1`). `OpponentBot(first_choice="second")` pins it.
> * ⚠️ **Every `we_go_first == True` branch now executes for the first time.**
>   None of them has ever run in self-play. That is simultaneously the largest
>   new risk tonight (§7 has a rule for it) and the reason Q6 changed from an
>   optional extra into a mandatory split.
>
> **What this revision changed:** Q6 (was "measure going-first too?", now "pin
> the seat or let it split?"), M1 (its baseline is no longer going-second), M3
> (corpus and seat policy would otherwise be measured as one delta — they are now
> two), M4 (rewritten as the seat split plus the never-executed-branch audit),
> and §7 (the forfeit-spike rule). The memory
> [[en-modo-matchup-nuestro-agente-nunca-sale-primero]] is now **false** and is
> rewritten as part of §8.
>
> **What it did not change:** F1–F5 are properties of the *corpus*, not of the
> agent, so tracks C and A stand exactly as written.

**This is the plan that runs tonight.** The search-oracle plan written for the
same date ([night-plan-2026-08-13.md](night-plan-2026-08-13.md)) was **discarded
on 12 August**: both are CPU-bound on the same six workers and only one fits a
night. Its file is kept, unscheduled, because the four Search-API facts it
measured (S1–S4) belong to
[phase D of the engine-source plan](engine-source-plan-2026-08-12.md) and are
still true. Nothing in this plan waits on it.

What makes this night different from every night before it: **every previous
night graded the agent's code. This one grades the meta and our piloting of a
fixed 60.** The deliverable is not a winrate delta — it is a **playbook per
archetype**, with each of its claims measured and each of its numbers carrying an
interval.

It is written to run **autonomously, end to end, while the user sleeps.**
Everything it needs is asked in §0, once, before anything runs. If §0 is answered
*"todo por defecto"*, the recommended column applies and the night proceeds
without another question. §7 is what makes that safe.

---

## 0. START HERE — the seven questions, asked before anything runs

The executor asks these **once, in a single message**, and does not stop again
until the morning report.

| # | Question | Recommended default | What changes if the answer differs |
|---|---|---|---|
| **Q1 · Corpus** | Replace `deck/real_opponents/` (87 lists, from the top-**300**) or build `deck/real_opponents_500/` beside it? | **Beside it.** `deck/real_opponents_2026-08-07/` is the precedent: corpora are snapshotted, never overwritten. M3 then measures whether the corpus change moved the headline number | Overwriting makes every number on record un-recomputable and silently re-labels the whole history |
| **Q2 · Which meta** ⚠️ | Target the **whole field** (500) or the **top-100**? | **Both, reported separately.** §1 measures that they are *different metas* — Marnie is 21 % of the top-100 and 42 % of positions 401-500. One run, two weightings (§3 M2 explains why the second is nearly free) | Field-only optimises for beating the players we are already beating. Top-100-only optimises on 100 decks and 1/5 of the sample |
| **Q3 · Scope of advice** | Piloting only (play decisions on a fixed 60), or also **list** changes (swapping cards)? | **Both, strictly separated.** Piloting hypotheses are tested and may merge (Q4); list changes are **proposed only, with evidence, never merged** — the 60 is frozen tonight | Piloting-only drops H2 and frees ~1 h. Allowing list merges unattended would change the submission with no human ever having seen the list |
| **Q4 · Agent edits** | May behaviour change tonight, under criterion? | **Yes**, branch per hypothesis, merge only on its written criterion, auto-revert anything measured neutral ([[politica-neutro-se-revierte-salvo-valor-ilegal]]) | "Measure only" is a fully legitimate night here and costs little: tracks C/M/A are all instruments, and only H writes rules |
| **Q5 · Budget** | Hours and concurrent processes? | **~8 h, `JOBS=6`**, 400 games/matchup weighted + seeded (`--allocation peso`) | A 4 h night keeps C, M1, M3 and A on the top-3 archetypes only, and drops M4, A5 and all of H |
| **Q6 · Seat** ⚠️ *(rewritten for `8192c22`)* | Since `8192c22` both sides answer YES and the seat splits **~50/50**, so the baseline now mixes two games that used to be one. Report the mix, or **split it by seat**? | **Split it.** M1 runs as the mix (that is what ladder play now is) and M4 pins each seat with `OpponentBot(first_choice="second")` for the top 4 archetypes. A single mixed number hides a policy that has never been tested on one of its two halves | Reporting only the mix is cheaper by ~40 min but cannot tell a good going-first plan from a bad one averaged with a good going-second one — and going-first is the half no self-play has ever executed |
| **Q7 · Finding budget** | A block returns a worklist of N items; how many get fixed tonight? | **Zero fixed in-flight.** Each finding gets a fixture, a memory and a rank; only H's pre-declared hypotheses are ever measured as changes | Fixing in flight is how a night loses its baseline: the M and H blocks would measure a moving tree |

Three things the executor must **not** ask, because they are already decided:

* the local engine is legitimate for measurement — what is forbidden is
  redistribution, enforced by lint **R11** and `.gitignore`;
* logs go to `log/noche-2026-08-13-b/`, never `/tmp`
  ([[corridas-largas-loguean-en-log-no-en-tmp]]);
* **census before winrate**, always ([[el-delta-de-el-coste-y-la-busqueda]]),
  and any self-play number needs n ≥ 1000
  ([[selfplay-gate-tamano-de-muestra]]).

---

## 1. What was measured while writing this plan

All of it on this machine, from `competitor_decks_500/indice.csv` and the 500
lists themselves. **These five facts are what the night is built on, and three of
them were not known before tonight.**

| # | Fact | Number |
|---|---|---|
| F1 | The 500 decks are **135 unique 60-card lists** | 85 lists = 90 % of the field · 130 = 99 % |
| F2 | **One single list is 32.4 % of the entire field** — 162 of 500 decks, byte-identical | Marnie Grimmsnarl |
| F3 | Eight archetypes are **92 % of the field** (460/500) | Marnie 37.4 %, Alakazam 17.8 %, Crustle Wall 8.2 %, Lopunny/Froslass 7.2 %, Dragapult 6.4 %, Ogerpon Verde 6.2 %, Festival Lead 5.0 %, Lucario 3.8 % |
| F4 ⚠️ | **The top-100 is a different meta from the rest of the ladder** | pos 1-100: Marnie 21 %, Lopunny/Froslass 16 %, Alakazam 15 %, Dragapult 14 % · pos 401-500: Marnie 42 %, Alakazam 14 %, Crustle 13 %, Dragapult 5 % |
| F5 | Against the old top-300 corpus, **Dragapult roughly doubled** | 3.3 % → 6.4 % of the field; Marnie 36.0 % → 37.4 % |

**F4 is the axis of this night and the reason Q2 exists.** The decks that *win*
are not the decks the field *plays*. A single meta-weighted average silently
answers "how well do I beat the players I already outrank" — because 400 of the
500 rows are below the top 100. Every headline number tonight is therefore
reported **twice**: weighted by the field, and weighted by the top-100.

**F2 is the reason this night can be unusually concrete.** Against a
byte-identical list that is a third of the field, a piloting recommendation is
not a generality — it can name cards, turns and prize counts, and be measured to
a ±0.46 interval.

### What tonight inherits from last night

| Shipped and committed | The number |
|---|---|
| `--jobs` | 5.06× at 6 workers, 6.76× at 10, winrates agreeing |
| `--seeds` | **87/87 matchups at delta 0.0000** — the control noise floor is zero, against ±6.5/+7.5 before |
| `--allocation peso` | Weighted interval ±1.50 → **±0.46** at equal compute |

Without those three this plan would not fit in a night; 135 matchups at the old
prices is most of a week.

---

## 2. Track C — the corpus (everything downstream blocks on this)

### C1 · Build it — `utils/real_opponents.py`

    python utils/real_opponents.py --source competitor_decks_500 \
        --output deck/real_opponents_500 --games 40

The tool already does the two things that matter: it **deduplicates** (F1: 500 →
135) and it **screens by pilotability** — the generic bot must play the real list
legally, finish its games, and win *something*. A list the bot cannot pilot
returns a high and **false** winrate for us, and what fails is kept in
`no_pilotables/` and reported, because knowing which part of the meta we cannot
measure is information.

**Both halves, mandatory** ([[validar-el-arnes-son-dos-mitades-sensibilidad-y-especificidad]]):

* *Sensitivity* — `pesos.csv` weights must sum to ~1.0 over admitted lists, and
  the admitted count must be in 80–135. Outside that, C1 failed.
* *Specificity* — ⚠️ **the F2 list (162 copies, 32.4 %) must be admitted.** If
  the single largest list in the meta fails the screen, the night's headline
  number is measuring the bot getting stuck on a third of the field. §7 has the
  rule; it is not a detail to note and continue past.

One recorded caution: an excluded list is not always "cannot start" — the 88th
list of the old corpus was excluded because a matchup we win 100 % of the time
**arbitrates nothing** ([[el-top-300-son-88-mazos-unicos-y-ya-los-tenemos]]).
The report must give the *reason* per exclusion, not just the count.

Time-box **60 min**.

### C2 · The band report — `utils/meta_representation_report.py`

    python utils/meta_representation_report.py --decks competitor_decks_500 \
        --band-size 50 --top-k 4

F4 was found by hand at band size 100–150; this is the tool that says it
properly, per 50 positions, with the dominant archetypes and the exact repeated
lists. Its markdown goes into the morning report **as-is**. Time-box 10 min.

### C3 · The second weighting — `pesos_top100.csv`

Same admitted lists, weights recomputed over positions 1-100 only. This is a
~30-line script and it is the whole of Q2's cost. Time-box 20 min.

**Allocation caveat, and it must appear in the report:** `--allocation peso`
spends games *according to weight*, so a matrix allocated by field weight
under-samples the lists that matter to the top-100 summary. Allocate by
**max(field, top100)** weight with the existing floor, so both summaries rest on
an adequate sample. Otherwise the top-100 number arrives with an interval too
wide to say anything and the night's second axis is decorative.

---

## 3. Track M — the measurement

### M1 · The baseline, both weightings

    python utils/matchup_matrix.py --opponents deck/real_opponents_500 \
        --weights --allocation peso --games 400 --seeds 400 --jobs 6

Output to `log/noche-2026-08-13-b/baseline_campo.txt`: the per-matchup winrate,
sorted weakest-first, each with its 95 % Wilson interval and its forfeits.
**Every later claim tonight compares to this file.** ~30-35 min at 135 matchups.

⚠️ **Since `8192c22` this is a ~50/50 seat mix, not a going-second number, and it
must be labelled `ASIENTO MIXTO ~50/50` in the file and in the report.** It is
therefore **the first baseline of the new seat policy** and is not comparable
with any figure on record — all of those describe the going-second half. Do not
compute a delta against a historical number anywhere tonight; the only legitimate
comparisons are M3's (corpus, code held fixed) and M4's (seat, corpus held
fixed).

### M2 · The top-100 summary — nearly free, and here is why

The expensive thing is the **per-matchup winrates**; the weighted summary is
arithmetic over them. So M2 is **not a second run**: it re-weights M1's completed
table with `pesos_top100.csv` and writes `baseline_top100.txt`. Report the two
headline numbers side by side, plus the per-archetype rows where they disagree
most — that list *is* the first draft of the playbook's priorities.

### M3 · Continuity — did the *corpus* change the question?

Same command against the old `deck/real_opponents/` (87 lists, top-300),
weighted. If the headline moves more than the intervals allow, the corpus change
**re-labels every number on record**, and the report must say so plainly and name
which past verdicts now rest on a corpus we no longer use. ~20 min.

⚠️ **`8192c22` introduces a confound here and it has to be cut deliberately.**
Two things changed at once — the corpus (300 → 500) and the seat policy
(always-second → ~50/50). A naive M3 measures their sum and attributes it to the
corpus. So M3 runs **both arms at HEAD**: old corpus vs new corpus, same code,
same seat behaviour. That isolates the corpus. The seat is M4's job and nothing
else's. Report the two deltas separately and never add them.

### M4 · The seat — the half that has never run (Q6)

Rewritten for `8192c22`. This is no longer an optional extra: the commit's own
message records that **every `we_go_first == True` branch executes for the first
time**, and a playbook has to say what to do on turn 1 in the half of games we
now open.

⚠️ **Corrected during execution — the first draft of this block was wrong twice,
and both corrections make it cheaper.**

**Error 1: `OpponentBot(first_choice="second")` does not pin us second, it pins us
first.** Trace it: the `IS_FIRST` select reaches seat 0 only, and `torneo`
alternates the candidate's seat by `i % 2`. When we are seat 0 we answer YES and
open; when the bot is seat 0 and *declines*, we open as well. So the flag yields
**we-go-first ~100 %**, not the going-second arm the draft asked for. There is no
flag on HEAD that pins us second, because that would require our agent to answer
NO — which is the pre-`8192c22` code, a different commit, and would confound the
seat with the policy.

**Error 2: no extra games are needed at all.** `selfplay.accumulate` has always
maintained `cand_primero` / `cand_segundo` as `[wins, played]`, keyed off
`r["primer_jugador"]`; `selfplay.py` prints them and `matchup_matrix.py` simply
never did. Surfacing them costs nothing and yields the split for **all 133
matchups** instead of 4 archetypes.

**So M4 is not a separate run.** It is a reporting change to `_row`/`_print_row`
(made, linted, smoke-tested) and M1 now emits, per matchup:

    asiento: primero 54.0% (27/50) segundo 48.0% (24/50)

**The split is EXACT, not approximate.** `torneo` alternates deterministically by
`i % 2`, so each matchup gets precisely half its games in each seat — verified
20/20 and 20/20 on a two-deck run. The commit message's "~50/50" understates it.

**Both halves, as met:** *sensitivity* — a planted asymmetry shows up, since the
two seats are reported as independent counters over disjoint game sets;
*specificity* — the two counts must sum to the decided games of the row, which is
checkable on every row of M1's output and is asserted in §8's read-back.

**What this leaves genuinely open**, and it goes to the pending list rather than
tonight: the going-second arm is no longer reproducible on HEAD in isolation, so
*no run tonight is comparable in kind with the historical going-second figures.*
That is a property of `8192c22`, not of this plan.

---

## 4. Track A — why we lose (this is where the playbook comes from)

The premise, and it is recorded: **13 of 13 defects this project has found were
found by a person reading a lost game**
([[el-canal-de-descubrimiento-es-un-humano-leyendo-una-partida-perdida]]).
Tonight cannot replace that reader. What it can do is **prepare the reading**:
harvest the losses, cluster them into classes, and rank the classes so the
morning reads the 6 that matter instead of 300.

### A1 · Harvest the losses

For each of F3's eight archetypes, against its **highest-weight admitted list**:
`utils/autopsy.py --opponent <csv> --games 400 --census`. The tool already
records the decision stream of losses only, runs detectors that reuse the agent's
own calculators, and — v2 — classifies each loss by **mode**: prizes / bench_out
/ deckout / limite. That mode is what separates "we lost the prize race" from
"we got milled", and against a stall deck they are different games with different
advice. Time-box 20 min per archetype, **run under the pool, not serially.**

### A2 · The census, with its control group

`autopsy.py --census` is v3 and carries a control group
([[autopsia-v3-censo-con-grupo-de-control]]). Use it. A finding class whose
frequency does not separate from control is **not a class**; it is the
instrument's own noise, and the recorded discipline is to say so rather than rank
it ([[matchpoint-el-gate-no-arbitra-mide-la-frecuencia]]).

### A3 · Cluster into failure classes

Per archetype, from A1's findings, three counts and nothing more elaborate:

1. **When** the prize race was lost — the turn distribution, not the mean;
2. **What the last live decision was** — the first MAIN select of the losing
   turn, with the count of legal non-END plays the menu offered (value left on
   the table). This is exactly what the v2 autopsy already records, and the
   reason it records the *first* main rather than the closing END.
3. **Which of our 60 cards never got played** in that matchup, across all games.
   Cheap, and the most direct route to a list finding (Q3) there is.

### A4 · Rank

Score each class by **archetype weight × class frequency × margin**, and report
the ranking with all three factors visible, never just the product. A class
worth +2 against 37 % of the field outranks a certainty against 1 %; F4 means
that ranking must be printed **twice**, once per weighting, and the disagreements
called out.

### A5 · The holdout — the 370 unlabelled extras

`competitor_decks_500/adicionales/` holds **370 further lists with no index and
no archetype labels.** They are not part of the 500 and they are the honest test
of everything above: recommendations derived from the 500 that do not survive
here are fitted to the exact lists we measured, not to the meta.

Tonight's use is deliberately minimal — **classify only**, by nearest-neighbour
overlap against the 135 admitted lists (`real_opponents.py` already has
`overlap_with`), and report how many fall into F3's eight archetypes versus
something the 500 never showed us. A recommendation is validated against this set
only if track H finishes early. Time-box 30 min, and **if it overruns, cut it** —
it is the most droppable block in the plan and it is placed last for that reason.

---

## 5. Track H — the hypotheses, measured

A4's ranking produces claims. A claim is not a recommendation until it has been
measured. **Each hypothesis needs its criterion written before it runs**, and an
ambiguous criterion counts as NOT passed
([[una-clausula-de-criterio-puede-ser-imposible-de-cumplir]]).

### H1 · Piloting hypotheses (may merge, per Q4)

Take the **top 3** of A4. For each, a scratch branch, then:

    python utils/matchup_matrix.py --opponents deck/real_opponents_500 \
        --weights --allocation peso --games 400 --seeds 400 --jobs 6 \
        --base main --control-card <id>

**Criterion:** merge only if the weighted delta's interval excludes zero **and**
`--control-card` shows the affected group moving where the control group does
not. Anything else is reverted and gets one line in its memory saying it was
asked and held.

**The caveat that must appear in the report:** common random numbers collapse to
exactly zero only for matchups the change *cannot* affect. A change that decides
differently desynchronises the RNG stream and keeps real variance. Seeding gives
a much lower floor, not an infinite one.

### H2 · List hypotheses (proposed only, never merged — Q3)

**The one real integration task, named because it is the only thing here that can
surprise:** `matchup_matrix` takes our deck implicitly from `deck.csv`, but
`utils/selfplay.py` already accepts `deck_candidato` / `deck_base` as lists of 60
ids (`selfplay.py:370`). So a list swap is measurable, and the missing piece is a
CLI flag threading a `--our-deck` through the matrix to that existing parameter.
Budget **45 min**; if it is not working in 90, **drop H2 entirely** and report the
list findings from A3.3 as unmeasured proposals with their card counts. Do not
spend the night on plumbing.

---

## 6. Schedule

Two tracks. Track C/M/A-CPU runs under the pool from an **exported tree**; the
executor works in the working tree and they must not touch each other:

    git archive HEAD | (mkdir -p log/noche-2026-08-13-b/tree && tar -x -C log/noche-2026-08-13-b/tree)

**While any pooled block is alive, no swap-based harness runs** —
`utils/mutation_probe.py` above all: it *is* the tree for the length of a run
([[no-editar-lo-que-un-job-en-segundo-plano-intercambia]]).

| Window | Executor | Pool (exported tree) |
|---|---|---|
| 00:00–00:20 | §0 answers applied; tree exported; `local_engine --verify` | — |
| 00:20–01:20 | **C1** corpus + both halves | — (C1 needs the pool for its screen) |
| 01:20–01:50 | **C2** bands, **C3** top-100 weights | **M1** baseline starts |
| 01:50–02:30 | **M2** re-weighting (arithmetic) | M1 finishes → **M3** continuity |
| 02:30–04:00 | **A3** clustering as A1 lands | **A1/A2** the 8 archetypes |
| 04:00–04:40 | **A4** ranking | **M4** seat, top 4 |
| 04:40–05:40 | **H2** integration (45 min box) | **H1** top-3 hypotheses |
| 05:40–06:10 | **A5** holdout classification — *cut if late* | — |
| 06:10–07:00 | Report, memories, pending list | — |
| 07:00 | **Hard stop.** Anything unfinished is reported as unfinished | |

Every block is **time-boxed**. A block that overruns is killed, its partial
output kept, and it is reported as *not finished* — never allowed to eat the
blocks after it. The boxes are ceilings, not estimates.

---

## 7. When something breaks at 03:00

The executor never asks a question after §0. It takes the rule, records which one
it took, and continues.

| If | Then |
|---|---|
| ⚠️ **The F2 list (162 copies) fails C1's screen** | **Do not proceed to M1 as written.** The headline would measure the bot stuck on 32 % of the field. Fall back to the *second* Marnie list by weight, label every field-weighted number `SIN LA LISTA DOMINANTE`, and make this finding the first line of the report |
| C1 admits < 80 lists | Corpus is over-screened. Re-run once with `--no-filter` for the dedupe only, use the OLD 87-list corpus for M1, and report C1 as failed with the rejection reasons |
| `local_engine.verify()` raises (engine drift) | **Every seeded block is void.** Do not fall back silently: re-run unseeded and label every number `SIN SEMILLA — suelo de ruido ±6,5` |
| The local engine is not built / `ptcg_engine/` absent | Run `cg/build_local_engine.sh`; if that fails, apply the row above |
| H2's `--our-deck` not working after 90 min | Drop H2. Report A3.3's list findings as unmeasured proposals |
| ⚠️ **Forfeits or step-limit games spike above C1's screening levels** | This is the first night `we_go_first == True` ever executes, so **suspect the new branches before suspecting the corpus.** Do not silently discard the games: record the forfeit rate per seat, and if the pinned-first arm forfeits materially more than the pinned-second one, that is **tonight's most valuable finding** — a crash in code no self-play has ever reached. Report it first, above every winrate |
| A block crashes with a traceback naming a `we_go_first` path | Same rule as above: keep the traceback, mark the block failed, and rank the finding at the top of the morning list. It is a defect, not an instrument problem |
| A block crashes | Traceback to `log/noche-2026-08-13-b/<block>.err`, mark it failed, **move on.** Never retry more than once |
| Suite or lint red at a commit point | **Do not commit.** Keep the branch, report it blocked. A red tree is never merged unattended |
| A criterion is ambiguous on its own terms | Treat as NOT passed, revert per Q4, record the ambiguity |
| Disk/RAM pressure from the pool | Halve `JOBS` once and continue. A slower night is a night; a killed one is not |
| Behind schedule at 05:00 | Cut in this order: **A5, then M4, then H2, then H1.** Never cut C or M1 — everything else is relative to them |

---

## 8. What the morning gets

1. ⭐ **`docs/playbook-vs-meta-2026-08-13.md`** — the actual deliverable. One
   section per archetype in F3, each carrying: our winrate with its interval
   (both weightings), the loss-mode distribution, the ranked failure classes, the
   seat note if M4 ran, and the recommendations **split into piloting (tested)
   and list (proposed)**. A section with nothing measured says so.
2. **`docs/history/night-2026-08-13-b.md`** — the write-up, including every
   block that failed and why.
3. **`deck/real_opponents_500/`** — the new corpus with `pesos.csv`,
   `pesos_top100.csv`, `no_pilotables/` and a reason per exclusion.
4. **The pending list**, ranked, with populations attached.
5. **Memories** for anything non-obvious, linked into `MEMORY.md` — F4 above all,
   plus the **rewrite of [[en-modo-matchup-nuestro-agente-nunca-sale-primero]]**,
   which `8192c22` made false. It must not be merely deleted: what replaces it is
   *there is no coin flip — seat 0 is asked and becomes the first player, so what
   is random is the seat, and since both sides now answer YES the first turn
   splits ~50/50.* A memory that reverses is more valuable than one that vanishes.
6. **`log/noche-2026-08-13-b/`** — every raw run, so any number can be re-read.

---

## 9. Judging the premise — how this night can be found to have been wrong

The premise is: *the 500 decks support piloting advice that the 87-list corpus
could not, and the top-100 is a different enough meta to change what that advice
is.*

It is falsified if, in the morning:

* **M3 shows the headline number unchanged** and **M2's two weightings agree
  archetype by archetype.** Then F4 is a curiosity about ladder position and not
  about play: the 87 lists were already the right corpus, the 500 bought nothing
  but confidence intervals, and the next night should stop rebuilding corpora and
  go back to the agent's code.
* **A4's classes all fail to separate from A2's control group.** Then the losses
  against this meta have no structure the current detectors can see, the playbook
  is a list of winrates with no advice attached, and the honest next step is the
  [search oracle](night-plan-2026-08-13.md) — a grader against *the rules* —
  rather than more census against heuristics.

Both outcomes are worth the night, and the second one is an argument for the
plan this night displaced. Neither is what is being hoped for, and the report
must say plainly which one happened.

---

Next: [Matchups](matchups.md) · [Tools](tools.md) · [The instruments](instruments.md) · [The engine source](engine-source-plan-2026-08-12.md) · [the discarded oracle night](night-plan-2026-08-13.md)
