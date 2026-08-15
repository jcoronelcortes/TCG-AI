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
| [Naming](naming.md) | The vocabulary the code itself uses: reach for the word already in use rather than a synonym. |

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
| ⭐ [The reversible bet (Marnie, step 94)](marnie-the-reversible-bet-2026-08-14.md) | **The promotion that gave a turn away, and the rule that came out of it.** With no engine in hand the agent promoted a Tapu Bulu at 0/4 with a retreat of 3 over an Ogerpon ex one attachment from a 420 through the Grass weakness — and drew the energy the very next turn. Route (f) bets the turn's own draw whenever the body can walk back: invisible to the winrate (2 795 vs 2 796 in 3 000 paired games) and worth **+15 pp / +1.03 margin** under the rules oracle on the board it was written from. |
| ⭐ [The veto that walks back (Archaludon, step 77)](archaludon-the-veto-that-walks-back-2026-08-14.md) | **The same promotion, vetoed one rung further down.** The selector correctly named an Ogerpon ex one attachment from finishing their Archaludon — with the Lillie's to find the Grass and the Grass to pay its own retreat — and the match-point veto overwrote it with −30000 because a 2-prize ex is their whole remaining pile. Their blow arrives a turn of ours later, so a body that can step aside is not there to receive it: **+14 pp / +1.09 margin** under the rules oracle, 0 flips on the frozen fifty. |
| ⭐ [The seat the search completes (Mega Lucario, step 59)](lucario-the-seat-the-search-completes-2026-08-14.md) | **The third promotion autopsy: the hand read as a card, never as a route.** Nothing on our bench survived their 270, so the evolution-survivor block opened — and found no evolution in hand, because the Hydrapple ex was in the deck and what the hand held was the Dawn that reaches it. A charged Ogerpon ex came up, could not touch the 440 in front of it, and paid two prizes plus three energies. **1 flip in 3 685 corpus decisions**, 0 mutation survivors, **+1 pp / +0.17 margin** over a 0.07 floor under the rules oracle. Also records what does *not* work: the cheapest body is not the answer, the cheapest body that is a **seat** is. |
| ⭐ [The shield they buy for one turn (Comfey/Chandelure)](comfey-the-shield-they-buy-for-one-turn-2026-08-14.md) | **The fourth wall, and the only one that leaves nothing on the board.** Acerola's Mischief makes our ex do zero to one of their bodies — damage and effects — for one turn, and its precondition puts it exactly on the turns that end the game: a loss held at one prize while the opponent never left six, attacking into a zero from turn 13 to the end. The only evidence is a `PLAY` entry in the log batch of *their* turn, and what it pins is a **serial**, so the shield travels with the body and the answer is to gust it away. Also the cleanest case of an instrument being blind by construction: the differential oracle reports nothing, with the reading on or off. |
| ⭐ [The prize the wall does not own (Crustle/Kangaskhan, step 123)](crustle-the-prize-the-wall-does-not-own-2026-08-15.md) | **An archetype flag vetoing a knockout that was not the archetype's.** The Crustle was on their *bench*; in the way stood a Mega Kangaskhan ex at 80 of 300 with no energy, and one of six Grass in our discard both paid for Wood Hammer and took three prizes. Night Stretcher could not be played for it, because against a wall list `_score_night_stretcher_play` **replaces** its ballot with the Crustle whitelist and every lethal-energy scenario lives in the list that is replaced. The proof it was a defect rather than a judgement: the *fetch* half of the same card already scored that Grass at 1400 with no guard at all. 0 flips in 3 580 corpus decisions; census 0.06/game, **below its own criterion**, and recorded that way. |
| ⭐ [Meganium is an attacker, not the doubler (Crustle, steps 92 and 137)](crustle-meganium-is-an-attacker-not-the-doubler-2026-08-15.md) | **The same archetype flag, one rung further in — and the wall's own answer starving in front of it.** Crustle blanks the bodies with a *rule box*; Meganium has none, so Solar Beam does its 140 into it. Both charging rules read it as the Wild Growth engine instead: the last Grass went to a **second** Teal Mask Ogerpon ex against the wall that blanks ex, and the turn's attachment went to an **Applin benched that very turn** over a Meganium one card from attacking. Narrowed from the deck list to the body (`_ctm_wall_in_the_way`) after the oracle graded the wide version 3 for / 6 against, and the six were all boards where the wall was not the obstacle. Census 0.58–0.84/game with **0.00 leakage**; the ladder half is **+17/+20/+26/+28/+18 pp** on step 137 across five runs; the reservation half is **NEUTRAL and says so**. |
| ⭐ [The second wave is a reason of its own (Festival Lead, step 103)](festival-the-second-wave-is-a-reason-of-its-own-2026-08-15.md) | **Four correct readings and none of them allowed to spend the turn.** `prizes_today` said 2, `_promote_ko_active_prizes` said 2, and the evolve veto fired — but the only flag that *executes* a promote route asks it to close the game, and `_festival_sac_pivot` (this exact swap) only opened for a **doomed** ex. Meanwhile Teal Dance banked the single Grass the detector was counting on: the veto then lifted **by itself** for want of that card and the body it had just protected was evolved. The pivot gains an offensive arm (the second wave has to really close a body) and the reserve now holds the energy, not just the body. Oracle: **two prizes instead of one, 50 of 50**; gate blind and its **own control says so** (−0.7 pp against a −0.4 pp floor); census 13 firings in 40 games, **0 outside the stadium**; 1 corpus flip. |
| ⭐ [The answer to the wall is a reserve, not today's attacker (Crustle, step 58)](crustle-the-reserve-does-not-take-the-front-2026-08-15.md) | **The mirror image of the entry above, and the same archetype flag a fourth time.** Their Crustle waited on the *bench* and a Mega Kangaskhan ex 300/300 stood in front; our Teal Mask Ogerpon ex hit it for 150. The agent **retreated it** — discarding an energy card — to attack for **140** with the Meganium, leaving the only body of ours that can ever hurt that wall in front of a Rapid-Fire Combo that kills it, having just pulled back the 210 HP body that survives it. The two 3400 retreat branches were guarded by the deck flag plus "the active does not knock out", which is not the same sentence as "the active is blanked". The swap is now asked the only question that pays for it: **more damage this turn than the body going down**, strictly. 2 corpus flips, both the same class; census 0.53 / 0.30 per game with **0.00 leakage** and 100 % of the flips a retreat we no longer make; oracle **1 for / 0 against**; gate **+0.60 pp on both lists over a +0.00 control**, not significant and stated as such. |
| [The harvest off the table (Marnie, step 150)](marnie-la-cosecha-fuera-de-mesa-2026-08-14.md) | The other Marnie autopsy: the four prizes their board takes with no attack at all, and why the retreat had already lost the game. |

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
| [The engine source](engine-source-plan-2026-08-12.md) | What arriving at the simulator's C++ source unlocks, and the four phases to exploit it. **Phases A–C shipped**: games run on every core (5.06× at 6 workers), a seeded engine puts the control group's noise floor at *exactly* zero (87/87 matchups at delta 0.0000), and spending the budget by meta share tightened the weighted interval from ±1.50 to ±0.46 for the same compute. Phase D — the forward-simulation API nothing has ever used — is the remaining prize. |
| ⭐ [The card census, run](card-census-2026-08-13.md) | **The plan below, executed — B0 to B7.** `utils/card_census.py` plus 10 635 simulated games weighted by meta share and 106 real ladder games of our own. Two headline findings. **The wins-vs-losses split measures the clock unless it is matched on game length** (a lost game runs 31 turns to a won game's 13), and what survives the match is that **Hydrapple ex is played less and pitched as fodder more in the games we lose** — the same direction in all three sources, which is the starvation finding on a single card. And **the generic bot prices the comeback cards as dead**: Unfair Stamp converts 23.5 % simulated against 72.1 % on the real ladder, because against the bot we are almost never behind. |
| [The card census, planned](card-census-plan-2026-08-13.md) | **The top pending item, scoped.** What each of our 60 cards actually does — pooled, per opponent archetype, and split wins vs losses — from simulated games *and* from real ladder replays. Verified while writing: the engine already emits `PLAY`, `ATTACH` and `EVOLVE` as distinct events, so a played Supporter and a card discarded as fodder are told apart by the engine rather than inferred; every copy carries a unique `serial`; and `DECK→LOOKING→DECK` gives a free read on the cards we search past and decline (28 looked at, 8 taken, 20 returned in one game). |
| ⭐ [Playbook against the meta](playbook-vs-meta-2026-08-13.md) | **How to pilot our list against the 500 decks at the top of the leaderboard**, measured against 133 real lists with their meta weight. **94.50 % ±0.19 in the field, 95.81 % at the top-100** — we do better at the top, because the field is weighted toward the two matchups we actually struggle in. Only two archetypes sit below 92 %: **Crustle Wall (80.0 %) and Ogerpon Verde (85.4 %)**, and they are also the two with the lowest prize differential and the largest seat dependence (+6.4 and +5.3 pp for opening). Going first is worth **+1.92 pp** across the meta with zero forfeits in 26 590 first-seat games. |
| ⭐ [Phase D — grading against the rules](phase-d-2026-08-14.md) | **The first instrument here that does not judge the agent against another heuristic.** A rollout to game end costs 9.3 ms, so the whole tie census runs in five minutes. Its verdict on 240 of 279 ties: the scorer says they are worth the same and the rules agree — **the ties are ties**. The one class with an opinion is the Ripening ↔ manual-attachment axis that was measured neutral and reverted, and three independent populations now say the revert was right by +0.63 to +0.76 prizes. Four of the plan's own assumptions did not survive contact, and the determinizer took three attempts, each one caught by its own guard. |
| ⭐ [Searching the list, run](list-search-2026-08-14.md) | **Eleven variants, zero recommended swaps, one finding.** The sixteenth Basic Grass is worth about **+0.09 prizes per game**, robust across four independent routes to it; which card pays for it is not resolved by this instrument. Two variants passed the winrate gate and neither is recommended: one cuts a card the simulation misprices by 17 points against the real ladder, the other deletes **52 of the agent's 393 named rules** — every gust rule there is. The gate found candidates; the recorded disciplines decided. |
| [Day plan, 14 Aug — searching the list](day-plan-2026-08-14.md) | **Running now.** The night measured the list as worth more than thirteen rule commits, so the day searches it: single-card swaps, each measured paired against the current sixty over the same 133 lists and the same seeds, with the criterion written before anything runs — a positive prize delta *and* a winrate interval that excludes zero. **Nothing is merged into `deck.csv`.** And the family simulation may not decide (Unfair Stamp, Fezandipiti ex, the recovery package) is measured but never recommended. |
| [Night plan, 15 Aug](night-plan-2026-08-15.md) | **The session written up below, as it was planned.** Six tracks, all six answered by default: the red test, the memory index, the unexplained −0.90 pp, the autopsy's worklist, one pending from 12 August and the discovery queue. Worth reading beside its write-up for one reason — the plan's own premise about the red test was wrong, and the write-up says how. |
| ⭐ [Night plan, 14 Aug](night-plan-2026-08-14.md) | **The next session, written to run unattended: the sixty cards moved.** `deck.csv` changed on 13 August (−1 Tapu Bulu, −1 Night Stretcher, +1 Poké Pad, +1 Basic Grass) and the working tree is red on seven tests, all of them consistent with that. Two things moved the same day — thirteen rule commits and four cards — so the headline runs **three arms and never adds the two deltas**. Found while writing it: the `--our-deck` flag the previous plan called "the one real integration task" would have measured something that is not a game, because `main.py` reads `deck.csv` from the working directory and the agent's whole deck belief comes from there. The correct harness is one exported tree per list and no new code. |
| [Night plan, 13 Aug](night-plan-2026-08-13-b.md) | **The previous session, written to run unattended: the 500 leaderboard decks and how to pilot against them.** The first plan whose deliverable is a playbook rather than a winrate delta. All seven questions asked in §0 before anything starts, then no interruption until the morning report. Measured while writing it: the 500 decks are 135 unique lists, **one of them is 32.4 % of the whole field**, eight archetypes are 92 % of it — and the **top-100 is a different meta from the rest of the ladder** (Marnie 21 % there, 42 % at positions 401-500), so every headline number is reported under two weightings. §7 is what it does when something fails at 03:00. |
| [~~Night plan, 13 Aug (the oracle)~~](night-plan-2026-08-13.md) | **DISCARDED, not scheduled** — the forward-simulation night, displaced by the plan above (both are CPU-bound on the same six workers). Kept only because its four measured Search-API facts belong to [phase D of the engine-source plan](engine-source-plan-2026-08-12.md): the API is already wrapped, it is a tree rather than a line, and a full rollout to game end costs 0.02 s. |
| [Night plan, 12 Aug](night-plan-2026-08-12.md) | The previous session plan — detectors for the eight defect classes of 12 August, plus the consolidated pending backlog. Earlier ones: [11 Aug](night-plan-2026-08-11.md), [9 Aug](night-plan-2026-08-09.md), [10 Aug](night-plan-2026-08-10.md), [10 Aug b](night-plan-2026-08-10-b.md), [10 Aug c](night-plan-2026-08-10-c.md). |

## Measurement sessions, written up

A session is planned, run, and then written up — including the reverts, because
a rule that was tried, measured neutral and removed stops the next person from
spending the same week.

| Page | What it found |
| --- | --- |
| ⭐ [The night of 15 Aug 2026](history/night-2026-08-15.md) | The ground, and a pending answered with a number. The red test was **not a regression** — the control worktree had no `records/` and the test had skipped itself, so a board a guard had never seen looked like one the day broke. Seven memory entries claimed work was uncommitted that had been in `main` for a day. The unexplained **−0.90 pp** of Mega Lopunny/Froslass is **not the code** (12 000 games per arm, ±0.1) and its losses are starvation. And **two pendings were answered with a number, both NO**: the Tera cover price (built, gated, eight of eight prize deltas negative) and the Dwebble the gust may not take (a one-in-forty-games board, below its own written criterion by fifteen times). |
| ⭐ [The night of 14 Aug 2026](history/night-2026-08-14.md) | The night the sixty cards moved. Seven tests went red and not one was a regression: **a replay is a game of the list of its day**, and the plan's own recommendation — re-freeze the corpus — would have written a false belief into the golden snapshot for good. The day's thirteen commits measure **+0.36 pp [+0.10, +0.63]**, the first measurement the Cornerstone merge has ever had. And the list is not a proposal: the census's own alarm found **90 real ladder games already played with it**. |
| [The night of 12 Aug 2026](history/night-2026-08-12.md) | The most recent: four detectors built for the eight defect classes of the day, three of which found something on their first run — a four-card family the code had never heard of, 280 menus where an order beat a number, and a lint rule calibrated against the exact field that lost a game. |
| [The night of 11 Aug 2026](history/night-2026-08-11.md) | Three defects nobody had read, two detectors that caught their own authors, and a gain that was real while the meta did not contain it. |
| [The night of 10 Aug 2026 (c)](history/night-2026-08-10-c.md) | The session that produced the corpus rebuild and the corpus bridge. |
| [The day of 9 Aug 2026](history/day-2026-08-09.md) | The full day, gate by gate. |
| [The 9 Aug full run](history/night-2026-08-09-full-run.md) | The complete pipeline end to end. |
| [The night of 7 Aug 2026](history/night-2026-08-07.md) | What was found, what was measured, and what was deliberately not shipped. |
| [Phantom knockouts vs Crustle](history/phantom-ko-crustle-2026-08-10.md) | One detector's findings chased to the bottom — and the artefacts of its own that were in the way. |
| [Tournament principles audit](history/tournament-principles-audit.md) | The five habits that separate a casual player from a tournament one, checked one by one against the code. |
| [The menu-order ties](history/menu-order-ties.md) | The 0.67% of decisions the emission order settles, class by class: which ones are harmless, and the promotion that handed the game away. |
| [The 500 decks](history/the-500-decks-2026-08-13.md) | The harvest itself: 500 lists, 135 unique, one of them 32.4% of the field — and the top-100 turning out to be a different meta from the rest of the ladder. |

**Single findings, written up on their own.** Each is one rule from proposal to
verdict, kept because the verdict is as useful as the rule:
[the cap that waits for an inflated hand](history/the-cap-waits-for-an-inflated-hand-2026-08-14.md)
(the run where the oracle killed the hunch it was built to test) ·
[the cap is cashed when the slot dies](history/the-cap-is-cashed-when-the-slot-dies-2026-08-14.md) ·
[their own drip finishes the body in front](history/their-own-drip-finishes-the-body-in-front-2026-08-14.md) ·
[a scorer does not write state](history/a-scorer-does-not-write-state-2026-08-11.md) ·
[every flag has a law](history/every-flag-has-a-law-2026-08-11.md) ·
[one of the four was dead](history/one-of-the-four-was-dead-2026-08-11.md) ·
[the ability is not the attachment](history/the-ability-is-not-the-attachment-2026-08-11.md) ·
[the fuel and the orphan](history/the-fuel-and-the-orphan-2026-08-11.md) ·
[the second copy](history/the-second-copy-2026-08-11.md).

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
- **These pages orient; the modules explain themselves.** Documentation stops at
  the level that stays true as the code moves. Below it, every package carries an
  `__init__.py` docstring for its layer and every module opens with what it is
  for, how its logic is organised and which traps it has already fallen into.
  When a page and a docstring disagree, the docstring is nearer the code and
  more likely right — and the page is a bug. Start at
  [Code map](code-map.md) to find the file, then read the file.
- **A measured number carries its method.** Where a page states a winrate, a
  frequency or a share, it also states the sample size, the corpus and the date.
  A number with no method behind it rots into folklore, and this project has
  reverted rules on the strength of numbers that turned out to be their own
  instrument's bug.
- **Session write-ups are append-only.** `docs/history/` records what was
  measured on a date, and it is not edited afterwards to match what is true
  today. When a finding is later closed or reversed, the newer page says so.
  Everything outside `history/` is expected to describe the present.
