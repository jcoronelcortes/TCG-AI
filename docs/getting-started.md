# Getting started

[← Documentation index](README.md)

## What this project is

A heuristic Pokémon TCG player. The whole agent is one function:

```python
from main import agent

selection = agent(observation)   # -> list of option indexes
```

The simulator hands the agent an **observation** (the board, our hand, the
opponent, and the menu of legal options) and expects back the **indexes of the
options to play**. Everything else in the repository exists to build, measure or
debug that function.

## Requirements

- **Python 3.10 or newer** (tested on 3.11).
- **No third-party packages for the agent itself.** This is deliberate: the
  agent runs inside the Kaggle competition container, where nothing gets
  installed. The agent, the tools in `utils/` and the bundled simulator in `cg/`
  use only the standard library plus `ctypes` for the native engine. Before
  importing any third-party package into agent or tool code, check that the
  competition environment has it.

Development dependencies (test runner and property-based testing) are separate:

```bash
python -m pip install -r requirements-dev.txt
```

> Without `hypothesis`, the property-based test file fails to load and pytest
> aborts the whole run with a collection error — it does not skip it.

`requirements-render.txt` (Pillow, NumPy, pandas, PyMuPDF) is optional and only
used by the deck-image renderer.

## Run the test suite

```bash
python -m pytest -q
```

The suite runs in a few seconds and is the fastest signal that nothing broke.
With coverage:

```bash
python -m pytest -q --cov=. --cov-report=term-missing
```

See [Testing](testing.md) for what the different kinds of tests protect.

## Play games locally

The repository ships the simulator, so you can play full games without Kaggle:

```bash
# agent vs agent (sanity check: winrate should sit near 50%)
python utils/selfplay.py --partidas 100

# agent vs a real leaderboard deck piloted by the generic bot
python utils/selfplay.py --partidas 200 --rival deck/rivales_reales/crustle_wall_2.csv
```

To see how the agent performs against the whole known meta:

```bash
python utils/matchup_matrix.py --partidas 400 --pesos
```

Both are described in [Tools](tools.md) and [Improving the agent](improving-the-agent.md).

## Package a submission

```bash
python utils/package_project.py
```

This writes `submission.tar.gz` at the repository root with `main.py`,
`deck.csv` and the local packages that `main.py` imports. The package list is
**derived from the imports**, never hand-written — forgetting a package is the
most expensive possible mistake, because the submission would start broken in
the competition while every local test stays green.

## Where to go next

- Want to understand the decisions? → [How the agent thinks](how-the-agent-thinks.md)
- Want to find some code? → [Code map](code-map.md)
- Want to change the strategy? → [Improving the agent](improving-the-agent.md)
