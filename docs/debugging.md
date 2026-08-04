# Debugging a decision

[← Documentation index](README.md)

"The agent did something stupid on turn 12" is not actionable until you can
reproduce that exact decision on demand. This page is how.

## Step 1 — get the observation

You need the single observation where the bad decision was made. Three ways in:

**From a recorded game.** A game log is a JSON file with a list of steps; each
step holds one view per player. Take the item that is *active*, belongs to *our*
seat, and carries a decision request. Feed it to the agent.

> **Important:** replay only our own active frames. Passing the opponent's
> frames or inert ones through the agent pollutes its internal tracking, and the
> decision you reproduce will not be the one that happened.

**Per turn.** `python utils/split_turns.py` splits the single log in `log/` into
one record per turn under `registros/` — much easier to navigate than one
enormous file.

**Synthetically.** If the position is hypothetical, build it with the scenario
builder (`tests/state_builder.py`) instead of hand-editing JSON. It enforces
that the board is actually possible. See [Testing](testing.md).

## Step 2 — replay it

Replay a whole game and see, step by step, what the agent chooses versus what
was actually played:

```bash
PYTHONPATH="$PWD" python3 -m utils.log_replay log/<game-id>.json --verbose
```

Useful flags:

- `--max-items N` — stop after N actionable observations;
- `--verbose` — print each observation, the agent's decision and the recorded action;
- `--interactive` — step through with Enter, quit with `q`.

## Step 3 — see the scores

Set `PTCG_DEBUG` and the agent prints its ranking — the top options with their
scores — to standard error for every decision:

```bash
PTCG_DEBUG=1 PYTHONPATH="$PWD" python3 -m utils.log_replay log/<game-id>.json --verbose
```

That tells you *what outscored the play you expected*. From there, the rule to
inspect is the one that produced the winning score, in the branch for that
option type ([Code map](code-map.md)).

## Step 4 — check whether it was a veto or a preference

Two very different situations:

- **The play you wanted scored negative** → a veto fired. Find the flag that
  vetoes it; the interesting question is which matchup or which precondition
  turned it on.
- **The play you wanted scored positive but lower** → it lost on value or on
  play order. Ordering only reshuffles positively scored plays, so if the option
  never appears at the top, check the tier before touching the score.

## Step 5 — freeze it

Once reproduced, turn it into a test so it cannot come back: a fixture if the
board is real, a synthetic scenario if it is not. See [Testing](testing.md).

---

## Notes that save time

- **Many scoring rules cite the game ID that motivated them** in their comments.
  When you touch a branch, searching for that ID tells you what the rule was
  protecting — and whether your change re-opens it.
- **`registros/` and `log/` are throwaway data** (git-ignored). They get
  replaced whenever new games are analysed, which is why the golden corpus
  stores hashes and can regenerate itself.
- **Patching for tests:** several names are bound in more than one module, so
  patching one module does not reach the others. `tests/patching.py` sets a name
  everywhere it is bound, which keeps tests working even when code moves
  between modules.

---

Next: [Testing](testing.md) · [Tools](tools.md) · [How the agent thinks](how-the-agent-thinks.md)
