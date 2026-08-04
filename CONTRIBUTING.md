# Contributing

This project is a heuristic agent: every rule in it was written by a person,
measured against real games, and kept only because it won more of them. That
history is what the process below protects. A change that makes the code nicer
but the agent worse is not an improvement here.

## The gates

Four checks. They are cheap, they run locally, and a change is not ready until
all four are green.

```bash
python -m pytest -q                      # 986 tests, ~7 s
python tests/golden_corpus.py            # replays every record, ~0.5 s
python utils/lint_architecture.py        # R1-R4, the Kaggle-safety rules
python -m pytest -q tests/test_submission.py   # loads main.py the way the container does
```

What each one is actually for:

**The suite** covers behaviour. Most of its files are named after the mistake
they prevent (`test_do_not_retreat_the_healthy_for_the_wounded_wall.py`), and
each one carries the record of the game where that mistake was made. Read the
docstring before changing a test: it usually explains why the obvious fix was
wrong.

**The golden corpus** replays every stored game and compares the decision the
agent takes at every step against a snapshot. A rename or a refactor must show
`no changes`. A rule change usually flips a handful of decisions, and each flip
has to be looked at: *was that flip intended?* That question is the review.

**The architecture lint** enforces the four rules that keep the agent loadable
on Kaggle -- no importing a mutable by value, no state inside the pure
subpackages, nothing bound after `def agent`, no lazy import of our own
package. They exist because each one broke a submission once.

**The submission smoke test** packages the tree and loads it with a verbatim
copy of Kaggle's loader, which uses `exec`, not `import`. Three real failure
modes live here; the file explains them.

## Before you change a rule

Behaviour changes need evidence, not argument. The heavier gates are in
[docs/improving-the-agent.md](docs/improving-the-agent.md); the short version:

```bash
python utils/selfplay.py --games 200 --base HEAD~1     # does it win more games
python utils/matchup_matrix.py --games 400 --weights   # at whose expense
```

Two things worth knowing before you trust a number: at 200 games the
per-matchup noise reaches ±6.5 points, and once the winrate saturates the
prize differential is the metric with resolution left.

If a change measures NEUTRAL, revert it. The project has a written history of
plausible ideas that measured flat or negative, and keeping them would have
made the code harder to reason about for nothing.

## Conventions

- **Names**: [docs/naming.md](docs/naming.md) holds the vocabulary. Reach for
  the word that is already in use rather than a synonym.
- **Comments explain WHY**, and cite the game they came from. The code says
  what it does; the comment says which loss taught us to do it.
- **The agent has no third-party dependencies.** It runs in a container where
  nothing gets installed. `requirements-dev.txt` is for the tests only.
- **Documentation is in English**, describes purpose over mechanics, and never
  cites line numbers -- they rot on the first edit.

## Reviewing someone else's change

Ask for the four gates. Then ask the two questions that the gates cannot:

1. **If the golden corpus flipped decisions, is each flip an improvement?**
   The diff names the record and the step; open it.
2. **Does a new rule state its evidence?** A rule with no game behind it is a
   guess, and guesses are what the measurement discipline exists to catch.

For a change that only moves names around, there is a stronger check than
reading the diff: `python utils/rename_code.py verify <map.tsv>` proves that
nothing but the mapped names moved, by applying the map to the old AST and
comparing. Renames in this repository are expected to come with their map.
