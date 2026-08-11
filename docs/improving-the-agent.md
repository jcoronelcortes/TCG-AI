# Improving the agent

[← Documentation index](README.md)

Adding a strategy rule is easy. Knowing whether it helped is the hard part, and
it is what most of the tooling in this repository exists for. This page is the
workflow.

## The loop

```text
1. FIND     a weakness that costs real games
2. REPRODUCE the exact decision that lost them
3. PIN       it with a test that fails today
4. CHANGE    the rule
5. MEASURE   decisions changed, then games won
6. KEEP or REVERT
```

## 1. Find a weakness

| Question | Tool |
| --- | --- |
| Which matchup do we actually lose? | `utils/matchup_matrix.py` — winrate and prize differential against every real leaderboard deck. |
| What went wrong in the games we lost? | `utils/autopsy.py` — replays losses and runs detectors over them: a lethal attack that was available and not taken, a turn ended with a full hand and no damage. |
| Is a rule for one matchup breaking another? | `utils/collision_radar.py` — measures how often we resolve the *same* canonical situation across different opponents. A resolution rate that collapses for one deck and not the others is a collision. |
| Was there a better line this turn? | `utils/turn_explorer.py` — enumerates every legal sequence of our own actions for a turn and compares the best one with what the agent chose. |
| Why do we stall against the wall? | `utils/wall_probe.py` — per-turn probe of the immune-wall matchup; dumps the turns that ended dry so they can be replayed. |
| Is there anything to write a rule *about*? | `utils/turn_waste_census.py` — counts, per turn and per plan mode, the resources that were legally playable and were declined: the turn's attachment, the Supporter slot, an evolution, a body for the bench. |
| Which rules never fire at all? | `utils/rule_census.py` — chain walked / evaluated / fired / decided, per named rule, sorted into four bands of deadness. A rule that is dead by *ordering* is a different bug from one dead by *condition*. |
| Does the agent believe something the engine disagrees with? | `utils/differential_oracle.py` — the attack plan's prediction against what actually resolved. `utils/invariant_monitor.py` — a promise still standing while its premise is dead. |
| Is a table of card IDs still true? | The census family: `op_scaling_census.py`, `op_buff_census.py`, `op_immunity_census.py`. They diff a table against the printed card text in both directions. |

All of these are catalogued in [Tools](tools.md), and the discipline that governs
them — **no detector reports a number until it has proved in the same run that it
can catch a planted defect and stay quiet without one** — is in
[The instruments](instruments.md). Read that before trusting a finding from any
of them.

**The waste axis is measured out.** The census above was run over 250 games and
found the agent is *not* leaving resources unspent: the turn's energy attachment
goes unused on 1.3% of DEVELOP turns, the Supporter slot is lost on a turn that
ends without attacking once in a thousand, and 90% of the declined benchings
happen with a bench of two or more already. Three rules were written against that
axis before it was measured; all three came back neutral or negative. What is
left to gain is not in what the agent fails to *spend* — it is in *which* of
several legal, scored plays it picks, and that is arbitrated by the golden corpus
and the records, not by a volume census.

**Aggregate before you conclude.** The per-deck table names the single worst
list; grouping by archetype often names a different culprit. That is exactly how
the current backlog got redirected from Marnie to Crustle
([Matchups](matchups.md)).

## 2. Reproduce the decision

A weakness you cannot reproduce is a story, not a finding. See
[Debugging a decision](debugging.md) for the mechanics: replay a recorded game,
split it per turn, or build the exact board synthetically.

## 3. Pin it with a test

Turn the reproduction into a test that fails **before** the change. Real
observations go into `tests/fixtures/`; boards that never occurred in a real
game are built with the scenario builder. A test that cannot fail proves
nothing — validate the new test by injecting the bug and watching it go red.

## 4. Change the rule

Rules live where the decision lives: per-card modules under `ptcg/decision/`,
option branches under `ptcg/turn/options/`. See the [Code map](code-map.md).

Two placement rules that keep costing time when ignored:

- **Caps and ceilings go in the wrapper, not at the end of the function.** A
  ceiling applied after everything else silently overrides the rules above it.
- **A veto is not a preference.** If the option must never be chosen, veto it;
  do not merely score it low and hope nothing outbids it.

## 5. Measure

Run the gates in this order — cheapest first.

| Gate | Command | What it catches |
| --- | --- | --- |
| Unit suite | `python -m pytest -q` | Broken behaviour that someone already pinned. |
| Golden corpus | `python tests/golden_corpus.py` | **Which historical decisions your change flipped**, with an explicit diff. |
| Mutation of your own lines | `python utils/gate_mutation.py --changed HEAD~1` | Whether the test you just wrote watches the code you just wrote. |
| Self-play | `python utils/selfplay.py --games 200 --base HEAD~1` | Does it win more games than the previous version. |
| A two-arm gate for the rule | `python utils/gate_<your_rule>.py` | The same, with the change as the *only* difference between the arms — and a control the rule cannot fire against. |
| Matchup matrix | `python utils/matchup_matrix.py --games 400 --weights --base <ref>` | Whether a gain in one matchup is paid for by a loss in another. |
| Equivalence (refactors only) | `python utils/shadow.py <before.py> <after.py>` | A refactor that was supposed to change nothing but did. |

Or `python utils/nightly.py --quick`, which runs the reproducible ones in the
order the dependencies want and writes a report.

### The measurement rules that were learned the hard way

- **First measure whether the decision changed at all.** If the agent picks the
  same options as before, no winrate result is meaningful — you measured noise.
- **Neutral gets reverted.** A change that does not move the needle is removed,
  unless it corrects a value that was demonstrably *wrong* (an illegal cost, a
  misread HP). Neutral-but-correct is kept; neutral-and-speculative is not.
- **Sample size decides what you can see.** At 200 games a matchup delta swings
  several points on noise alone. Only large, consistent deltas are signal.
- **The opponent must be able to execute the mechanism you are testing.** If the
  generic bot cannot pilot the deck — or never uses the ability your rule is
  meant to counter — every result comes back neutral by construction. This has
  happened, and it invalidated a whole batch of experiments.
- **Winrate saturates; prize differential does not.** Above ~94% against the
  generic bot, use the prize differential to tell changes apart.
- **The weighted ladder figure cannot see a hard-matchup gain.** 36% of the
  field is a matchup we win 98% of, so a change worth eleven points against
  Crustle — 10% of the field — moves the weighted mean by a fraction. A gain can
  be real and the meta not contain it. Measure hard-matchup changes on the hard
  matchups, and say which you are reporting.
- **Every `--opponent` run is the going-second half of the game.** The reference
  bot takes the first turn unless told otherwise. See [Matchups](matchups.md).
- **Suspect the gate first.** A gate that shares modules between its arms
  reports exactly zero, and zero orders a revert here. Run the instrument twice
  before believing it, and check that its self-test ran.

## 6. Keep or revert

Write down what you measured, including the reverts. A rule that was tried,
measured neutral and removed is worth as much as one that shipped — it stops the
next person from spending the same week.

Where that goes: a page under `docs/history/` for a whole session, or the commit
message for a single change. Both are append-only — a write-up records what was
true on its date, and a later page says when a finding was closed or reversed.
The write-ups already there are indexed from the
[documentation index](README.md).

---

Next: [The instruments](instruments.md) · [Tools](tools.md) · [Testing](testing.md) · [Debugging a decision](debugging.md)
