# Tools

[← Documentation index](README.md)

Everything in `utils/` is a command-line tool. None of them are needed to *run*
the agent — they exist to measure it, feed it opponents, debug it and ship it.
Flags and identifiers are in English; a few stored data fields are still Spanish, and the last section says which and why.

Run them from the repository root.

---

## Play games and measure

### `selfplay.py` — the winrate gate

Plays full games with the local simulator. This is the gate that answers the one
question no unit test can: **does this change win more games?**

```bash
python utils/selfplay.py --games 100                      # mirror: sanity check, expect ~50%
python utils/selfplay.py --games 200 --base HEAD~1        # candidate vs. a previous version
python utils/selfplay.py --games 200 --opponent deck/real_opponents/crustle_wall_2.csv
python utils/selfplay.py --games 200 --opponent ... --base HEAD~1   # matchup delta
```

It loads two independent copies of the agent so their internal tracking never
mixes, and alternates seats between games, because the simulator's shuffles and
coin flips cannot be seeded. Output: score, winrate with a 95% confidence
interval, and the split by seat.

### `matchup_matrix.py` — the matchup matrix

Plays N games against **every** opponent deck in a folder and prints the table
from weakest matchup to strongest, with confidence intervals and forfeits.

```bash
python utils/matchup_matrix.py --games 400 --weights
python utils/matchup_matrix.py --games 200 --base <git-ref>   # per-matchup delta
```

By default it measures against the real leaderboard lists in
`deck/real_opponents/`. `--weights` weights each list by how often it actually
appears, which turns the average into an expected ladder winrate. The synthetic
decks in `deck/opponents/` are still there but are no longer the default: many of
them are archetypes that do not exist in the current meta, and measuring against
them spent half the budget on imaginary opponents. They remain useful for
exercising **mechanics** the real meta does not offer (item lock, mill).

### `opponent_bot.py` — the reference opponent

The generic bot that pilots any deck legally and consistently. It is not a good
player and does not try to be: because its policy is fixed and deterministic,
the **difference** between two versions of our agent against it is signal, even
though the bot's absolute level is not.

---

## Understand losses

### `autopsy.py` — automatic autopsy of losses

Plays N games, records the decision stream of the ones we lost, and runs
detectors over them: a lethal attack that was available and never taken, and
sterile turns (ended with a full hand and no damage). Each loss is classified by
how we lost — prizes, bench-out, deck-out.

```bash
python utils/autopsy.py --opponent deck/real_opponents/<deck>.csv --games 40
python utils/autopsy.py --census ...        # census with a control group
```

**40 games collects records; it does not compare matchups.** At that size the
winrate swings enormously: two 60-game runs on a matched pair of Crustle lists
reported 83.3% and 81.7% — the same, to the eye — where the truth was 69.5% and
85.0%, and both errors happened to point the wrong way at once. Raised to 200
games both landed on the matrix's figure. Use the default to gather losses to
read; if the number itself is the finding, it needs 200+ or the matchup matrix.

### `collision_radar.py` — collisions between matchup rules

Finds the failure class nothing else finds: a veto written for one matchup that
kills a play another matchup requires. It defines deck-agnostic situations and
measures how often we resolve each one per opponent. A resolution rate that
collapses for a single deck points at the flag to inspect.

### `turn_explorer.py` — exhaustive turn explorer

Enumerates every legal sequence of **our** actions for one turn, evaluates the
resulting board, and reports the dominant line. If the agent's line is
dominated, you have a new scenario with the correct play already computed. It
models our turn only (no draws, no opponent branching) — that limit is
deliberate and documented in the script.

### `turn_waste_census.py` — is there anything to write a rule about?

Counts, per turn and per plan mode, the resources that were **legally playable
in the menu** and were declined: the turn's energy attachment, the Supporter
slot, an evolution, a body for the bench, an ability. It runs one step earlier
than every other tool here — before asking whether a rule would change a
decision, it asks whether the behaviour the rule would fix happens at all.

The first run (250 games) came back negative, and that answer is the point: the
agent is not leaving resources unspent, so the remaining ground is in *which*
legal play it picks, not in what it fails to spend. The script's docstring
carries the numbers.

```bash
python utils/turn_waste_census.py --games 250 --detail
```

### `wall_probe.py` — the immune-wall probe

Answers one specific question per turn: when our ex is blocked by an immune wall
and a non-ex answer is already charged on the bench, how does the turn end? Dry
turns are dumped as replayable observations.

**Read the dumps.** They are the point of the tool, not a side effect. Twenty-two
dry turns against `crustle_wall_6` shared one shape -- our active at zero energy
with no retreat in the menu while a charged Tapu Bulu sat on the bench -- and one
of them (`seco_019`) turned out to be a lethal line the agent could see and was
outbid on. That is the band-ordering bug of `_attach_enable_retreat_ko`.

### `healing_census.py` — how much of our damage gets healed away

Follows every opposing body by serial and separates the hit points we take off it
from the ones a card puts back. The number that matters is the ratio: damage that
never became a prize.

```bash
python utils/healing_census.py --opponent deck/real_opponents/crustle_wall_6.csv
```

Fifty-five of the ninety-seven real lists carry healing and the agent reads none
of it. Against `crustle_wall_6` -- the worst matchup in the matrix --
**83% of the damage we deal is healed back**; against `crustle_wall_2`, 44%;
against Marnie, 26%; in the mirror, 0%, which is the method's noise floor.

### `promoted_reply_census.py` — is a rule worth writing?

The shape every candidate rule should be put through before it is written: count
the nested populations, from "the situation happens" down to "and we had a choice
about it". It was built for one question (when our attack knocks their active
out, does the body they promote reply?) and its answer was to NOT write the rule:
the actionable population is 0.08% of decisions.

### `permutation_probe.py` — does the menu's order decide?

Plays games with two agent instances: the driver sees the real menu, the shadow
sees the same board with the options shuffled, and their choices are compared as
PLAYS rather than as indexes. Any difference is a decision the rules did not
make. Currently **0.56%** of decisions, most of them ties over which card a
search brings back.

### `mutation_probe.py` — which safety nets can actually fail?

Rewrites one expression at a time (comparisons, small integer boundaries, boolean
operators, `not`) and runs the suite against each mutant. A SURVIVOR is a line no
test is watching.

```bash
python utils/mutation_probe.py ptcg/calc/damage.py --lines 560-600
python utils/mutation_probe.py --changed HEAD~3     # only the lines a diff added
```

It edits the file in place -- the suite imports the agent from the tree -- and
restores it on exit, on exception and on a kill. `--changed` is the mode worth
using: it asks whether the test you just wrote watches the code you just wrote.

---

## Opponent decks

| Tool | Purpose |
| --- | --- |
| `download_competitor_decks.py` | Downloads the exact 60-card lists of the top leaderboard competitors from their public replays. Resumable. `--top 100` |
| `real_opponents.py` | Turns those lists into *measurable* opponents: deduplicates them (300 decks are ~93 unique lists), keeps each one's meta weight, and screens out lists the generic bot cannot pilot — an unpilotable list measures the bot getting stuck, not the matchup, and returns a falsely high winrate. It also marks the lists that are near-copies of our own 60 (`solape_propio` in `pesos.csv`): the bot pilots those legally but pilots *our* engine, badly, so they read as a matchup we dominate. They are kept, because people play them, and flagged so the aggregation can report the field with and without. |
| `build_meta_decks.py` | Hand-built synthetic archetype decks, for mechanics the real meta does not currently offer. |
| `harvest_opponent_deck.py` | Rebuilds a plausible 60-card opponent list from what was visible in local game records. |
| `op_scaling_census.py` | Audits `ptcg/cards/op_scaling.py` against every opposing deck in the repo: which attacks scale with the board rather than doing their printed damage, which of them the agent reads, and which are missing. The suite runs it as a gate — a new deck that brings an unread one is invisible in a game, because the agent does not crash, it just walks into the hit. `--unmodelled` |

---

## Reproduce and debug

| Tool | Purpose |
| --- | --- |
| `log_replay.py` | Replays a recorded game through the agent and compares its choices with what was actually played. `--verbose`, `--interactive`, `--max-items N` |
| `split_turns.py` | Splits a game log into one record per turn, into `records/`. Takes no arguments. |
| `record_corpus.py` | Records fresh games against the real leaderboard decks, in the same format, so the golden corpus can be regenerated without depending on downloaded replays. |

See [Debugging a decision](debugging.md) for how these fit together.

---

## Ship it

### `package_project.py`

Builds `submission.tar.gz` with `main.py`, `deck.csv` and the local packages
that `main.py` imports. The package list is **derived from the imports**, so a
new package is included the moment the agent imports it — nobody has to remember
to update the script. Forgetting one is the most expensive possible mistake: the
submission starts broken in the competition with every local test green.

---

## Architecture and refactoring

These exist because of the large refactor described in
[Project history](project-history.md). They are still useful when moving code.

| Tool | Purpose |
| --- | --- |
| `lint_architecture.py` | Four architecture rules, checked by the test suite. They cover failures that do **not** show up as a red test: importing a mutable by name (freezes a stale copy), data modules touching state, anything bound after the agent entry point (breaks the competition loader), and eager imports that break the container. |
| `purity.py` | Proves which definitions can be moved out of `main.py` without touching mutable state. |
| `extract_pure.py` / `extract_definitions.py` | Move constants and definitions into package modules, carrying their comments with them. |
| `migrate_state.py` | Rewrites module-level state into fields of the state object, editing text in place so comments survive. |
| `shadow.py` | The equivalence gate: plays self-play with the old version and asks the new one for the same observation. Any different choice is a flip. |

---

## Assets

| Tool | Purpose |
| --- | --- |
| `deck/render_deck_image.py` | Renders `deck/deck_en.jpg` from `deck.csv` and the official card data. Needs the optional render dependencies. |

---

Next: [Testing](testing.md) · [Debugging a decision](debugging.md)

## Flag names: what changed

The command line used to be in Spanish. It is not any more, and there are no
aliases: an old invocation fails with argparse's own error. The mapping, for
commands you may have written down:

| Old | New |
|---|---|
| `--partidas` | `--games` |
| `--rival` | `--opponent` |
| `--rivales` | `--opponents` |
| `--pesos` | `--weights` |
| `--espejo` | `--mirror` |
| `--censo` | `--census` |
| `--todos` | `--all` |
| `--candidato` | `--candidate` |
| `--control-carta` | `--control-card` |
| `--sin-criba` | `--no-filter` |
| `--salida` | `--output` |
| `--destino` | `--target` |
| `--origen` | `--source` |
| `--actualizar` | `--update` |
| `--aplicar` | `--apply` |
| `--volcar` | `--dump` |
| `--desde` / `--hasta` | `--from-line` / `--to-line` |

`tests/test_cli.py` keeps it that way: it fails if a script offers a Spanish
flag again, and if any `args.X` a script reads is not a `dest` its parser
declares.

## What is still Spanish, and why

The identifiers are done: four batches renamed them with
`utils/rename_code.py`, which proves against git that **only** the mapped names
moved. What is left is **stored data**, and it is left on purpose:

- the finding fields the tools write and read — `turno`, `hallazgos`,
  `detector`, `detalle`, `modo_derrota` — carried by the 900+ files under
  `records/` and by the golden decisions;
- the `pesos.csv` columns — `archivo`, `arquetipo`, `peso_meta`,
  `solape_propio`, `motivo`.

Renaming a stored field is not a rename, it is a migration: every file already
written keeps the old spelling, and the reader that stops accepting it breaks
silently. That is not hypothetical — it is what left `turn_explorer.py`
crashing on every real finding until it was fixed. When these do move, they
move with a converter for the existing records and a reader that accepts both
spellings, with the golden corpus as the witness.

Two rules that come out of doing the batches:

- **Run `rename_code.py` on Python 3.12 or newer.** Below that a whole
  f-string is one token, so `f"{old_name}"` survives the rename while the
  assignment above it does not. The tool now refuses to start.
- **Screen the map for collisions first.** The AST proof shows that nothing but
  names changed; it cannot show that two different symbols were not merged into
  one. Check every target against the names already present in the files the
  source appears in.
