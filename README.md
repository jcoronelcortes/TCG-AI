# TCG-AI

An entry for the Kaggle competition **[The Pokémon Company — PTCG AI Battle
Challenge Simulation](https://www.kaggle.com/competitions/pokemon-tcg-ai-battle)**:
a **heuristic agent that plays Pokémon Trading Card Game** against other
people's agents inside the competition's simulator.

It receives the game state, scores every legal option, and plays the best one.
There is no machine learning: every rule was written by a human, measured
against real games, and kept only if it won more of them.

```python
from main import agent

selection = agent(observation)   # -> the indexes of the options to play
```

## What the competition asks for

The competition page is the authority on rules, timeline and scoring — this
page does not restate them, because a copy would rot. What matters for reading
this repository is the shape of the contract the agent has to satisfy, and that
is visible in the code:

- **One function.** A submission is Python that the competition runner loads
  with `exec` and calls for every decision, taking the LAST callable it finds.
  Ours is `agent(observation) -> list[int]`, and it is deliberately the last
  thing in [main.py](main.py). The loader is vendored verbatim in
  [tests/kaggle_loader.py](tests/kaggle_loader.py) so the smoke test can load
  the submission exactly the way the container does.
- **Menus, not moves.** Each observation carries the state plus the list of
  options that are legal right now. The agent returns indexes into that list,
  which is why every rule in here ends up as a score attached to an option.
- **A 60-card deck**, ours in [deck.csv](deck.csv), fixed for every game.
- **Agent against agent**, on a ladder. Games are played by the simulator that
  ships in [cg/](cg/) — the same one the competition runs, native library
  included, which is what makes the local self-play and matchup measurements
  worth anything.
- **A packaged submission**: `submission.tar.gz`, built by
  [utils/package_project.py](utils/package_project.py), containing the agent and
  the local packages it imports. Nothing gets installed in that container, so
  the agent depends on the standard library alone.

If you are here to read the agent rather than to run it, start with
[docs/how-the-agent-thinks.md](docs/how-the-agent-thinks.md).

## Quick start

```bash
python -m pip install -r requirements-dev.txt   # test runner only; the agent needs nothing
python -m pytest -q                             # run the test suite (~3 271 tests, ~30 s)
python tests/golden_corpus.py                   # replay the frozen games: which decisions moved
python utils/selfplay.py --games 100            # play 100 games locally
python utils/package_project.py                 # build submission.tar.gz
```

Requires Python 3.10+ (CI runs 3.10 and 3.12). **The agent itself has no
third-party dependencies**, and that is deliberate: it runs in a competition
container where nothing gets installed.

## Architecture

**[Diagrams: the three views of this repository →](images/architecture.md)**

Three ideas explain the shape of everything here.

**The agent is one function scoring a menu.** There is no game loop of our own
and no search tree in the shipped code: the simulator hands over the state plus
the options that are legal right now, and `agent()` returns indexes into that
list. So every strategic idea in the project ends up in the same form — a score
attached to an option — and the turn is decided in one pass: what the prize
count says the turn is FOR, then a score per option, then the final choice with
its ordering vetoes lifted or confirmed.

**`ptcg/` is split by what a module is allowed to touch, not by feature.**
Bottom to top: `cards/` is data, `calc/` reads the board and writes nothing,
`engine/` is the rule machinery, `state/` is the only thing that survives
between turns, `decision/` is one module per card that has real strategy, and
`turn/` is the phases of the turn itself. Dependencies point downward only, and
an architecture linter enforces it rather than trusting anyone to remember.

**What ships and what measures are kept apart on purpose.** The submission is
built by walking `main.py`'s imports, so a package the agent does not import
cannot reach the competition container — which is what lets the rollout
arbiter, the opponent prior and the seedable local engine live in this
repository without ever being in the thing we submit. The linter guards that
direction too (rules R11 and R12): the instrument never touches the thing being
measured.

## Where things are

| Path | What it is |
| --- | --- |
| `main.py` | The agent's entry point, board setup and opponent identification. |
| `ptcg/` | The agent's package: card data, calculators, state, per-card decisions, turn phases. |
| `cg/` | The competition simulator, vendored (includes the native engine). |
| `deck.csv` | Our 60-card deck. |
| `deck/`, `competitor_decks/`, `dataset/` | Opponent lists, leaderboard decks and card reference data. |
| `tests/` | The safety nets: behaviour tests, real fixtures, invariants, and the frozen corpus that ships with the repo. |
| `utils/` | Command-line tools: play, measure, audit, autopsy, package — plus `nightly.py`, which runs them as one pipeline. |
| `docs/` | The documentation. |
| `log/`, `log_analisys/`, `records/` | Local, throwaway game data. Git-ignored; the folders are kept, the content is not. |

## How this agent is developed

Every rule in here came from a game that was lost. The method is a single loop,
run one board at a time, and the discipline around it is the reason the rules
can be trusted:

```text
FIND  →  DESCRIBE  →  REPRODUCE  →  DIAGNOSE  →  DESIGN  →  PIN  →  MEASURE  →  DECIDE
```

Four things about it are worth knowing before reading any number in this
repository:

- **The discovery channel is a person reading a lost game.** Measured on 12
  August 2026: all thirteen defects fixed that day came from someone reading the
  JSON of a defeat. Zero came from the test suite, the frozen corpus, the
  oracles or self-play — those are **regression** nets, and they answer "did
  this change what we already knew", never "what is wrong that we do not know
  yet".
- **The winrate cannot be the referee.** Against the reference bot the agent
  wins about nineteen games in twenty however it spends a turn, so a rule that
  moves one decision in 3 685 is invisible at any affordable sample size. The
  verdict comes instead from three cheaper, sharper places: a **census** (does
  this board even happen?), the **corpus** (which historical decisions did it
  flip?), and the **rules oracle** (was it the better play, rolled out to the
  end?).
- **Neutral gets reverted** — unless a census proves the population is real and
  the oracle grades it positive over that board's own noise floor, in which case
  it ships **marked NEUTRAL** so a later session can revisit it instead of
  mistaking it for a measured win.
- **No detector reports a number until it has proved, in the same run, that it
  can catch a planted defect and stay quiet without one.** Five detectors in
  this repository have reported their own bugs as defects of the agent, and each
  time the output looked exactly like a finding.

➡️ **[The method](docs/the-method.md)** is the whole process written out: the
anatomy of a board write-up, how a decision is reproduced, a taxonomy of the
causes that recur, the finite menu of shapes a fix can take, the measurement
ladder cheapest-first, and what has to be rebuilt to run the same process on a
different deck.

## Documentation

**Start at [docs/README.md](docs/README.md).**

- [How the agent thinks](docs/how-the-agent-thinks.md) — the decision loop in one page
- [Our deck and its engines](docs/deck-and-engines.md) — the cards and combos everything is built around
- [Strategy](docs/strategy.md) · [Matchups](docs/matchups.md) — what the agent knows about playing well
- [Code map](docs/code-map.md) — where everything lives, in prose
- [Architecture diagrams](images/architecture.md) — the same map drawn: the layers, one decision at runtime, and how a change earns its place
- [Improving the agent](docs/improving-the-agent.md) — how a change is measured before it is kept
- [The method](docs/the-method.md) — the whole development process end to end, written to be reproduced on any deck
- [The instruments](docs/instruments.md) — the measuring tools, and the rule that keeps their numbers honest
- [Tools](docs/tools.md) · [Testing](docs/testing.md) · [Debugging a decision](docs/debugging.md)

## Contributing and licence

[CONTRIBUTING.md](CONTRIBUTING.md) explains the gates a change has to pass —
most of them run in CI on every push and pull request — and what to look at when
reviewing one. The code is MIT licensed ([LICENSE](LICENSE)); the vendored
simulator under `cg/` belongs to the competition and keeps its own terms.
