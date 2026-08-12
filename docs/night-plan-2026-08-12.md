# The night of 12 August 2026 — every bug today was found by a human reading a lost game

[← Documentation index](README.md)

**Status: written 12 August, on branch `main`, HEAD `710c198`, suite 2419 pass /
14 skip in 21 s, `lint_architecture` clean. The working tree carries one
uncommitted fix** (Festival Lead's second wave — `main.py`, `ptcg/cards/ids.py`,
`ptcg/state/agent_state.py`, 3 tests, 3 fixtures).

This plan is written to be executed **autonomously, end to end, by one agent**.
Everything it needs from the user is asked in §0, before anything runs. If §0 is
answered with *"todo por defecto"*, the recommended column applies and the night
proceeds without another question.

---

## 0. START HERE — the six questions, asked before anything runs

The executor asks these **once, at the beginning, in a single message**, and then
does not stop again. Every one has a recommendation; the recommendation is what
the nights of 10 and 11 August actually did.

| # | Question | Recommended default | What changes if the answer differs |
|---|---|---|---|
| **Q1 · Baseline** | The Festival Lead fix is uncommitted. Commit it to `main` first, put it on a branch, or export the dirty tree as-is? | **Commit to `main`** — suite green, lint clean, it is the same shape as the last three nights | A branch means every M block measures a tree the morning may not keep; a dirty export means no `git archive` and the M/C isolation of §3 is lost |
| **Q2 · Autonomy** | Branch per change, merged to `main` when its written criterion passes? Branches left unmerged? Or measurement only, agent untouched? | **Branch per change + merge on criterion**, with automatic revert of anything measured neutral ([[politica-neutro-se-revierte-salvo-valor-ilegal]]) | "Unmerged" turns the morning into a review queue; "measure only" drops track B entirely and frees ~4 h for track M |
| **Q3 · Scope** | Which of C1–C6 (detectors) and B1–B10 (the pending backlog)? | **C1–C4 mandatory, C5–C6 if the clock allows; B1, B2, B8 from the backlog** — the three with a written method or a new fixture already in hand | Fewer detectors buys more B items, and the whole argument of §2 is that tonight the detectors are worth more than the fixes |
| **Q4 · Budget** | Hours and concurrent processes? | **~8 h, `JOBS=6`** (gates at 15 000 games/arm, matchup matrix at 400/matchup, invariant monitor at 30 000) | A 4 h night drops M3/M5 and halves the gates; the whole machine allows M3 wide *and* the mutation gate in the same window |
| **Q5 · Agent edits** | May the agent's behaviour change tonight, or is tonight instruments-only? | **Yes, under Q2's criteria** | Instruments-only is a legitimate night — it is what §2 argues is the bottleneck — and it makes the night fully unattended |
| **Q6 · Finding budget** | When a detector returns a worklist of N items, how many get fixed tonight? | **Zero fixed in-flight.** Each finding gets a fixture, a memory and a rank; fixes come from the B list only | Fixing in-flight is how a night loses its baseline: the M blocks are measuring a tree that is moving |

Two more things the executor needs and must **not** ask, because they are already
decided in memory:

* opponents: the weighted matrix runs over `deck/real_opponents/` (89 lists), and
  in matchup mode **our agent never goes first**
  ([[en-modo-matchup-nuestro-agente-nunca-sale-primero]]);
* logs go to `log/noche-2026-08-12/`, never `/tmp`
  ([[corridas-largas-loguean-en-log-no-en-tmp]]).

---

## 1. What the day taught, as classes rather than cases

Thirteen defects were fixed on 12 August (seven in the staging that `f229ff1`
carried, four in the commits of the day, one in the working tree, one — the
`_ub_real_fodder` quantifier — spanning both). **The finding that decides tonight
is not any of them:**

> **Thirteen of thirteen were found the same way: a person read a lost episode.**
> Not one came from the suite, the frozen corpus, the differential oracle, the
> invariant monitor or self-play. The corpus caught exactly one — *after* the
> fact, as a snapshot that disagreed (`74f85f1`: golden had `[5]`, code gave
> `[3]`).

That is the whole quality picture in one sentence. This project's nets are
**regression nets**: excellent at stopping a known behaviour from moving,
structurally incapable of finding an unknown one. The discovery channel is a
human with a JSON log, and it does not scale past a handful of turns a day.

So tonight does what the night of 11 August did, and it worked: **turn the day's
cases into classes, and build the detector that finds the class without a human
in the loop.**

| Class | Today's cases | The detector that was missing | Block |
|---|---|---|---|
| **A card's text is not modelled at all** | Deluxe Bomb (1167): `grep -rn "1167\|Deluxe"` → zero hits. 120 to our own attacker, unmodelled | Nothing enumerates the card texts we *could* be playing against and asks which ones the code has never heard of | **C1** |
| **The TIER decides before the number** | `_TIER_ENERGY` handed to every ATTACH regardless of worth (`74f85f1`); `_TIER_DEVELOP` above an ordinary search with one bench seat left (`fcfb17d`) | No instrument counts the menus where the chosen option was outscored by one it outranked by tier | **C2** |
| **Data with no consumer** | `op_wins_after_ko` / `op_prizes_after_ko` — computed, printed in the plan, read by nobody, for two days (`710c198`) | No lint asks whether a field anyone bothered to compute is ever read | **C3** |
| **The premise expired and the guard did not notice** | Vetoes opening `not state.supporterPlayed` go blind the moment it is spent (`f229ff1`); Festival Lead's two waves already thrown (working tree); the Stamp resetting a hand a veto was priced on | The flag monitor covers flags that survive the *board*; nothing measures the blind window of a guard hung on a *spent turn resource* | **C4** |
| **Legality read where the result was meant** | Three rules in one commit: the order, the fetch and the charge all asked "is this legal" on a turn with no tomorrow (`fcfb17d`) | Nothing replays the corpus under a forced `do_or_die` and lists the rules that answer the same either way | **C5** |
| **A quantifier asked one at a time** | `_ub_real_fodder` asked about ONE protected card per call, so each of the two was the other's proof nothing was burning (`f229ff1`) | `duplicate_protection_audit.py` exists for the latch; it does not ask the single-vs-set question | **C6** |
| **A general law with a consumer still missing** | The last-resort band took its 3rd consumer (the Supporter slot) and its 4th (the energy tier) on consecutive days | A census of every constant that encodes a *law*, against the list of modules that read it | **M0** (report only) |
| **A threshold written by hand** | `_ub_cancel_tomorrow_supporter` bounded at a hand of three; the hand had four | ±1 sensitivity sweep over numeric literals inside rule predicates | **M6** (report only) |

Two of these classes are worth a sentence each, because they are the ones with
open pending work behind them:

* **Unmodelled card text** is not one bug, it is a *catalogue-sized hole*. Deluxe
  Bomb, the Iono/Bellibolt line ([[linea-iono-bellibolt-invisible-al-codigo]]),
  and the family the memory already names — Do the Wave's `damage = 0`, Powerful
  Hand, Assemble Alloy — are all the same shape: an effect that does not live in
  `attack_table`. C1 enumerates the whole hole in one run.
* **TIER over score** is already doctrine ([[tier-de-orden-manda-sobre-la-puntuacion]])
  and today it cost two separate turns. Doctrine without a population is a
  belief. C2 turns it into a number.

---

## 2. Two tracks, and why the tree is exported

Track **M** is CPU: it answers questions already written down. Track **C** is the
executor: it builds detectors and commits them. They run at the same time and
must not touch each other.

    git archive HEAD | (mkdir -p log/noche-2026-08-12/tree && tar -x -C log/noche-2026-08-12/tree)

Every M block runs from the export. Track C then edits and commits the working
tree all night without a block loading a half-written file.

**Hard rules, all of them paid for once already:**

* while any M block is alive, **no swap-based harness runs** —
  `utils/mutation_probe.py` above all: it *is* the tree for the length of a run
  ([[no-editar-lo-que-un-job-en-segundo-plano-intercambia]]);
* a two-arm gate must define **and call** `provenance()` (lint R7) — a gate that
  cannot see its own change measures zero, and here zero orders a revert;
* every detector ships with **both halves** — it catches a planted defect *and*
  stays quiet without one — or it does not ship, and it does not print;
* **census before winrate**, always. Do not ask a winrate of a 0.1 % event
  ([[el-delta-de-el-coste-y-la-busqueda]] cost 90 000 games to confirm what a
  census had said three days earlier);
* any self-play number needs n ≥ 1000 ([[selfplay-gate-tamano-de-muestra]]).

---

## 3. Track C — the detectors (this is the axis)

Each block below states its **calibration against real history**: the tree of a
known commit where the detector must produce a known finding. This is the
sensitivity half, and tonight it is free, because the defects were fixed today
and `git` still has the boards.

### C1 · The card-text coverage census — `utils/card_text_census.py` *(cheapest, largest)*

**What.** For every card id that appears in `deck/real_opponents/` (89 lists),
`deck/opponents/` and our own list: pull `card_table[id].skills[].text` and
`.attacks[]` from the simulator, and report whether that id — or its constant in
`ptcg/cards/ids.py` — is referenced anywhere under `main.py`, `ptcg/`.

The text is there. Verified while writing this plan:

    >>> card_table[1167].skills
    [Skill(name='Deluxe Bomb', text='If the Pokémon this card is attached to is in
     the Active Spot and is damaged by an attack from your opponent's Pokémon
     (even if this Pokémon is Knocked Out), put 12 damage counters on the
     Attacking Pokémon...')]

**Output.** One table, ranked by *(lists that play it × copies)*, in three bands:
**never referenced** (Deluxe Bomb's band) · **referenced by id only** (we know
the card exists; we may not model what it does) · **modelled** (a rule names it).
Findings are worklist items with a rank, not verdicts — a card can be legitimately
irrelevant, and the report says so in its own header.

**Two halves.** *Sensitivity:* Deluxe Bomb (1167) must land in band 1 — it is the
known defect, still unfixed. *Specificity:* Powerful Hand, Festival Grounds and
Myriad Leaf Shower must land in band 3; if any modelled card lands in band 1 the
grep is wrong, not the code.

**Cost.** ~1 h. **Criterion:** none needed — a census does not change behaviour.
It ends the night as `docs/tools.md` entry plus a memory with the top 20.

### C2 · The tier-vs-score inversion census — `utils/tier_inversion_census.py`

**What.** At the one choke point where the menu is ordered, record every decision
where the chosen option's **score was strictly lower** than that of an option it
beat **on tier alone**. Report per ordered pair *(winning tier, losing tier)*:
frequency, and the median score gap.

**Why it is the highest-value block.** Both of today's ordering bugs are exactly
one row of that table (`_TIER_ENERGY` over an 11 900 search; `_TIER_DEVELOP` over
the same). The output is a ranked list of *every place the same trade is being
made*, over 3 580 frozen decisions plus N self-play games.

**Two halves.** *Sensitivity:* run it on `74f85f1^`; the `registro_006` step-54
board must appear, `_TIER_ENERGY` over tier 0, gap 11 880. *Specificity:* on
HEAD that row must be gone and the ATTACH must still take back its tier once the
real plays are spent — the rule yields the order, it is not cancelled.

**Cost.** ~1.5 h. **Output:** worklist ranked by frequency × gap. Rows above the
0.5 % exposure floor become B-list candidates for a later night; nothing is fixed
tonight (Q6).

### C3 · Lint R10 — a computed field with no reader

**What.** A tenth rule in `utils/lint_architecture.py`: every field of `TurnPlan`
and of `AgentState`, and every `@property` derived from one, must have at least
one reader outside its own module and outside `tests/`. A field may be exempted
only by an inline comment giving the reason, in the shape the other lint
exemptions already use.

**Care required — the trap that makes this rule useless if missed:** the fields
are read *through their properties*. A grep for `.op_wins_after_ko` finds nothing
even after `710c198` fixed it, because the consumer reads
`plan_of(ctx).do_or_die`. R10 must resolve **property → the fields it reads**, and
count a property's readers as readers of those fields. Measured while writing
this plan, on HEAD, with the naive grep: `win_route`, `win_needs_supporter`,
`win_needs_charge`, `mode` and `op_wins_after_ko` all report zero readers, and at
least three of those are false positives of exactly this kind.

**Two halves.** *Sensitivity:* on `710c198^` the rule must flag
`op_wins_after_ko` — it was two days old and unread, and it is the bug the rule
exists for. *Specificity:* on HEAD it must be silent, and it must stay silent
about `win_route`, which is read through three properties.

**Cost.** ~1.5 h. **Criterion:** it lands only if both halves pass. A lint that
cries wolf on `win_route` is worse than no lint.

### C4 · The blind-window census — spent turn resources

**What.** Every predicate in a rule that reads a turn resource flag
(`supporterPlayed`, `energyAttached`, `retreatUsed`, the Festival wave counter,
and whatever the AST sweep finds of that shape) is a guard with a **blind
window**: the decisions of the turn that happen *after* the resource is spent.
Report, per rule: the size of that window over the frozen corpus, and whether the
rule's answer inside the window is the one it would give outside it.

This is the class of `not state.supporterPlayed` (today) and of the Festival
waves (today). It is *not* what `FLAG_MIRROR`/`FLAG_UNSTUCK` cover — those catch
a flag that outlives the board; this catches a guard that stops asking.

**Two halves.** *Sensitivity:* on `f229ff1^` the Ultra Ball cost vetoes must
report a non-empty blind window on the `registro_006` turn-6 board.
*Specificity:* rules with no turn-resource read must report no window at all.

**Cost.** ~2 h. **Output:** ranked worklist. Expect the report to be larger than
the finding — say so in the header.

### C5 · The `do_or_die` differential — legality where result was meant *(if the clock allows)*

**What.** Replay the frozen corpus twice: once as-is, once with
`TurnPlan.do_or_die` forced true. List the rules whose answer **does not change**
in either direction. Those are the rules that price a play against turns that do
not exist — the class of the three that `fcfb17d` fixed.

**Care:** the population is deliberately tiny (18 of 3 580, 0.50 %) and the
defensive machinery here has measured *negative* three separate times when made
to fire more often. This block produces a **worklist for reading**, never a
change. Its output is a list of names, ranked by how many DENY boards they touch.

**Two halves.** *Sensitivity:* on `fcfb17d^`, `_ub_no_attacker_prefer_meowth` and
`_charge_active_finishes` must both appear. *Specificity:* on HEAD both must be
gone.

**Cost.** ~2 h.

### C6 · The single-vs-set quantifier audit *(if the clock allows)*

**What.** Extend `utils/duplicate_protection_audit.py`: for every corpus menu
holding **two or more** protected cards, ask each protection function with each
card individually and with the set, and flag the disagreements. That
disagreement, on one board, was today's `_ub_real_fodder`.

**Two halves.** *Sensitivity:* `f229ff1^`, `registro_006` turn 6 step 81 — the
Xerosic/Lillie's pair must disagree. *Specificity:* HEAD, silent there.

**Cost.** ~1 h, because the harness already exists.

---

## 4. Track B — the behaviour backlog, consolidated

Every pending item in memory, in one place, ranked. **Q3 picks from this list;
nothing else gets touched.** Ordering rule: an item runs only if it has a written
method *or* a fixture already in hand — everything else waits for the census that
tells it whether it has a population.

| id | The pending item | Source | Method status | Gate / criterion |
|---|---|---|---|---|
| **B1** | The turn ends at END with a playable Meowth ex in hand and three free bench seats (`registro_026` t8 vs Crustle) | [[pendiente-el-turno-acaba-con-un-meowth-jugable-en-mano]] | **Written** — isolate the suspect veto's constant at 0 ([[aislar-una-regla-poniendo-su-constante-a-cero]]), measure on the matchup gate vs `crustle_kangaskhan.csv` | The Meowth-vs-END ranking is *pre-existing*; if the cause is a deliberate "do not hand a 2-prize ex to the wall" rule, the finding is that it is undocumented where it is read, and the item closes with a comment, not a change |
| **B2** | The projector "which body, when I bench it, lifts MY damage over the threshold" | [[pendiente-proyectar-el-cuerpo-que-sube-el-dano-antes-de-gastarlo]] | Mirror of `op_scaling`, which exists on their side; catalogue in `utils/op_scaling_census.py` | The largest capability hole on the list. Census first: how many corpus decisions bench a body while a cheaper one reaches the same threshold |
| **B3** | Deluxe Bomb (1167): 120 to our own attacker, a veto on **who attacks** | [[pendiente-modelar-deluxe-bomb-12-contadores-al-atacante]] | Sibling of Wood Hammer's self-damage, which *is* modelled — read that route before inventing one | Inert by construction in self-play (no `deck/opponents/` list plays it): the bar is the frozen corpus (50/3580) plus a fixture at step 84 |
| **B4** | Promoting a Tera pulls an **immune** 2-prize body off the bench | [[pendiente-promover-un-tera-saca-un-cuerpo-inmune-de-la-banca]] | The retreat branch already respects it (`main.py` ~6103); the promotion branch charges nothing | It is a **price**, not a veto — it enters below the reasons that already rule, and it applies only to the Tera holder |
| **B5** | The same Stamp sentence with Xerosic (`XEROSIC_HAND_CAP` = 3) | Proposal of 12 Aug, item 3 | Named today; competes for the Supporter slot | Same shape as the Stamp fix already landed |
| **B6** | The Meowth ex pair of `registro_021` t5 — the only one still sharing protection in the KEEP band | [[el-latch-dispara-y-una-regla-general-lo-deshace]] | A Basic is not in `_SUPP_PLAY_IDS`; that is the whole diagnosis | Corpus flip review; no winrate |
| **B7** | The 280 Ripening ↔ Teal Dance ties | Night of 11 Aug, task 4 | Boards already dumped in `log/noche-2026-08-11/permutacion/` | Re-triage with the permutation probe **before** writing any tie-break: the 415 ABILITY ties turned out to rest on two wrong premises and were reverted |
| **B8** | Where the ability points when it forces its attachment | Night of 11 Aug, task 4 | Work on the sub-scorer, not on the tie | Follows B7 |
| **B9** | `_teal_dance_possible` reads the field **before** the search resolves | Night of 11 Aug, task 2 | Cheap, if the `registro_002` board reappears | Conditional on the board reappearing |
| **B10** | The Iono / Bellibolt line, invisible to the code | [[linea-iono-bellibolt-invisible-al-codigo]] | Should be *subsumed by C1* — if C1 works, this arrives ranked, with its text, alongside everything else of its shape | Do not start it by hand before C1 has run |

**The default of Q3 is B1, B2, B3**: one with a written method, one that is the
largest hole, one with a fixture and a modelled sibling to copy.

---

## 5. Track M — the measurement backlog

Launched by `utils/noche-2026-08-12.sh` (generated at execution time from the
answers to §0 — sizes below assume the Q4 default). Up to `JOBS` concurrent. **No
block may stop the night**: a failure leaves its log and the next one starts.

| id | Block | Size | What it answers |
|---|---|---|---|
| **M0** | Rule census sweep, `utils/rule_census.py --corpus --games 400` | minutes | The exposure of every named rule on today's HEAD, in one table — including the four laws with a possibly-missing consumer (§1, last two rows) |
| **M1** | Weighted matchup matrix over `deck/real_opponents/`, 400 games/matchup, bot declines first | ~2 h | **The post-12-August baseline.** Four behaviour changes landed today and none of them has a weighted number |
| **M2** | Differential oracle, all 89 lists, 300 games each | ~2–3 h | The oracle has not run wide since today's four fixes |
| **M3** | Invariant monitor, 30 000 games, dumped | ~2 h | Including the flag mirrors that went to zero on 11 August — do they stay there |
| **M4** | Permutation probe, 4 000 games, dumped | ~1 h | Feeds B7; order-dependent decisions, triageable |
| **M5** | Hypothesis soak, 200 000 examples | ~1–2 h | |
| **M6** | Threshold sensitivity sweep (±1 on numeric literals in rule predicates) | ~1 h | The `hand ≤ 3` class. Report only |
| **M7** | Mutation gate | ~1 h | **Runs alone, after every other M block has finished** — it swaps the tree |

---

## 6. The criteria, written before the numbers exist

Copied here so the executor does not have to go looking, and so no number gets
interpreted after the fact.

1. **A detector that fails either half does not print.** Its stage is marked
   INVALID and quarantined in the report. An unvalidated number is not a smaller
   finding; it is not a finding.
2. **Neutral reverts**, except where the change removes an internal contradiction
   or an illegal value ([[politica-neutro-se-revierte-salvo-valor-ilegal]]). When
   the exception applies, the neutrality goes **in the commit message**.
3. **Frequency before winrate.** Below 0.5 % exposure, no games are played: the
   corpus and the reasoning are the whole argument
   ([[el-cap-fuera-de-su-matchup-se-precia-por-la-mano-rival]]).
4. **Census reports rank, they do not rule.** A rule with zero fires is not
   automatically dead — several here are written for one board.
5. **Run a deterministic instrument twice before believing it**
   ([[un-detector-que-identifica-por-id-fusiona-lo-que-python-recicla]]).
6. **Compare against the finest reading the agent has**, not against a coarse
   proxy ([[un-detector-compara-contra-la-lectura-mas-fina-que-el-agente-tenga]]) —
   half of one night's findings were the detector's own coarseness.

---

## 7. Order of execution

    0.  Ask §0. Wait. Then nothing else stops.
    1.  Q1's baseline: commit (or branch), then `git archive` to
        log/noche-2026-08-12/tree/
    2.  Launch track M from the export (M0 first — it is minutes and it feeds the
        morning), M7 excluded and held back
    3.  Track C in order: C1, C2, C3, C4, then C5/C6 if the clock allows.
        Each: build → both halves → run → commit the instrument → write the
        memory. A detector that fails its halves is committed anyway, marked, and
        its output is not read.
    4.  Track B per Q3, one at a time, each on its own branch with its criterion
        written before its number.
    5.  When every M block has finished: M7 alone.
    6.  The morning report.

**Stop conditions.** The night stops early only if: the suite goes red on `main`
and is not green again within one fix; or an M block corrupts the export. Neither
has happened in three nights.

---

## 8. What the morning report must contain

`utils/informe_noche.py` over `log/noche-2026-08-12/`, plus, written by hand:

* **The C1 table**, top 20 by rank — the answer to "what is the agent not even
  able to see". This is the piece most likely to change what the next week does.
* **The C2 table** — every place where a tier is outranking a number, with
  frequency and gap. Two of tonight's rows were today's bugs; the question is how
  many rows there are.
* Per detector: both halves, pass/fail, and the calibration commit used.
* Per B item: the criterion as written *before*, the number, and the decision —
  including the reverts, with their reason.
* **The one number that matters for the day's four fixes**: M1's weighted matrix
  against the 11 August baseline.
* The new pending list, replacing §4 — and, if C1 lands, B10 should be gone from
  it, absorbed.

---

## 9. The premise of this plan, stated plainly so the morning can judge it

Tonight spends most of its constructive budget on **instruments rather than on
play**, in a project whose agent has ten named pending improvements waiting. The
argument for that is one line of §1: **thirteen of thirteen defects today were
found by a human reading a lost game**, and that channel does not scale. If the
morning finds that C1–C4 produced worklists nobody can act on, the premise was
wrong and the next night goes back to track B — and that judgement should be made
on the tables of §8, not on how the night felt.
