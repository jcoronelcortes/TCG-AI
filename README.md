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
python -m pytest -q                             # run the test suite
python utils/selfplay.py --games 100             # play 100 games locally
python utils/package_project.py                 # build submission.tar.gz
```

Requires Python 3.10+. **The agent itself has no third-party dependencies**, and
that is deliberate: it runs in a competition container where nothing gets
installed.

## Where things are

| Path | What it is |
| --- | --- |
| `main.py` | The agent's entry point, board setup and opponent identification. |
| `ptcg/` | The agent's package: card data, calculators, state, per-card decisions, turn phases. |
| `cg/` | The competition simulator, vendored (includes the native engine). |
| `deck.csv` | Our 60-card deck. |
| `deck/`, `competitor_decks/`, `dataset/` | Opponent lists, leaderboard decks and card reference data. |
| `tests/` | The safety nets: behaviour tests, real fixtures, invariants, golden corpus. |
| `utils/` | Command-line tools: play, measure, autopsy, package. |
| `docs/` | The documentation. |

## Documentation

**Start at [docs/README.md](docs/README.md).**

- [How the agent thinks](docs/how-the-agent-thinks.md) — the decision loop in one page
- [Our deck and its engines](docs/deck-and-engines.md) — the cards and combos everything is built around
- [Strategy](docs/strategy.md) · [Matchups](docs/matchups.md) — what the agent knows about playing well
- [Code map](docs/code-map.md) — where everything lives
- [Improving the agent](docs/improving-the-agent.md) — how a change is measured before it is kept
- [Tools](docs/tools.md) · [Testing](docs/testing.md) · [Debugging a decision](docs/debugging.md)

## Current results

Against the 93 real leaderboard decks, weighted by how often each appears:
**93.3% expected ladder winrate**, +3.9 prizes per game, zero forfeits across
37,200 games. The weakest matchup is the Crustle wall archetype. Details and
method in [Matchups](docs/matchups.md).

## Contributing and licence

[CONTRIBUTING.md](CONTRIBUTING.md) explains the four gates a change has to pass
-- two of them run in CI on every push and pull request -- and what to look at
when reviewing one. The code is MIT licensed ([LICENSE](LICENSE)); the
vendored simulator under `cg/` belongs to the competition and keeps its own
terms.
