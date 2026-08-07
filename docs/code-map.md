# Code map

[← Documentation index](README.md)

Where everything lives and what it is responsible for. Module names are in
Spanish (so is the code); the descriptions here are what matters.

## Top level

| Path | Purpose |
| --- | --- |
| `main.py` | The agent. Owns `agent()` — the entry point the simulator calls — plus board setup, opponent identification, the decision flags, and who to promote after a knockout. Everything it does not own is imported from `ptcg/`. |
| `ptcg/` | The agent's own package: data, calculators, state, per-card decisions and the phases of a turn. |
| `cg/` | The competition simulator, vendored. See [The simulator layer](simulator.md). |
| `deck.csv` | Our 60-card deck: one card ID per line. |
| `deck/` | Deck-adjacent assets: opponent deck lists and the deck-image renderer. |
| `dataset/` | Official card reference data for the challenge. |
| `competitor_decks/` | Real 60-card lists downloaded from the leaderboard, with an index by archetype and score. |
| `tests/` | The safety nets. See [Testing](testing.md). |
| `utils/` | Command-line tools: play games, measure matchups, autopsy losses, package the submission. See [Tools](tools.md). |
| `records/`, `log/` | Local, throwaway game data (git-ignored). Recorded games and per-turn records used to reproduce decisions. |
| `notebook/` | Meta-analysis notebooks (not versioned). |

## Inside `ptcg/`

The package is split by **what a module is allowed to touch**, not by feature.
Data and rules at the bottom, board reading in the middle, per-card decisions and
turn phases on top. An architecture linter enforces the boundaries — see
[Testing](testing.md).

### `ptcg/cards/` — card data

Pure data. No game state, no simulator access; readable and testable without
starting a battle.

| Module | Purpose |
| --- | --- |
| `ids.py` | Card IDs and the named constants for every card the agent knows about. |
| `groups.py` | Derived groupings: which cards are walls, threats, pre-evolutions of ex lines, and so on. |
| `lines.py` | Evolution lines: stage of a card, its root basic, the chains our deck can build, which link is missing, and what a body in play becomes in one step (which is how the defence sees an opposing pre-evolution for what it will be). |
| `costs.py` | Printed attack costs of our attackers. The *effective* cost of the turn is derived from this (a stadium can tax it). |
| `tables.py` | Card and attack tables built once from the simulator's data. |
| `scoring.py` | Scoring constants shared by several phases. |

### `ptcg/engine/` — the decision scaffolding

| Module | Purpose |
| --- | --- |
| `plan.py` | `AttackPlan`: the turn's chosen attacker, target and attack. |
| `context.py` | `DecisionContext`: the snapshot of the turn handed to the per-card scorers. |
| `rules.py` | A small generic rules engine (fixed rules, adjustments, scenario resolution). |
| `debug.py` | Decision dumping for debugging. See [Debugging a decision](debugging.md). |

### `ptcg/calc/` — reading the board

The calculators. They answer factual questions so the strategy layer does not
have to.

| Module | Purpose |
| --- | --- |
| `energy.py` | Effective energy: our Grass energy counts double while our accelerator is in play, and a stadium can raise attack costs. Answers "can this Pokémon attack?". |
| `damage.py` | What both sides' attacks actually do: our base damage, whether a knockout is guaranteed, sniping the bench — and the projector for the **opposing** active's hit, which every defensive rule in the agent hangs off. Tools and attacker abilities that add a flat amount before weakness are applied there. |
| `card.py` | Reading a card from the observation: its prize value, how good a body it is. |
| `opponent.py` | Reading the opponent: can it attack, which of its bodies are harmless, how big is its hand. |
| `board.py` | Board reading: our active, what can evolve, what the hand can do. |
| `grass.py` | The energy plan: how many more Grass energies the board can actually use, and whether one of them unlocks an attacker today. |
| `probability.py` | Draw probability, used to price refills and searches. |

### `ptcg/state/` — memory

| Module | Purpose |
| --- | --- |
| `agent_state.py` | `AGENT_STATE`: the mutable state that survives between turns (the plan, who goes first, whether we got knocked out, pending search commitments, opponent-archetype flags). One object, never reassigned. |
| `tracking.py` | The belief about our own deck: initial scan, card movement between zones, prize identification. |
| `zones.py` | The zone keys used by that tracking (deck / hand / in play / discard / prize). |
| `logs.py` | Reading the observation's event log, including the knockout window. |

### `ptcg/decision/` — one module per card that has real strategy

These are the cards whose "should I play it, and on what" is a topic in itself.

| Module | The question it answers |
| --- | --- |
| `boss_orders.py` | Is dragging an opponent's benched Pokémon to the front worth the turn, and which one? |
| `ultra_ball.py` | Is the search worth its discard cost, and what should we dig for? The largest decision module in the project. |
| `night_stretcher.py` | What is worth recovering from the discard — a body, an engine piece, or energy for a finisher? |
| `meowth.py` | The hand engine: when to bench Meowth ex for its Supporter search, and what that search is worth. |
| `op_scaling.py` | The opposing attacks whose damage is a count of the board, not the number printed on the card ("20x", "30+"). Fifteen of them appear in the opposing decks in the repo; four more are left out on purpose because their scale is a coin flip or the opponent's own choice. `utils/op_scaling_census.py` audits the table against the card pool. |
| `disruption.py` | Hand disruption. Xerosic's Machinations and Unfair Stamp live together on purpose: the correct order between them makes each consult the other. |
| `supporters.py` | The remaining Supporters and choosing the best one in hand. |
| `poke_pad.py` | Which Pokémon is worth searching for. |
| `bug_catching_set.py` | Bug-type search. |
| `stadiums.py` | Stadium play: our own accelerator, and the shared instant-evolution stadium. |

### `ptcg/turn/` — the phases of a turn

This is the body of what used to be one enormous function, split by phase.

| Module | Purpose |
| --- | --- |
| `game_plan.py` | What the prize count says the turn is FOR, decided before the first decision: is there a route that closes the game, how many prizes we take, how many they take on the reply. The ordering vetoes read it so they do not step aside for a resource card on a turn that ends the game. |
| `scoring.py` | The dispatcher: sends each menu option to the branch for its type. |
| `opciones/` | One module per option type: `play`, `card`, `retreat`, `evolve`, `attach`, `ability`, `attack`, and the short ones together in `minor`. |
| `supporters.py` | Valuing every Supporter in hand for this turn. |
| `energy.py` | Who deserves the energy attachment this turn. |
| `finalize.py` | The close of the turn: play-order tiers, last-second rescues, and the final choice. |
| `ctx*.py` | The context objects that carry the turn's facts between those phases. |

---

Next: [The simulator layer](simulator.md) · [Strategy](strategy.md) · [Tools](tools.md)
