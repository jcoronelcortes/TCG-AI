# The instruments

[← Documentation index](README.md)

This project has no machine learning and no search tree. Every rule in it was
written by a person, which means the only thing separating a good rule from a
plausible one is **measurement** — and by August 2026 the measuring apparatus had
become large enough to need a page of its own.

[Improving the agent](improving-the-agent.md) is the workflow: find, reproduce,
pin, change, measure, keep or revert. This page is about the tools that produce
the numbers in step 5, the discipline that decides whether a number is allowed
to be believed, and the order to reach for them in. Individual invocations are
in [Tools](tools.md).

---

## The rule that governs all of them

> **A detector does not get to report a number until it has proved, in the same
> run, that it can catch a planted defect and stay quiet without one.**

This is not a style preference. Four detectors in this repository have reported
their own bugs as defects of the agent:

- the **differential oracle** did it over three separate rounds — 89% of its
  phantom knockouts turned out to be gusts the turn never played, and half of
  the residue under that was our own bench being over-counted;
- the **invariant monitor** did it twice in one morning;
- the **mutation gate** did it twice more, for two unrelated causes.

In every case the numbers looked exactly like findings. So each detector carries
a **self-test with two halves** — sensitivity (plant a defect, see it caught) and
specificity (remove the defect, see the silence) — and refuses to print if either
half fails. `utils/nightly.py` marks such a stage INVALID and quarantines its
output in the report rather than summarising it: an unvalidated number is not a
smaller finding, it is not a finding at all.

Two corollaries the same period produced:

- **Run a deterministic instrument two or three times before believing it.** Two
  audits disagreed about how many discard menus the corpus contains. The capture
  keyed menus by `id(select)` without holding a reference, and CPython reuses an
  address the moment the object at it is collected, so distinct menus merged
  onto one key. The same corpus reported 90, then 98. It is 118, and every rate
  published before the fix had the wrong denominator.
- **A gate must be able to see its own change.** Before the two-arm gates
  exported both trees, both arms shared every module under `ptcg/`, so a change
  to any rule measured exactly zero — and in this project neutral orders a
  revert. It is now **R7** in the architecture lint: a `utils/gate_*.py` that
  loads two arms must define **and call** `provenance()`.

---

## The four questions, and what answers each

### 1. "Does this situation even happen?" — the censuses

The cheapest question, and the one most often skipped. Several rules here were
written, measured neutral and reverted for a population under a tenth of a per
cent of decisions. A census is minutes; 200 games is not.

| Tool | Counts |
| --- | --- |
| `rule_census.py` | Every named scoring rule: chain walked / evaluated / fired / decided. Sorts them into four bands of deadness. |
| `turn_waste_census.py` | Resources that were legally playable and were declined, per turn and per plan mode. |
| `promoted_reply_census.py` | The nested populations of one candidate rule, from "the situation happens" down to "and we had a choice about it". |
| `promoted_relay_census.py` | The same shape, for the body promoted after a knockout. |
| `relay_saves_the_game_census.py` | The retreat that cashes the last prize with a body that outlasts the promotion: how often the rule fires, and whether it moves anything. Carries a `--control` arm that measures the noise floor of asking the agent twice about the same board. |
| `match_point_reply_census.py` | The shelf `op_wins_after_ko` sits on, split three ways, **and whether the prediction comes true**: of the boards where we attacked anyway, how many actually ended on their reply. The second half is the one that matters — it prices the reading before a rule is written on it. |
| `healing_census.py` | How much of the damage we deal gets healed back before it becomes a prize. |
| `fodder_ladder_audit.py` | Discard menus where a Basic Grass outranked an evolution the agent itself calls orphaned. |
| `duplicate_protection_audit.py` | Menus where two copies of a card came out with the same "this is our only out" score. |
| `blind_window_census.py` | Per guard, how much of the turn it **cannot see**. A rule opening with `not state.supporterPlayed` arbitrates until the slot is spent and is unreachable afterwards; a guard near 100% blind is dead code that reads like a live rule. |
| `tier_inversion_census.py` | Every menu where an **order** beat a **number** — the one line in the project where a category decides before a value. Load-bearing and, on the day it was written, the source of two separate defects. |

A zero from a census is a statement about the **workload**, not only about the
rule. The rule census at three loads makes that visible: 120 rules never fire
over the frozen corpus alone, 38 over the corpus plus 2 400 games. What survives
the widest load is what deserves reading.

### 2. "Is the table still true?" — the audits

A table of card IDs rots silently: the cards it describes are outside the
repository, and nothing goes red when one of them is wrong. Three siblings diff
a table against the printed card text in **both** directions — an ID in the table
whose card does not say that thing, and a card that says it and is in no table.

| Tool | Audits |
| --- | --- |
| `op_scaling_census.py` | `ptcg/cards/op_scaling.py` — the opposing attacks whose damage counts the board. |
| `op_buff_census.py` | The abilities and tools that add a flat amount to an opposing attack. |
| `op_immunity_census.py` | `EX_IMMUNE_IDS`, `ABILITY_IMMUNE_IDS`, `FULL_HP_SURVIVE_IDS`. |
| `card_text_census.py` | The fourth sibling, and it asks what the other three cannot: of every card that can be put on the table against us, which ones does the code **not mention at all**? The three above each check one table against the cards; this one finds the cards no table has heard of. |

They pay for themselves. The immunity audit found `EX_IMMUNE_IDS` carrying a
Crustle whose ability is Sturdy — the ex-immune wall is a different card that
shares nothing but a name — so every attack from our ex read as zero against a
150 HP body that falls in one hit. Exposure was 0 of 87 real lists, so nothing
was bleeding; a wall that is not there is still walked around for free.

An exclusion has to carry its argument in the table's `_EXCLUDED`, and a test
enforces that. `--check` makes each one exit non-zero, which is how the suite
runs them as gates.

### 3. "Does the agent believe something the engine disagrees with?" — the differential detectors

These need no expected answer. They compare two things the code produces and
report where they disagree.

| Tool | Compares |
| --- | --- |
| `differential_oracle.py` | What the agent's attack plan *predicted* against what the engine actually resolved. A predicted knockout that did not happen is a `PHANTOM_KO`. |
| `invariant_monitor.py` | Properties that must always hold across a game: documented caps, the card-tracking belief, and whether a raised flag still has its premise. |
| `permutation_probe.py` | The agent against itself on a shuffled menu, comparing **plays** rather than indexes. Any difference is a decision the rules did not make. |
| `mutation_probe.py` | The suite against a rewritten expression. A survivor is a line no test is watching. |
| `shadow.py` | Two versions of the agent on the same observation. Any different choice is a flip. |

Two readings of the oracle that keep recurring, both written into the tool:

- **judge the body the plan was about**, not the one that took the hit. Most of
  its early findings were gusts the turn never played;
- **the oracle is a mirror.** It watches whichever agent it is attached to, so
  when it is pointed at a self-play run, half of its residue describes our agent
  failing to pilot the *opponent's* deck. The worst deck in the corpus turned
  out to be exactly that.

The invariant monitor's `STALE_FLAG` check needs a **premise** written next to
the flag, and sixteen boolean flags currently have none — which is how "our
agent never goes first" stayed invisible for months. A flag with no premise is
not watched.

### 4. "Does it win more games?" — self-play and the matrix

The only question the ones above cannot answer, and the most expensive.
`selfplay.py`, `matchup_matrix.py`, and the two-arm `gate_*.py` scripts written
per candidate rule. What to know before trusting one of their numbers is in
[Improving the agent](improving-the-agent.md); the bound that applies to all of
them is in [Matchups](matchups.md) — **the reference bot takes the first turn,
so nearly every figure on record describes the going-second half of the game.**

---

## The two-arm gate

A `utils/gate_*.py` is written per candidate rule, not per project. It exports
two trees, loads an agent from each, and plays the same matchups with both, so
the only difference between the arms is the change under test.

Three things a new one must do, all three learned from a gate that reported a
false neutral:

1. **export both trees**, package included — a change under `ptcg/` that both
   arms import from the working tree comes out of both arms identically;
2. **define and call `provenance()`**, which prints what each arm actually is.
   R7 in the architecture lint checks this statically;
3. **state its own control**: an opponent the rule cannot possibly fire against,
   run in the same session. A delta that does not clear the control's noise
   floor is not a delta.

## The nightly

`utils/nightly.py` runs the whole thing as one script, in the order the
dependencies want:

```text
suite -> lint -> corpus -> coverage -> mutation
      -> differential oracle -> invariant monitor
      -> permutation -> hypothesis soak -> matchup matrix
```

The gates come first because everything after them is only worth reading on a
green tree: a night built on a red baseline attributes its own damage to the
wrong stage.

```bash
python utils/nightly.py --quick             # a few minutes: is the pipeline itself working
python utils/nightly.py                     # ~1 hour: the detectors get enough games to mean something
python utils/nightly.py --full --since origin/main   # hours, including the matchup matrix
```

It writes `log/nightly_<timestamp>/REPORT.md` plus one log per stage. Nothing it
runs writes to `main.py` or `ptcg/` — except the mutation stage, which rewrites
the file it is mutating for the length of one test run and restores it on exit,
on exception and on a kill. That is why it is the one stage that must not run
while anything else is reading the tree.

A session run this way gets written up afterwards, in `docs/history/`. Those
write-ups are part of the method, not a diary: they record the reverts as
carefully as the ships, because a rule that was tried, measured neutral and
removed is worth as much as one that shipped — it stops the next person from
spending the same week.

---

Next: [Tools](tools.md) · [Improving the agent](improving-the-agent.md) · [Testing](testing.md)
