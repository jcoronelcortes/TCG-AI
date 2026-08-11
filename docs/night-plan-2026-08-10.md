# The night of 9–10 August — the run the infrastructure was waiting for

**You are the one who runs it.** This document is the task, not a report.

Everything built on 8 and 9 August — the differential oracle, the invariant
monitor, the mutation gate, the coverage floors, the frozen corpus, the
properties — exists to produce **a list of findings**. That list has never once
been generated at full size. That is what tonight does.

---

## 0. Before launching — 2 minutes

```bash
cd "/Users/jcoronel/Desktop/VS Proyectos/TCG AI"
git status --short          # must be clean
git log --oneline -1        # note the hash: everything is measured against it
```

**If the tree is not clean, commit or stash first.** The mutation gate rewrites
files on disk while it runs and restores them when it finishes; with unsaved
changes on top, an interruption halfway is harder to undo.

A check that the pipeline is healthy (40 seconds, this is not the real run):

```bash
python utils/nightly.py --quick --since HEAD~1
```

It has to finish with **every stage OK or FINDINGS**, none FAILED and none
INVALID. If any comes back INVALID, stop: it means a detector cannot validate
itself, and **its numbers tonight would be worth nothing**.

---

## 1. The command for the night

```bash
python utils/nightly.py --full --since 69ad2e3 2>&1 | tee log/noche_10ago.txt
```

`69ad2e3` is the commit before the 9 August work, so the mutation gate watches
**everything added to the agent today**, which is what needs checking. To cover
only the latest change, use `--since HEAD~1`.

Leave the laptop plugged in and awake.

### How long it takes, measured rather than estimated

| Stage | Size under `--full` | Time |
|---|---|---:|
| Suite | 1 878 tests | 16 s |
| Lint | — | 1 s |
| Local golden corpus | 50 records | 2 s |
| **Coverage against the floors** | whole suite instrumented | **11 min** |
| **Mutation gate** | lines added since `69ad2e3` | **1 min** |
| **Differential oracle** | 19 decks × 2 000 games | **≈57 min** |
| Invariant monitor | 2 000 games | ≈4 min |
| Permutation probe | 2 000 games | ≈6 min |
| Property soak | 20 000 examples | ≈3 min |
| **Matchup matrix** | 98 real decks × 200 games | **≈12 min** |
| | | **≈1 h 35 min** |

The three figures in bold were measured directly today; the rest is a linear
extrapolation from real short runs (this simulator scales linearly: 0.1 s per
complete game).

**It is not a whole night, it is an hour and a half.** If you want the machine
to work longer, §5 says what to spend the remaining hours on — but do not extend
for the sake of extending: more games of the same thing buy precision, not
truth.

---

## 2. What to look at on waking, in this order

Everything lands in `log/nightly_<date>_<time>/`, with a `REPORT.md` and one log
per stage.

**First, the report's "Reading" section.** It is designed to be read before any
number:

1. **Are any stages INVALID?** Those are the ones that failed their own
   self-test. Their numbers are *replaced*, not shown, and rightly so: a
   detector that cannot demonstrate it still works and on top of that says "I
   found nothing" is the most misleading of the three outcomes. If there is one,
   that stage measured nothing tonight.
2. **Are any stages FAILED?** That is a broken tree, not a finding.
3. **Stages with FINDINGS** are the ones that found something. A non-zero exit
   code **because that is their report**, not because they are broken.

**Then the numbers, in order of what a defect there costs:**

| Log | What to look for | What we know today |
|---|---|---|
| `*_oracle_*.log` | `PHANTOM_KO`, `MISSED_KO`, `DAMAGE_DRIFT` | The residue was **2 351 over 165 199 attacks (1.42%)**. `festival_lead` was 39% of it and is **still unexplained** |
| `*_monitor.log` | `DECK_BELIEF`, `ILLEGAL_INDEX`, `END_EMPTY_BENCH`, `ENERGY_CAP` | All should come out **0**. `STALE_FLAG`/`STALE_READ` come out in the thousands and **are not defects** (documented in the file itself) |
| `*_mutation.log` | `SURVIVORS` | Today it stood at **zero**. Every new survivor is the sentence of a missing test |
| `*_permutation.log` | `order-dependent` | **0.6–0.7%** is the known level. A jump is the signal |
| `*_matrix.log` | the weakest matchup | The only stage that answers "does it win more?" |

---

## 3. If something breaks

**Skip it and carry on.** The script already does that by itself, except for the
suite and the lint, which stop the night on purpose: a run over a broken tree
attributes its own damage to the wrong stage.

If you have to kill the whole run, **Ctrl-C is safe**. The mutation gate traps
SIGINT/SIGTERM and restores whichever file it was mutating; that mechanism
exists because it once left an unparseable module on disk. After killing it,
check:

```bash
git status --short     # has to be clean again
```

---

## 4. The rule that is never skipped

**No finding from tonight becomes a change to the agent without being
measured.** Not because that is prudent in the abstract, but because in two days
**four** detectors in this repository reported their own bugs as defects of the
agent:

- the differential oracle, three rounds, 16 764 non-existent findings in v1;
- the monitor, twice in one morning (37 799 and 16 980);
- the mutation gate, twice more, from two different causes.

Every one of them with the "validate the harness" doctrine already written down.
The only thing that has worked is the **self-test that aborts the run**, which is
why `nightly.py` marks INVALID above the exit code.

And if a finding does turn out to be real: **measure the frequency before the
winrate**. Today's fix corrected an impossible belief on 25% of boards and moved
**2 decisions in 50 955** — at that frequency a winrate gate can only return
NEUTRAL by construction.

---

## 5. If you want the machine to work more hours

In order of what contributes most per hour, and none of the three is "more of
the same":

1. **The oracle against the REAL decks** (`deck/real_opponents/`, 98 lists)
   instead of the 19 synthetic ones. Today it has only been measured against the
   synthetic ones, and the unexplained residue lives exactly there:

   ```bash
   for f in deck/real_opponents/*.csv; do
     python utils/differential_oracle.py --games 500 --opponent "$f" \
       --dump log/oracle_reales/violations
   done 2>&1 | tee log/oracle_reales.log
   ```

2. **The monitor with a dump**, so every violation is left as a fixture ready to
   be pinned:

   ```bash
   python utils/invariant_monitor.py --games 20000 \
     --dump log/monitor_soak/violations 2>&1 | tee log/monitor_soak.log
   ```

3. **The property soak at scale** — it is the only tool that reaches boards no
   game has ever produced:

   ```bash
   PTCG_HYPOTHESIS_EXAMPLES=200000 python -m pytest -q \
     tests/test_invariants.py tests/test_properties_of_any_legal_board.py \
     2>&1 | tee log/hypothesis_soak.log
   ```

---

## 6. The success criterion

The night was worth it if the morning has **a list of reproducible findings and
detectors that still validate themselves**. It is not measured in lines changed
in `main.py`: that number should be **zero**, as it was last night.

And a run that finds nothing **is a result**, not a wasted night: it means the
oracle's residue dropped where it had to drop and the invariants hold. Write it
down exactly like that. The failure mode this project already knows by name is
*a number nobody read*.
