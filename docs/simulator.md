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

## What the observation already resolves for you

The board the engine sends is not the text printed on the cards: it is the state
**after** the engine has applied every effect in play. That sounds obvious and it
is the easiest rule in the project to break, because a card's text invites you to
re-derive something the observation already contains.

Two concrete shapes of it, both verified by probing the engine directly:

- **HP already includes the buffs.** A Pokémon whose ability or tool grants extra
  HP arrives with that HP in `maxHp` — the field is documented as *current* max
  HP, not printed HP. Okidogi's Adrena-Power is the worked example: it reports
  230 the moment the condition is met and 130 when it is not. Recomputing the
  bonus would invent a body that cannot be knocked out.
- **An Energy reports the type it actually provides.** `energies` carries
  resolved energy types, so a special Energy shows up as whatever it supplies on
  the body it is attached to. Prism Energy provides every type on a *Basic* and
  only Colorless otherwise, and the engine reports exactly that: rainbow on a
  Basic, colorless on a Stage 1. The "must be a Basic" clause is the engine's job
  and it has already done it.

The working rule: **only compute what the observation does not contain.** Damage
an attack will do next turn is ours to project, because it has not happened yet.
The state of the board is not.

When you are unsure which side of the line a card falls on, the cheapest answer
is an experiment: build a small deck around the card, play games through `cg/`
with the generic bot, and read the raw observation. That is how both examples
above were settled, and it takes minutes.

## Data files around the simulator

| Path | What it is |
| --- | --- |
| `deck.csv` | Our deck: 60 card IDs, one per line. This exact format is what every deck file in the project uses. |
| `dataset/EN_Card_Data.csv` | Official English card reference data for the challenge. |
| `dataset/Card_ID List_EN.pdf` | The official card list, used by the deck-image renderer. |
| `deck/real_opponents/` | The measurable meta: 87 real leaderboard lists, deduplicated and screened for whether the generic bot can pilot them, plus `pesos.csv` giving each list its meta frequency, its archetype and how many cards it shares with our own sixty. Lists the bot cannot pilot go to `no_pilotables/` — not a failure, but the part of the meta the harness cannot measure yet. |
| `deck/real_opponents_2026-08-07/` | The corpus this one replaced, kept rather than deleted. A finding is only reproducible while the list it was written against exists, and a rebuild moves sixty of them. `utils/corpus_bridge.py` carries a finding across the gap. |
| `deck/opponents/` | Hand-built synthetic archetype decks, kept for exercising mechanics the current meta does not offer (item lock, mill). No longer the default target of the matchup matrix. |
| `competitor_decks/` | The raw download: 60-card lists from the top of the leaderboard, plus an index classifying each by archetype, position and score. **300 files, 88 distinct decks** — see below. |

### The top-300 is 88 decks, and `deck/real_opponents/` already is them

Measured 12 August 2026 over `competitor_decks/mazo_*.csv`: all 300 files load
into `battle_start` without error, but deduplicated by sorted card multiset they
are **88 unique lists** — the other 212 files are exact copies. Of those 88,
**87 are already in `deck/real_opponents/`**; the missing one is the list
`pesos.csv` marks `no_pilotable`.

The duplicate count *is* the meta weight, and `pesos.csv` already encodes it:
multiplicities 92, 45, 24, 9, 7… map onto `peso_meta` 0.3067, 0.15, 0.08, 0.03…

Two consequences worth stating plainly, because both are easy to get wrong:

- **There is no deck-harvesting work left.** Running the 300 files instead of
  the 88 costs 3.4× the compute for exactly zero additional information.
- **Equal games per deck misallocates the budget.** 66 of the 88 lists appear
  exactly once (0.33 % of the meta each) while the top three are 53.7 % between
  them, so a uniform schedule spends **75 % of the compute on 22 % of the
  meta**. That is what `--weights` and `--allocation` exist to fix; see
  [Tools](tools.md).

The `<archetype>_<n>.csv` naming is by descending meta weight **within** an
archetype, which makes a name a **rank, not a deck**: after a re-harvest,
`crustle_wall_6` lands on different sixty cards. Record a finding against the
list's contents, not its filename.

## Native-library notes

The engine is loaded through `ctypes`. If you move platforms or update
dependencies, this is the layer to check first — a missing or mismatched native
library fails at import time, before any game logic runs.

---

Next: [Code map](code-map.md) · [Tools](tools.md)
