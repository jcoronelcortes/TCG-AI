# The night of 11 August 2026 — the instruments that would have seen it coming

**Status: written 10 August, ~23:00, on branch `ub-cost-does-not-eat-what-the-search-buys`, HEAD `87eb50a`, tree clean, suite 2161 green.**

This night has one axis, and it is not a rule. Of the ten things fixed on
10 August, **the two most expensive were instruments, not agent logic** — a gate
that could not see the package it was gating (`6c08b87`) and an oracle that
judged the wrong body (`51dc87d`, 89.2 % of its findings misattributed). Both
had been reporting numbers for days. Both numbers were believed.

So tonight builds the detectors that would have caught the day's bugs *as a
class*, runs the measurement backlog against the frozen tree while it does, and
touches the agent's behaviour as little as possible.

---

## 1. What the day taught, as classes rather than cases

| Class | Today's cases | The instrument that was missing |
|---|---|---|
| **A blind instrument reports "neutral"** | `6c08b87` both arms shared `ptcg/`; `51dc87d` the oracle read the wrong body | A gate must prove, in the same run, that its arms answer differently (`provenance()`). **No lint enforces this.** |
| **Dead code hides defects behind it** | `93a27eb`: `_protect_last_supporter` was unreachable on *every* Xerosic forced discard; reviving it exposed two pre-existing regressions | Nothing counts which named rules never fire. The rules engine already names every one of them and nobody asks. |
| **One menu, two callers, opposite horizons** | `93a27eb`: turn flags that were the *opponent's*; a play-context sentence pricing a discard at −1 | No lint on where turn-scoped flags may be read |
| **The two halves of one play contradict each other** | `5040fa9`: the fetch was priced 950 *because* we held the Meganium, and the cost discarded the Meganium | No test asserts `_ub_real_fodder` and the discard ladder agree |
| **A protection switches off when you hold MORE of the resource** | `ab1945a`: counter-stadium protected only at `hand_counts <= 1`, so two copies both went | No audit of the latch-once pattern across the catalogue |
| **A projection blind to the ABILITY** | `b5cf071`: energies counted, `Assemble Alloy` not | (pending — the same hole exists on our own side) |
| **A test pinning transient data** | `32a5537`: a census anchored to a `records/` filename | No lint forbids it |
| **Frequency before winrate** | censuses of 4/3580, 0/3580, 0/12431 | Already doctrine; not yet routine |

**The through-line:** four of the eight are the *same* failure — a measurement
that looks like a finding. That is what tonight instruments.

---

## 2. Two tracks, and why the tree is exported

Track **M** (measurement) is CPU and answers questions already written down.
Track **C** (construction) is me, building instruments and committing them.
They run at the same time, and they must not touch each other.

**The export is what makes that safe.** `git archive HEAD` into
`log/noche-2026-08-11/tree/` and every M block runs from *there*. Track C can
then edit and commit the working tree all night without a block loading a
half-written file. This is exactly the fix of `6c08b87` reused: `checkout_tree`
learned to export the whole tree because loading one file was never the agent.

`records/` is deliberately absent from the export (1 tracked file of 16 — it is
transient by design). No M block needs it: they all play games or replay the
frozen corpus, both of which are tracked.

**Hard rule:** while any M block is alive, no swap-based harness runs —
`utils/mutation_probe.py` above all. It *is* the tree for the length of a run,
and this project has lost work to that twice in one night.

---

## 3. Track M — the measurement backlog

Launched by `utils/noche-2026-08-11.sh`. Up to 6 concurrent processes of the 10
authorised, leaving headroom so no block is starved. No block can stop the
night; a failure leaves its log and the next one starts.

| id | block | size | what it answers |
|---|---|---|---|
| **M0** | Census sweep of the whole gate family | minutes | The exposure of every rule gated so far, on today's HEAD, in one table. Frequency before winrate, made routine. |
| **M1** | `gate_the_search_buys --games 15000` | ~1.5 h | The pending falsification of the cost/search rule |
| **M2** | the same, `--control`, same n | ~1.5 h | That run's own noise floor, **measured rather than assumed** |
| **M3** | Differential oracle, all 88 real lists, 300 games each | ~2–3 h | The oracle has **never** run wide since the target fix. Every residue number on record is inflated by up to 89 %. |
| **M4** | The five worst of M3 by rate, 1000 games, dumped | ~1 h | Fixtures for the morning |
| **M5** | Invariant monitor, 30 000 games, dumped | ~2 h | |
| **M6** | Permutation probe, 4 000 games, dumped | ~1 h | Order-dependent decisions, triageable |
| **M7** | Property soak, 200 000 hypothesis examples | ~1–2 h | |
| **M8** | Weighted matchup matrix over the real corpus | ~2 h | The one number that says how we do against the meta that exists — and the baseline the morning compares against |

**The decision criterion for M1/M2, written now, before the number exists:**

> If the affected group's delta does not clear the `--control` floor at the same
> n, the rule is neutral in winrate. **It is not reverted for that** — it is
> defended by the corpus and by the internal contradiction it removes
> (`_RULES_UB_BAYLEEF` scored the fetch 950 *because* the Meganium was in hand,
> and the cost threw the Meganium away). What gets done then is: write the
> neutral into the commit, and stop asking a winrate of a 0.11 % event.

That is the exception the policy allows. It does not extend to anything else
tonight.

---

## 4. Track C — the four instruments (the axis)

Each lands with **both halves or it does not land**: it must catch a planted
defect *and* stay quiet without one. A detector that cannot prove it still works
produces the result that misleads worst — "nothing found" meaning "nothing
looked".

### C1 · The rule census — `utils/rule_census.py` *(the one that matters)*

The instrument that would have found `_protect_last_supporter` in a single run.
Every scoring rule in this project already has a NAME and every chain already
resolves through one choke point, `_resolve_with_trace` in
`ptcg/engine/rules.py`. Nothing counts.

A hook there, behind `PTCG_RULE_CENSUS` (zero cost when unset), tallies per
named rule: **evaluated / fired / decided**. Run over the 3 580 frozen decisions
plus N self-play games against the real corpus, and report three bands:

* **NEVER EVALUATED** — the chain never reached it; something above always
  decides first. Dead by *ordering*.
* **EVALUATED, NEVER FIRED** — its condition never held on any real board. Dead
  by *condition*. ← this is `_protect_last_supporter`, and it is the band that
  hid two regressions behind it.
* **FIRED, NEVER DECIDED** — always outranked. Not dead, but not load-bearing.

**Honest caveat, and it goes in the output:** a rule with zero fires is not
automatically a bug — it can simply be rare, and several here are written for
one board. The report is a **worklist ranked by chain traffic**, never a verdict.

*Two halves:* plant `_FixedRule("__canary_dead__", lambda c: False, …)` into a hot
chain and require it reported; require the top rule of that same chain to appear
in no band.

### C2 · Three lint rules — `utils/lint_architecture.py`

The linter has R1–R5. Today produced three more, each from a bug that shipped:

* **R6** — a test that names a `records/` file must carry the skip guard.
  `records/` is transient and gets re-harvested; `32a5537` went red with nothing
  about the rule changing.
* **R7** — every `utils/gate_*.py` must define **and call** `provenance()` before
  it measures. The written rule of this project is that neutral means revert, so
  a gate that cannot see its own change is the expensive failure.
* **R8** — inside the `SelectContext.DISCARD` block, `supporterPlayed` and
  `energyAttached` may only be read through the horizon helper. On a forced
  discard those flags are the *opponent's*, and reading them raw is precisely
  `93a27eb`.

*Two halves each:* a synthetic offending file is flagged; the real tree is clean.
**If R8 needs a refactor larger than an hour to be enforceable, it lands
report-only and the refactor is written up, not attempted at 03:00.**

### C3 · The duplicate-protection audit — `utils/duplicate_protection_audit.py`

For every card the discard ladder prices: build the forced-discard hand with one
copy, then with two, and report every card whose **second copy receives the same
protection as the first**. The latch-once pattern (`_lillie_protected_once`,
`_evo_spare_seen`, and `ab1945a`'s counter-stadium) is the fix; this finds who
still lacks it.

*Expected first hit:* the corpus flip left standing on 10 August — a second
Meowth ex outranking a live Night Stretcher. That is Wave 2 of
`docs/discard-plan-2026-08.md`, and this audit is what turns it from one
anecdote into a list.

*Two halves:* `Forest_of_Vitality` (latched this morning) must **not** be
reported; a card whose protection is known un-latched must be.

### C4 · The contradiction test — `_ub_real_fodder` ↔ the ladder

Over the 3 580 frozen decisions, compare what `_ub_real_fodder` calls real fodder
with the band the ladder gives that same card, and report every disagreement.

This is the instrument the **pending "the cost eats the FUEL of what it buys"**
task needs *before* the ladder is touched: the memory already states the two
modules contradict each other there (a Basic Grass at 80, the top fodder, above a
Bayleef at 50 and a Meganium at 40 that cannot enter play for two turns — while
`_ub_real_fodder` counts both of those as fodder). Tonight measures the
disagreement across the whole corpus. **It does not fix it** — that is a ladder
change touching every forced discard, and it gets its own record, census and gate
on another day.

### C5 · *Only if* C1–C4 are committed green with ≥2 h left

The Xerosic cap outside its matchup (`60` fixed, reading nothing), by its own
written protocol: clone `gate_the_search_buys.py`, **census first**, and if
exposure is under ~0.5 % the honest report is the census and the rule is not
written at all. Criterion before the number, always.

---

## 5. The standing rules of the night

1. **No block can stop the night.** A run that aborts halfway attributes its own
   damage to the wrong stage.
2. **Both halves or it does not land.** Sensitivity *and* specificity, in the
   same run, for every detector.
3. **Track C changes no agent behaviour** except C5, and C5 only under its own
   census and pre-written criterion.
4. **No swap-based harness while M is alive.** Mutation included.
5. **Commit per finding**, suite green and linter clean before each one.
6. **A census with no exposure is reported as a census**, never dressed as a
   winrate.
7. **Neutral means revert** — except where the rule removes an internal
   contradiction rather than improving an estimate (§3), and that exception is
   claimed in writing *before* the number is read.
8. Long runs log to `log/`, never `/tmp`.

---

## 6. Timeline

| | |
|---|---|
| **T+0:00** | Preflight: suite green, linter clean, `git status` empty, export the tree, record HEAD in `RESUMEN.txt` |
| **T+0:15** | Launch track M. From here it is unattended. |
| **T+0:15 → T+3:00** | **C1**, the rule census, with both halves. Its first report is the night's main finding either way. |
| **T+3:00 → T+5:00** | **C2**, the three lint rules |
| **T+5:00 → T+7:00** | **C3**, the duplicate-protection audit |
| **T+7:00 → T+8:30** | **C4**, the contradiction test |
| **T+8:30 → T+10:00** | Triage of M's dumps as they land; **C5** only if everything above is committed and green |
| **T+10:00 → T+11:00** | `docs/history/night-2026-08-11.md`, memory updated, final `git status` and suite |

---

## 7. What is on the desk in the morning

* `log/noche-2026-08-11/RESUMEN.txt` — every block, its exit code, its duration.
* **The rule census** — the list of rules that never fire, ranked by traffic.
  Each entry is either a rule to delete or a bug like this morning's.
* Three new linter rules, each pinned by the bug it comes from.
* Two audits (duplicate protection, fodder↔ladder) as **worklists** for the
  ladder work, which is explicitly not done tonight.
* The oracle's residue re-measured wide, for the first time since the detector
  was fixed — every prior figure on record is inflated by up to 89 %.
* The cost/search delta closed at n=15 000 against its own control floor.

## 8. Explicitly out of scope

The ladder rewrite (the FUEL pending), the projection of "which body, when
benched, lifts my own damage", and Waves 2–5 of the discard plan. All three are
behaviour changes with their own blast radius; tonight builds the instruments
that make them measurable and stops there.
