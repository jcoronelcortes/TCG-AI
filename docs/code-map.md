# Code map

[← Documentation index](README.md)

Where everything lives and what it is responsible for. Identifiers, filenames
and flags are English throughout; what is still Spanish is *stored data*, and
[Tools](tools.md) says which fields and why.

## Top level

| Path | Purpose |
| --- | --- |
| `main.py` | The agent. Owns `agent()` — the entry point the simulator calls — plus board setup, opponent identification, the decision flags, and who to promote after a knockout. Everything it does not own is imported from `ptcg/`. |
| `ptcg/` | The agent's own package: data, calculators, state, per-card decisions and the phases of a turn. |
| `cg/` | The competition simulator, vendored. See [The simulator layer](simulator.md). |
| `deck.csv` | Our 60-card deck: one card ID per line. |
| `deck/` | Deck-adjacent assets: opponent deck lists and the deck-image renderer. The measurable corpora live here — `real_opponents/` (the 87 admitted lists of the top-300 harvest), `real_opponents_500/` (the 133 admitted lists of the top-500 one, git-ignored, so tools want an absolute path to it) and the dated retirement of an earlier one. Each carries its own `pesos*.csv` weights. |
| `dataset/` | Official card reference data for the challenge. |
| `competitor_decks/`, `competitor_decks_500/` | Real 60-card lists downloaded from the leaderboard, with an index by archetype and score. The `_500` sweep of 12 August is the current one; the earlier top-300 harvest is kept because a finding written against a list is only reproducible while that list exists. |
| `ptcg_engine/`, `cg/build/` | The simulator's own C++ source and the locally built, **seedable** engine. Git-ignored, and the architecture lint (R11) keeps both unreachable from `main.py` and `ptcg/` — the competition binary is the only engine the agent may ever see. See [The simulator layer](simulator.md). |
| `tests/` | The safety nets, including the committed frozen corpus. See [Testing](testing.md). |
| `utils/` | Command-line tools: play games, measure matchups, audit tables, autopsy losses, package the submission. See [Tools](tools.md) and [The instruments](instruments.md). |
| `records/`, `log/`, `log_analisys/` | Local, throwaway game data (git-ignored, the folders kept via `.gitkeep`). Recorded games, per-turn records, and everything the gates and the nightly pipeline write. |
| `notebook/` | Meta-analysis notebooks (not versioned). |

Working locally you will also see git-ignored files at the root that are not
part of the project: `_v_*.py` (ablation copies of `main.py` for A/B runs),
`main_pre_*.py` (snapshots taken before a large change) and `submission.tar.gz`.
A fresh clone has none of them.

## Inside `ptcg/`

The package is split by **what a module is allowed to touch**, not by feature.
Data and rules at the bottom, board reading in the middle, per-card decisions and
turn phases on top. An architecture linter enforces the boundaries — see
[Testing](testing.md).

> **This page is the index; the modules explain themselves.** Every package has
> a `__init__.py` docstring covering its layer, and every module opens with what
> it is for, how its logic is organised and which traps it has already fallen
> into. Read `ptcg/__init__.py` for the layer map, then the module itself — this
> table only tells you which file to open.

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
| `op_scaling.py` | The **opposing** attacks whose damage is a count of the board rather than the number printed on the card ("20x", "30+"). It lives here because it is a table, not a decision. `utils/op_scaling_census.py` audits it against every opposing deck in the repo, and the suite runs that audit as a gate. |

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
| `logs.py` | Reading the observation's event log — the draws and card movements that keep the deck belief current between decisions. (The knockout *window*, which is a different question, is decided in `main.py`.) |

### `ptcg/decision/` — one module per card that has real strategy

These are the cards whose "should I play it, and on what" is a topic in itself.

| Module | The question it answers |
| --- | --- |
| `boss_orders.py` | Is dragging an opponent's benched Pokémon to the front worth the turn, and which one? |
| `ultra_ball.py` | Is the search worth its discard cost, and what should we dig for? The largest decision module in the project. |
| `night_stretcher.py` | What is worth recovering from the discard — a body, an engine piece, or energy for a finisher? |
| `meowth.py` | The hand engine: when to bench Meowth ex for its Supporter search, and what that search is worth. |
| `disruption.py` | Hand disruption, in **both** directions. Playing Xerosic's Machinations and the Unfair Stamp lives here — they are together on purpose, because the correct order between them makes each consult the other — and so does the other half: what to keep when *their* card forces a discard on us. See [Discarding well](discard-plan-2026-08.md). |
| `supporters.py` | The remaining Supporters and choosing the best one in hand. |
| `poke_pad.py` | Which Pokémon is worth searching for. |
| `bug_catching_set.py` | Bug-type search. |
| `stadiums.py` | Stadium play: our own accelerator, and the shared instant-evolution stadium. |

### `ptcg/turn/` — the phases of a turn

This is the body of what used to be one enormous function, split by phase.

| Module | Purpose |
| --- | --- |
| `game_plan.py` | What the prize count says the turn is FOR, decided before the first decision: is there a route that closes the game, how many prizes we take, how many they take on the reply. It answers with one word — `WIN_NOW`, `DENY`, `RACE`, `DEVELOP` — and the ordering vetoes read it so they do not step aside for a resource card on a turn that ends the game. |
| `scoring.py` | The dispatcher: sends each menu option to the branch for its type. |
| `scoring_sentinel.py` | The one sentinel value the branches return to say "I appended my own scores". It lives in its own module so the dispatcher and the branches do not have to import each other. |
| `options/` | One module per option type: `play`, `card`, `retreat`, `evolve`, `attach`, `ability`, `attack`, and the short ones together in `minor` (including the yes/no select that decides whether we take the first turn). |
| `supporters.py` | Valuing every Supporter in hand for this turn. |
| `energy.py` | Who deserves the energy attachment this turn. |
| `finalize.py` | The close of the turn: play-order tiers, last-second rescues, the filed ordering vetoes being lifted or confirmed, and the final choice. |
| `ctx.py`, `ctx_scoring.py`, `energy_ctx.py`, `supporters_ctx.py` | The context objects that carry the turn's facts between those phases, so each phase reads one snapshot instead of recomputing the board. |

## Inside `tests/`

Most of `tests/` is one file per lesson learned; those are described in
[Testing](testing.md). The modules that are *not* tests are the shared
machinery:

| Module | Purpose |
| --- | --- |
| `state_builder.py` | Builds synthetic observations with strict 60-card accounting. |
| `golden_corpus.py` | The replay engine behind both corpora, and a command line of its own. |
| `corpus/` | The committed frozen corpus: 50 games reduced to our own decisions, plus the snapshot to compare against. |
| `fixtures/` | Observations captured from real games, self-contained JSON. |
| `kaggle_loader.py` | A verbatim copy of the competition loader, so the smoke test loads the submission exactly as the container does. |
| `patching.py` | Sets a name everywhere it is bound — several names live in more than one module, so patching one does not reach the others. |
| `main_support.py` | What more than one slice of the `main.py` regression log needs. |
| `decision_grid.py`, `rule_trace.py`, `fez_menu.py` | The metamorphic sweep, rule-chain tracing, and one shared menu builder. |

---

Next: [The simulator layer](simulator.md) · [Strategy](strategy.md) · [Tools](tools.md) · [The instruments](instruments.md)
