# The turn we cannot resolve, we can play out — plan for 16 August 2026 onwards

[← Documentation index](README.md) · [the instruments](instruments.md) ·
[phase D](phase-d-2026-08-14.md) · [the engine source](engine-source-plan-2026-08-12.md)

**Status: written 15 August 2026, after reading the fortnight. Nothing in it has
run except §1.4, which is measured on this machine and is the reason the rest is
written.**

This page is not another rule. It is a proposal to change *where the next point
of winrate comes from*, because the channel that produced the last fifty findings
has run into its own floor, and the competition hands us an instrument we have
never used at play time.

---

## 1. What the fortnight actually bought, and what it says

### 1.1 The numbers

| | 1 August | 15 August |
|---|---|---|
| Corpus | 87 lists | **500 harvested → 133 admitted**, carrying meta weight |
| Weighted ladder winrate | 92.8 % | **95.4 % ±0.17** |
| Prize differential | +3.803 | **+4.172** |
| Measurement | unseeded, sequential, ±7 pp control drift | **seeded (CRN), 6×, delta 0.0000 on an identical arm** |
| Grading | heuristic vs heuristic | **+ the rules oracle** (rollouts to game end) |
| Code | — | 344 commits, ~48 k lines of rules, 128 named constants |

Three infrastructure phases (A parallel, B seeded, C weighted allocation) and the
rules oracle (D0–D2) are the fortnight's durable output. They cost days and they
made every later measurement cheaper or honest.

### 1.2 The finding the fortnight kept repeating, and it is about the method

Read the ledger rather than the commits:

- **The list beat the code.** Four cards were worth **+0.59 pp [+0.34, +0.84]**;
  the thirteen rule commits of the same day, **+0.36 pp [+0.10, +0.63]**.
- **Sixteen entries in the memory index carry a NEUTRO label.** The last ten
  merges ship on *census + rules oracle*, marked neutral in winrate, because the
  winrate cannot see them. That is the honest label and it is also a diagnosis:
  the shipping criterion has moved to instruments that grade **one board**.
- **13 of 13 findings came from a human reading a lost game.** The discovery
  channel is a person, and it is the only one that has ever produced a
  correction. The 15 August night ran the automated worklist for a whole block
  and it returned **1 board worth reading** out of 40 sterile turns and 4 missed
  lethals.
- **The archetype flag has now caused four documented defects** — `op_is_*_deck`
  read as *"is this knockout available"* when it only ever meant *"which body is
  worth searching for"*. Every new matchup rule adds a flag, and the flag is the
  repository's most reliable source of collateral damage.

None of that is a failure. It is what a heuristic scorer looks like when it is
finished: 95.4 % of the field, with the residue in two archetypes and inside
games the reference bot is too weak to arbitrate.

### 1.3 Where the residue actually is

| | Field share | Winrate | Prizes | Seat gap |
|---|---:|---:|---:|---:|
| **crustle_wall** | 8.23 % | 80.0 % | +2.32 | +6.4 pp |
| **ogerpon_verde** | 6.22 % | 85.4 % | +2.14 | +5.3 pp |
| everything else | — | 92–99 % | +2.7…+5.3 | ≈ +1 pp |

Those two rows account for **≈2.6 pp of the ≈4.6 pp** the field still takes off
us (8.23 % × 20 pp = 1.65, 6.22 % × 14.6 pp = 0.91) — **more than half of all the
winrate that is left anywhere.**
They are also the two rows where the seat is worth five or six points, i.e. where
the game is decided by tempo — which is the signature of a matchup that wants a
*plan*, not one more scored option.

### 1.4 ⭐ The instrument we have never used at play time — measured today

The observation the competition hands `agent()` carries a field called
**`search_begin_input`**, and `cg.api.search_begin` takes *that observation plus
our own prediction of the hidden cards* and returns a forward simulator. It is
not a private tool: the API asks the **agent** to supply `opponent_deck`,
`opponent_hand`, `opponent_prize`, `your_prize`. It is the competition's own
offer of a search at play time, and `utils/package_project.py` already ships
`cg/` with its native library inside `submission.tar.gz`, so the container has
everything it needs.

Three numbers, measured on 15 August on this machine:

| What | Measured |
|---|---|
| Budget per episode (`remainingOverageTime`, real ladder replay) | **600 s** |
| Budget a whole real 208-decision game actually spends | **4.72 s → 22.7 ms/decision** |
| **Unused** | **99.2 %** |
| One rollout to game end, **fully sampled** determinization, random policy | **5.2 ms** (88 steps) |
| Same with `main.agent` as the rollout policy | 43.0 ms (and see §5.2) |
| Matching their board against the 133 admitted lists | **7 ms**, and at turn 7 it named `festival_lead_5` at **100 % board coverage** |

`utils/search_oracle.py:determinize` **already supports the legitimate variant**:
`opponent_obs=None` samples their hand from the unseen multiset instead of
reading it, and the docstring calls that "the common case". The only reason the
module says *"can never be a play-time policy"* is the optional omniscient half —
which the play-time path simply does not use.

> At 5.2 ms, the spare 595 s of an episode is **≈114 000 rollouts per game**. A
> policy that searched 20 decisions per game, 3 options each, K=100, would spend
> **31 s** — 5 % of the pool.

**This is the largest unexploited asset in the project, and it is the one that
answers the question this plan was asked** ("play better against the different
deck types"): a rollout under a sampled opponent list *is* a matchup plan,
computed rather than written, and it needs no new `op_is_*_deck` flag to exist.

---

## 2. The proposal, in one paragraph

Keep the heuristic agent exactly as it is — it is 95.4 % and it is fast. Add
**two** things it does not have: an **opponent model that is a posterior over the
133 real lists** instead of a boolean flag, and a **bounded rollout arbiter**
that is consulted only on the handful of decisions per game where the score is
close *and* the stake is large. The heuristic keeps the play; the search breaks
the ties the scorer has no honest opinion about, and it breaks them with the
opponent's actual deck in the simulation.

Everything below is ordered so that **each phase is worth shipping on its own**
even if the next one never runs.

---

## 3. Phase S0 — the clock, the container and the permission · half a day

Nothing is built until these three are answered, because any of them can end the
plan.

| # | Question | How | Ends the plan if |
|---|---|---|---|
| S0.1 | Does the competition allow calling `search_begin` at play time? | The API takes *our* predictions and the field ships inside the observation, so the reading is that it is intended. **This is a call for the deck owner against the Kaggle rules, exactly like R1 of the engine-source plan** — it is not a call this page makes | The rules forbid it |
| S0.2 | Does `search_begin` work from **inside a live `agent()` call**, with a battle already open in the same process? | New test `tests/test_search_from_inside_the_agent.py`: run a self-play game; on one decision, open a search, roll it out, close it, and assert the **real** battle continues to the same result as a run without it | The search perturbs the live battle |
| S0.3 | What does a rollout cost **in the container**, not here? | A one-off submission that times 100 rollouts and prints the ms in a log the ladder returns. Until that number exists, every budget in this plan is a local estimate | It is >10× slower than local |

**Acceptance:** S0.2 green, S0.3 a number on record, S0.1 answered by the owner.
Budget rule written down and never exceeded: **the pool never goes below 120 s**,
whatever the search wants.

---

## 4. Phase S1 — the opponent is not a flag, it is a posterior over lists · 1–2 days

**Shippable alone, and it improves the agent even with no search behind it.**

`ptcg/opponent/prior.py`, and it is pure Python with no engine dependency:

```python
posterior(obs) -> [(list_name, weight), ...]   # normalised, meta-prior included
```

- every admitted list scored by **coverage of their visible board** (the
  `_their_deck_for` heuristic of `utils/oracle_*.py`, promoted out of `utils/`
  into the agent) times its **meta weight** from `pesos.csv`;
- a list that cannot host the board (a card of theirs it does not contain) gets
  zero, not a low score;
- the output feeds two consumers: the sampler of §5, and — separately — the
  existing archetype flags, which become `P(archetype) > θ` instead of
  "one card in the discard".

**The census that decides whether it is worth anything** —
`utils/opponent_prior_census.py`, run over the frozen corpus and 500 self-play
games where the true list is known:

| Question | Criterion |
|---|---|
| Top-1 accuracy by turn | must beat today's flags' *first correct turn*, per archetype |
| Archetype accuracy by turn | ≥ 90 % by the turn the current flag fires, and **earlier** |
| False positives | the four documented flag defects must not reproduce: measure how often the top-1 list is of an archetype we are not facing |

**Acceptance:** the posterior identifies the archetype at least one turn earlier
than the flag, at no worse precision. If it does not, S1 stops here and §5 uses
the flat "all lists that can host the board" set instead — which is still enough
for the sampler.

> Why this matters on its own: three of the fortnight's four archetype-flag
> defects were *the flag being right about the deck and wrong about the board*. A
> posterior does not fix that by itself, but it is the object a rule can ask
> **"how sure are we"** of, and that question does not exist today.

---

## 5. Phase S2 — the arbiter, offline first · 2–3 days

`ptcg/search/arbiter.py`. It never runs in a game during this phase; it is a
**shadow**.

### 5.1 What it is

```python
arbiter(obs, options, budget_s) -> index | None      # None = "no opinion"
```

- determinization: `search_oracle.determinize(obs, None, our_deck, their_deck)` —
  the sampled, play-time-legal path, already written and already guarded by the
  arithmetic that refuses to close;
- `their_deck` **resampled per rollout** from §4's posterior. That is the point:
  K rollouts average over *which deck they brought* as well as over the shuffle;
- K per option chosen from the budget, floor **K ≥ 50** — the measured noise floor
  says K=20 is unusable and K=50 is where it becomes readable;
- the verdict is the **prize margin first, the win flag second**, for the reason
  the matrix already reports both;
- returns `None` unless the best option clears the **second-best plus that
  board's own noise floor**, measured in the same call by a second batch of the
  same option. A preference that does not clear its floor is not a preference.

### 5.2 The rollout policy, and it is the one real design decision

`policy="agent"` (our own agent driving both seats) measured **43 ms** and won
**0 of 5** against the random policy's 6 of 20 on the same board. That is not
noise to be averaged away, it is a warning: **`main.agent` writes to the
`AGENT_STATE` global**, so using it inside a rollout corrupts the belief state of
the real game it was called from, and it also pilots the *opponent's* deck —
which memory already records as half the differential oracle's residue.

So the rollout policy is **not** `main.agent`. It is
`ptcg/search/fast_policy.py`: stateless, no globals, a few lines — take a lethal
if the menu shows one, otherwise attack, otherwise a weighted random legal
choice. Two requirements, both testable:

1. **it must be strictly better than random**, on the sensitivity board
   `search_oracle.self_test` already uses;
2. **it must touch no global.** `utils/lint_architecture.py` gets an **R12**:
   nothing under `ptcg/search/` may import `AGENT_STATE` or call `main.agent`.

### 5.3 How it is graded before it is ever played

The shadow run, `utils/shadow_arbiter.py`, over the frozen corpus and 500 games:

1. for every decision, record the heuristic's choice and the arbiter's;
2. keep the **disagreements** — that population is the whole finding;
3. grade each disagreement with the *omniscient* `search_oracle` at K ≥ 100 —
   the grader may read the opponent's hand precisely because it is not playing.

| Reading | What it means |
|---|---|
| Disagreements per game | the trigger's real workload (feeds §6) |
| Oracle margin, arbiter's choice − heuristic's | **the criterion**: it must be positive and clear the boards' own floor |
| Split by archetype | where the search is worth its clock, and it is the answer to "play better against deck type X" |

**Acceptance:** on the disagreement population, the arbiter's choice grades
positive over the worst floor, **and the crustle/ogerpon rows are not the ones
dragging it down**. A negative or floor-bound result here ends the plan at a cost
of three days and leaves S1 shipped — which is why S1 comes first.

---

## 6. Phase S3 — where to spend the clock · 1 day

Not every decision, and specifically **not the exact ties**: 240 of 279 of them
were measured to be genuine indifference, so paying rollouts for them buys
nothing. The trigger is written before it is measured:

```
fire when   (stake ≥ 1 prize on this decision or the next reply)
      and   (score gap between the top two options < GAP)
      and   (budget remaining > floor)
```

Candidate populations, all of which the repository can already count:
attack-or-end menus, gust targets, the promotion after a knockout, and the
charge order against a wall — the four families every one of the fortnight's
findings landed in.

`utils/census_the_arbiter_fires.py`: firings per game, ms per game, p99 ms per
decision, on lists that carry the matchup and on lists that cannot.

**Acceptance:** ≤ 40 s of the pool per game at p99, ≥ 10× margin to the 600 s,
and a **hard guard** that returns the heuristic choice the instant the pool drops
below the floor. Census before winrate, as always.

---

## 7. Phase S4 — the winrate, measured where it can be seen · 1 day

Two arms, seeded, `--jobs 6`, `--allocation peso`, **on the matchups the change
is for**:

```bash
python utils/gate_the_arbiter.py --only crustle_wall,ogerpon_verde \
    --control marnie_grimmsnarl --games 1000 --seeds 1000 --jobs 6
```

- the control is an archetype where the trigger fires least, run at the **same
  N** — a gate row without its control at the same N is not a reading;
- CRN collapses to zero only while both arms decide identically, and this one
  decides differently by construction, so n ≥ 1000 per matchup;
- report the weighted field figure too, **and expect it to be small**: a change
  worth points against 8 % of the field moves the mean by a fraction. The
  weighted number is reported to prove nothing broke, not to prove this worked.

**Acceptance to ship:** ≥ +2 pp on crustle_wall *or* ogerpon_verde, control
inside its own noise, zero forfeits in the whole run, and the fallback path
proved by a corpus replay with the arbiter disabled showing **0 flips** against
today's agent.

---

## 8. Phase S5 — safety, and it ships with S2, not after it

The competition punishes a crash and a timeout with a forfeit, and we currently
have **1 in 34 800**. Every one of these is a requirement, not a nicety:

1. **One `try/except Exception` around the entire arbiter**, returning the
   heuristic choice. A search that raises must be invisible.
2. **The budget is read from `remainingOverageTime` on every decision**, never
   assumed. Below the floor, the arbiter is off for the rest of the game.
3. **A wall-clock deadline inside the rollout loop**, checked per rollout, so a
   pathological board cannot overrun even with the budget available.
4. **A kill switch**: `ARBITER_ENABLED = False` restores today's agent exactly,
   and a corpus test asserts 0 flips in that state.
5. **`search_end()` / `search_release()` on every path**, including the raising
   one. States are pooled 128 at a time; leaking them is how a long game dies.
6. **R11 stays**: the local seeded engine never ships. The container runs the
   official `cg/` binaries, and the arbiter must work with the *unseeded* one —
   which it does, since it is an estimator over K anyway.

---

## 9. The second track, and it runs in parallel because it needs no decisions

**S6 — the discovery channel stops being one human.** 13 of 13 findings came from
a person reading a lost game; the automated worklist returned 1 board out of 44.
The shadow of §5.3 is a *better* worklist by construction: it is a ranked list of
**boards where the rules disagree with our scorer, with the prize margin
attached**. Point it at the losses of `crustle_wall` and `ogerpon_verde`
specifically and it becomes the thing the night plans have been asking for — the
morning gets boards ranked by prizes at stake, each with the alternative line
already played out.

**S7 — the 128 constants, tuned per archetype, offline.** Seeded CRN plus the
process pool make a coordinate descent affordable for the first time: perturb one
constant, replay the same seeds, keep the sign. Two guards, and without them this
is a machine for overfitting 133 lists: **hold out 20 % of the lists** and never
tune on them, and require any kept move to survive on the holdout. Run it only
after S2, because a tuner pointed at a scorer that is about to be arbitrated by
search is tuning the wrong object.

---

## 10. What this plan deliberately does not do

- **No more single-board rules.** The fortnight shipped ten of them and sixteen
  memories say NEUTRO. The bar stays where CONTRIBUTING put it, and this plan
  simply stops feeding that channel.
- **No new `op_is_*_deck` flag.** Four defects. The posterior of §4 replaces the
  question the flags were being asked badly.
- **`deck.csv` is not touched.** The list is the deck owner's call, even though
  §1.2 is the strongest evidence the project has produced that the fuel axis pays
  better than the code axis.
- **No machine learning.** Nothing here trains anything; the search is the
  engine's own rules rolled forward, which is the same instrument phase D
  already validated.
- **No search in the submission until S0.1 is answered by the owner.**

---

## 11. The order, and what each step costs if it fails

| Phase | Days | Ships alone? | If it fails |
|---|---|---|---|
| **S0** clock, container, permission | 0.5 | — | The plan ends here and costs half a day |
| **S1** the posterior over lists | 1–2 | **Yes** — better archetype detection | Falls back to the flat candidate set; §5 still runs |
| **S2** the arbiter, in shadow | 2–3 | No | Ends the plan with S1 shipped |
| **S3** the trigger and its census | 1 | No | Retune GAP; the census is cheap |
| **S4** the gate on the two hard matchups | 1 | — | NEUTRO reverts, per policy |
| **S5** safety | with S2 | — | Blocking: nothing ships without it |
| **S6** the shadow as a worklist | free | **Yes** | — |
| **S7** the tuner on a holdout | 2 | Yes | Overfits; the holdout is what says so |

Roughly **a week to a shipped answer**, with two of the phases worth keeping even
if the headline never lands.

---

## 12. The one sentence

Fifty rules were written by hand this fortnight against a bot that cannot tell
most of them apart, while **99.2 % of the thinking time the competition grants
us went unspent** and the simulator it hands us in every observation was never
called. The next point does not come from a fifty-first rule.

---

Next: [The instruments](instruments.md) · [Phase D](phase-d-2026-08-14.md) ·
[Improving the agent](improving-the-agent.md) · [Matchups](matchups.md)
