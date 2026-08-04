# TCG-AI

A **heuristic agent that plays Pokémon Trading Card Game** in the simulator of
the *PTCG AI Battle Challenge*.

It receives the game state, scores every legal option, and plays the best one.
There is no machine learning: every rule was written by a human, measured
against real games, and kept only if it won more of them.

```python
from main import agent

selection = agent(observation)   # -> the indexes of the options to play
```

## Quick start

```bash
python -m pip install -r requirements-dev.txt   # test runner only; the agent needs nothing
python -m pytest -q                             # run the test suite
python utils/selfplay.py --partidas 100         # play 100 games locally
python utils/empaquetar_proyecto.py             # build submission.tar.gz
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
| `deck/`, `decks_competidores/`, `dataset/` | Opponent lists, leaderboard decks and card reference data. |
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

Against the 89 real leaderboard decks, weighted by how often each appears:
**93.1% expected ladder winrate**, +3.9 prizes per game, zero forfeits across
35,600 games. The weakest matchup is the Crustle wall archetype. Details and
method in [Matchups](docs/matchups.md).
