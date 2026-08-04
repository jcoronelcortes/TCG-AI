# TCG-AI Documentation

TCG-AI is a **heuristic agent that plays Pokémon Trading Card Game** inside the
simulator of the *PTCG AI Battle Challenge*. It receives the game state, scores
every legal option, and plays the best one. There is no machine learning: every
decision comes from rules that a human wrote, measured, and kept only if they
won more games.

This documentation explains **what each part of the project is for**, not how it
is written line by line. It is meant to stay readable as the code changes.

---

## Start here

| Page | What you get |
| --- | --- |
| [Getting started](getting-started.md) | Install, run the tests, play a game, package a submission. |
| [How the agent thinks](how-the-agent-thinks.md) | The whole decision loop in one page. Read this before anything else. |
| [Glossary](glossary.md) | Card-game terms and project vocabulary, defined once. |

## The code

| Page | What you get |
| --- | --- |
| [Code map](code-map.md) | Every folder and package, and what it is responsible for. |
| [The simulator layer](simulator.md) | How the project talks to the game engine, and what the data files are. |
| [Our deck and its engines](deck-and-engines.md) | The 60 cards we pilot and the combos the agent is built around. |

## The strategy

| Page | What you get |
| --- | --- |
| [Strategy](strategy.md) | The principles the agent encodes: attacking, energy, retreating, hand refills, disruption. |
| [Matchups](matchups.md) | The opposing archetypes, how we handle each, and where we currently lose. |

## Working on the project

| Page | What you get |
| --- | --- |
| [Improving the agent](improving-the-agent.md) | The measurement workflow: how a strategy change is proposed, measured, and kept or reverted. |
| [Tools](tools.md) | Catalogue of the scripts in `utils/`: what each one is for and how to run it. |
| [Testing](testing.md) | The safety nets: unit tests, real fixtures, golden corpus, invariants, architecture lint. |
| [Debugging a decision](debugging.md) | How to reproduce one concrete decision and find out why the agent chose it. |
| [Project history](project-history.md) | Why the code is shaped the way it is, and the mistakes that shaped it. |

---

## Documentation conventions

- **English only.** All documentation written from now on is in English. (Code
  comments and docstrings are still in Spanish; they carry a lot of domain
  history and are being left as-is for now.)
- **No line numbers, no line ranges.** Code moves constantly. Pages point at
  folders, packages and concepts instead.
- **Purpose over mechanics.** Each page answers "what is this for, when do I use
  it, why does it exist" — the source is the authority on the exact rules.
