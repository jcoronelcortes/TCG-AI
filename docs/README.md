# TCG-AI Documentation

TCG-AI is a **heuristic agent that plays Pokémon Trading Card Game** inside the
simulator of the Kaggle competition [The Pokémon Company — PTCG AI Battle
Challenge Simulation](https://www.kaggle.com/competitions/pokemon-tcg-ai-battle).

It receives the game state, scores every legal option, and plays the best one.
There is no machine learning: every decision comes from rules that a human
wrote, measured, and kept only if they won more games.

This documentation explains **what each part of the project is for**, not how it
is written line by line. It is meant to stay readable as the code changes.

---

## Start here

| Page | What you get |
| --- | --- |
| [Getting started](getting-started.md) | Install, run the tests, play a game, package a submission. |
| [Contributing](../CONTRIBUTING.md) | The four gates a change must pass, and how to review one. |
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
| [The instruments](instruments.md) | The measuring apparatus as a whole — the four questions it answers, and the rule that decides whether a number may be believed. |
| [Tools](tools.md) | Catalogue of the scripts in `utils/`: what each one is for and how to run it. |
| [Testing](testing.md) | The safety nets: unit tests, real fixtures, both golden corpora, invariants, mutation, architecture lint, and what runs in CI. |
| [Debugging a decision](debugging.md) | How to reproduce one concrete decision and find out why the agent chose it. |
| [Project history](project-history.md) | Why the code is shaped the way it is, and the mistakes that shaped it. |
| [Rename maps](history/rename-maps/README.md) | What became what when the project was translated to English. |

## Work in progress

Plans with a status line at the top. They are living documents: each one says
which waves have shipped, which are still plan, and what running the shipped
ones actually cost.

| Page | What it plans |
| --- | --- |
| [Discarding well](discard-plan-2026-08.md) | The forced-discard decision: what the per-card price list gets wrong, the keep-set planner meant to replace it, and the waves to get there. Waves 0–1 shipped. |
| [The testing plan](testing-plan-2026-08.md) | How the safety nets were rebuilt in August 2026 — the frozen corpus, the coverage ratchet, the mutation gate, the nightly pipeline. |
| [The engine source](engine-source-plan-2026-08-12.md) | What arriving at the simulator's C++ source unlocks — seeded, reproducible games; a forward-simulation API we have never used — and the four phases to exploit it. Includes the measured correction that the "top-300" is 88 distinct decks we already have. |
| [Night plan, 12 Aug](night-plan-2026-08-12.md) | The most recent session plan — detectors for the eight defect classes of 12 August, plus the consolidated pending backlog. Earlier ones: [11 Aug](night-plan-2026-08-11.md), [9 Aug](night-plan-2026-08-09.md), [10 Aug](night-plan-2026-08-10.md), [10 Aug b](night-plan-2026-08-10-b.md), [10 Aug c](night-plan-2026-08-10-c.md). |

## Measurement sessions, written up

A session is planned, run, and then written up — including the reverts, because
a rule that was tried, measured neutral and removed stops the next person from
spending the same week.

| Page | What it found |
| --- | --- |
| [The night of 12 Aug 2026](history/night-2026-08-12.md) | The most recent: four detectors built for the eight defect classes of the day, three of which found something on their first run — a four-card family the code had never heard of, 280 menus where an order beat a number, and a lint rule calibrated against the exact field that lost a game. |
| [The night of 11 Aug 2026](history/night-2026-08-11.md) | Three defects nobody had read, two detectors that caught their own authors, and a gain that was real while the meta did not contain it. |
| [The night of 10 Aug 2026 (c)](history/night-2026-08-10-c.md) | The session that produced the corpus rebuild and the corpus bridge. |
| [The day of 9 Aug 2026](history/day-2026-08-09.md) | The full day, gate by gate. |
| [The 9 Aug full run](history/night-2026-08-09-full-run.md) | The complete pipeline end to end. |
| [The night of 7 Aug 2026](history/night-2026-08-07.md) | What was found, what was measured, and what was deliberately not shipped. |
| [Phantom knockouts vs Crustle](history/phantom-ko-crustle-2026-08-10.md) | One detector's findings chased to the bottom — and the artefacts of its own that were in the way. |
| [Tournament principles audit](history/tournament-principles-audit.md) | The five habits that separate a casual player from a tournament one, checked one by one against the code. |
| [The menu-order ties](history/menu-order-ties.md) | The 0.67% of decisions the emission order settles, class by class: which ones are harmless, and the promotion that handed the game away. |

---

## Documentation conventions

- **English only, everywhere.** Everything written *into* the project is
  English: documentation, code comments, docstrings, test docstrings, test
  assertion messages and commit messages. Two deliberate exceptions: what the
  tools **print** to the console is a reply to the user and stays in Spanish,
  and so do stored data fields already written to disk (see the last section of
  [Tools](tools.md) — renaming one of those is a migration, not a rename).
- **No line numbers, no line ranges.** Code moves constantly. Pages point at
  folders, packages and concepts instead.
- **Purpose over mechanics.** Each page answers "what is this for, when do I use
  it, why does it exist" — the source is the authority on the exact rules.
- **A measured number carries its method.** Where a page states a winrate, a
  frequency or a share, it also states the sample size, the corpus and the date.
  A number with no method behind it rots into folklore, and this project has
  reverted rules on the strength of numbers that turned out to be their own
  instrument's bug.
- **Session write-ups are append-only.** `docs/history/` records what was
  measured on a date, and it is not edited afterwards to match what is true
  today. When a finding is later closed or reversed, the newer page says so.
  Everything outside `history/` is expected to describe the present.
