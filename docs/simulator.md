# The simulator layer

[← Documentation index](README.md)

`cg/` is the competition's simulator, vendored into the repository. The agent
does not own it and should not need to change it, but every observation the
agent reads and every game the tools play goes through it.

## What is in `cg/`

| Module | Purpose |
| --- | --- |
| `api.py` | The vocabulary of the game: the enums (option types, decision contexts, areas, card and energy types, log types) and the data classes for the board, cards, Pokémon, options and observations. It also converts the raw dictionary the engine sends into those objects. |
| `game.py` | Driving a battle: start one with two decks, read the current observation, submit a selection, finish and release. This is what the local tools use to play full games. |
| `sim.py` | Loading the native engine: finds the right library for the platform, loads it, and defines the shared battle handle. |
| `utils.py` | Turning JSON and dictionaries into the data classes above. |
| `cg.dll`, `libcg.so`, `libcg.dylib`, `libcg-arm64.so` | The native engine itself, one per platform. These are versioned on purpose — nothing runs without them. |

## The two things worth understanding

**The decision context tells you what is being asked.** The same agent function
handles a normal turn, the initial setup, promoting after a knockout, choosing
a card to fetch, choosing a discard, picking a damage target and answering
yes/no. Each of those arrives as a different context, and the agent branches on
it before anything else.

**The option type tells you what a menu entry is.** Play a card, attach energy,
evolve, use an ability, retreat, attack, end the turn, choose a card, choose an
energy, answer a number. The agent has one scoring branch per type — see the
[Code map](code-map.md).

Both are enumerations in the simulator's API, and both are used constantly
throughout the documentation and the code.

## Data files around the simulator

| Path | What it is |
| --- | --- |
| `deck.csv` | Our deck: 60 card IDs, one per line. This exact format is what every deck file in the project uses. |
| `dataset/EN_Card_Data.csv` | Official English card reference data for the challenge. |
| `dataset/Card_ID List_EN.pdf` | The official card list, used by the deck-image renderer. |
| `deck/rivales_reales/` | Real leaderboard lists, deduplicated and screened for whether the generic bot can pilot them, with a weights file giving each list its true meta frequency. Lists the bot cannot pilot are kept aside — they are not a failure, they are the part of the meta the harness cannot measure yet. |
| `deck/rivales/` | Hand-built synthetic archetype decks, kept for exercising mechanics the current meta does not offer. |
| `decks_competidores/` | The raw download: 60-card lists from the top of the leaderboard, plus an index classifying each by archetype, position and score. |

## Native-library notes

The engine is loaded through `ctypes`. If you move platforms or update
dependencies, this is the layer to check first — a missing or mismatched native
library fails at import time, before any game logic runs.

---

Next: [Code map](code-map.md) · [Tools](tools.md)
