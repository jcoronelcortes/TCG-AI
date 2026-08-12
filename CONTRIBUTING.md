# Contributing

This project is a heuristic agent: every rule in it was written by a person,
measured against real games, and kept only because it won more of them. That
history is what the process below protects. A change that makes the code nicer
but the agent worse is not an improvement here.

## The gates

Four checks before you propose a change. Three of them now run in CI on every
push and pull request ([.github/workflows/gates.yml](.github/workflows/gates.yml))
— the suite, the architecture lint and the golden corpus. The fourth, self-play,
cannot: it takes minutes and answers a different question. All four are cheap,
and a change is not ready until all four are green.

```bash
python -m pytest -q                      # 2440 tests, ~23 s
python tests/golden_corpus.py            # replays the frozen games, ~0.5 s
python utils/lint_architecture.py        # R1-R11: Kaggle safety, the instruments, the scorers
python -m pytest -q tests/test_submission.py   # loads main.py the way the container does
```

CI runs two more jobs beyond those: a **coverage ratchet** that fails when a
module loses the watch it had (`utils/gate_coverage.py --check`), and a
**mutation gate** on pull requests that mutates only the lines the diff adds and
asks whether any test goes red (`utils/gate_mutation.py --changed <base>`). The
mutation job is `continue-on-error` on purpose — it reports before it blocks.

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

It runs in two places now, and they behave differently on purpose. The **local**
corpus reads `records/`, which is transient game data, so a replaced record
silently re-snapshots. The **frozen** corpus (`tests/corpus/`, 50 games kept as
only our own decisions, 0.85 MB gzipped) is committed, cannot self-heal, and is
therefore what CI and a reviewer actually see. Accepting a reviewed flip in the
frozen one is `python utils/freeze_corpus.py --snapshot-only` — never the bare
command, which would rebuild the bundle from whatever games happen to be in your
`records/` and quietly shrink the gate.

**The architecture lint** enforces eleven AST rules. R1–R5 keep the agent
loadable on Kaggle — no importing a mutable by name, no state inside the pure
subpackages, nothing bound after `def agent`, no lazy import of our own package,
no top-level name defined twice. R6–R8 watch the *instruments* instead, and each
one comes from a defect that shipped green in August 2026: a test may not read a
`records/` file without a skip guard, a two-arm `gate_*.py` must define **and
call** `provenance()`, and inside the DISCARD block the turn flags may only be
read through the horizon. R9–R10 watch the agent's own discipline — a per-option
scorer prices an option and does not write state, and a field of `TurnPlan` or
`AgentState` that nobody reads is a question the agent asked and then ignored.
R11 keeps the two apart: the seeded local engine the tools measure with may
never be reachable from `main.py` or `ptcg/`. Full list with the defect behind
each one in [docs/testing.md](docs/testing.md); see also
[docs/instruments.md](docs/instruments.md).

**The submission smoke test** packages the tree and loads it with a verbatim
copy of Kaggle's loader, which uses `exec`, not `import`. Three real failure
modes live here; the file explains them.

### Running them all at once

```bash
python utils/nightly.py --quick     # every gate and every detector, a few minutes
python utils/nightly.py             # ~1 hour: the detectors get enough games to mean something
python utils/nightly.py --full      # hours, including the matchup matrix
```

`utils/nightly.py` is the whole pipeline as one script, with the report written
to `log/nightly_<date>/REPORT.md`. It exists because a night that only its author
can relaunch is not infrastructure.

## Before you change a rule

Behaviour changes need evidence, not argument. The heavier gates are in
[docs/improving-the-agent.md](docs/improving-the-agent.md); the short version:

```bash
python utils/selfplay.py --games 200 --base HEAD~1     # does it win more games
python utils/matchup_matrix.py --games 400 --weights   # at whose expense
```

Three things worth knowing before you trust a number:

- at 200 games the per-matchup noise reaches ±6.5 points;
- once the winrate saturates, the **prize differential** is the metric with
  resolution left — the weighted ladder figure cannot move for a change that
  only helps the close matchups, because 31% of the field is a matchup we
  already win 97% of;
- every `--opponent` run measures the **going-second** half of the game. The
  reference bot takes the first turn unless you pass
  `OpponentBot(first_choice="second")`.

If a change measures NEUTRAL, revert it. The project has a written history of
plausible ideas that measured flat or negative, and keeping them would have
made the code harder to reason about for nothing.

**Before that, ask whether the behaviour happens at all.** A census is cheaper
than a game, and several rules in this repository were written, measured neutral
and reverted for a population that was under a tenth of a per cent of decisions.
`utils/rule_census.py`, `utils/turn_waste_census.py` and the audits listed in
[docs/instruments.md](docs/instruments.md) answer "is there anything here to
write a rule about" before anyone plays 200 games about it.

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

Ask for the four gates. Then ask the three questions that the gates cannot:

1. **If the golden corpus flipped decisions, is each flip an improvement?**
   The diff names the record and the step; open it.
2. **Does a new rule state its evidence?** A rule with no game behind it is a
   guess, and guesses are what the measurement discipline exists to catch.
3. **If the change comes with a number, did the instrument that produced it
   prove it can fail?** Four detectors in this repository have reported their
   own bugs as defects of the agent. A measurement from a tool that did not run
   its self-test in the same run is not a smaller finding — it is not a finding.

For a change that only moves names around, there is a stronger check than
reading the diff: `python utils/rename_code.py verify <map.tsv>` proves that
nothing but the mapped names moved, by applying the map to the old AST and
comparing. Renames in this repository are expected to come with their map.
