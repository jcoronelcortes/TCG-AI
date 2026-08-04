# Improving the agent

[← Documentation index](README.md)

Adding a strategy rule is easy. Knowing whether it helped is the hard part, and
it is what most of the tooling in this repository exists for. This page is the
workflow.

## The loop

```
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
| Self-play | `python utils/selfplay.py --partidas 200 --base HEAD~1` | Does it win more games than the previous version. |
| Matchup matrix | `python utils/matchup_matrix.py --partidas 400 --pesos --base <ref>` | Whether a gain in one matchup is paid for by a loss in another. |
| Equivalence (refactors only) | `python utils/shadow.py <before.py> <after.py>` | A refactor that was supposed to change nothing but did. |

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

## 6. Keep or revert

Write down what you measured, including the reverts. A rule that was tried,
measured neutral and removed is worth as much as one that shipped — it stops the
next person from spending the same week.

---

Next: [Tools](tools.md) · [Testing](testing.md) · [Debugging a decision](debugging.md)
