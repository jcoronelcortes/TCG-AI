# Project history

[← Documentation index](README.md)

Why the code is shaped the way it is. Read this before making a structural
change — most of the constraints here look arbitrary until you know what they
cost.

## The agent used to be one file

The whole agent lived in `main.py`: about 25,000 lines, of which a single
function accounted for 15,000. It worked, and it scored well, but changing how
one kind of play was scored meant navigating a thousand-line branch inside a
fifteen-thousand-line function.

In August 2026 it was split into the `ptcg/` package. `main.py` kept the entry
point, board setup, opponent identification, the decision flags and post-knockout
promotion; everything else moved out into modules grouped by responsibility
(data, calculators, state, per-card decisions, turn phases).

**The refactor changed no decisions.** It was verified by a shadow harness that
played self-play with the old version and asked the new one for the same
observation: over 90,000 decisions, zero differences. The submissions built from
it scored the same as the original.

## What did not move

One large block inside the entry point resisted extraction: pulling it out
produced a real behaviour change, not a mechanical seam. It was reverted rather
than forced. If you pick this up, the unexplored path is to use the shadow
harness's flips — which name the exact turn and step — to localise the
divergence, instead of starting from the tests that fail.

## The lessons that shaped the constraints

These are the ones that cost real time, and each of them is now enforced by a
lint rule or a test.

**1. The competition container executes the agent file, it does not import it.**
The loader compiles the file, runs it in an empty namespace with the directory
on the path *only* during that run, and keeps the **last callable** in the
namespace. Consequences: the agent entry point must be the last thing defined,
nothing may bind a callable after it (a class counts), no submodule can import
the agent module back, and every package import must happen up front — a package
imported for the first time mid-game is a crash mid-battle. Covered by the
submission smoke test.

**2. A table can be state in disguise.** The attack-cost table looked like a
constant, was read from dozens of places, and was quietly rewritten every turn
by a stadium effect. It never appeared in any global declaration, because
mutating a dictionary does not require one. The constant part now lives with the
data; the part that changes lives with the state.

**3. Importing a name binds a copy.** `from module import value` does not create
a view — when the original is reassigned, the importer keeps reading the old
one. Silently. This broke tests three times during the refactor and is the
reason all cross-turn state lives in a single object that is never reassigned,
and the reason there is a helper that patches a name everywhere it is bound.

**4. The measuring harness can break too.** The self-play gate loaded two agents
that ended up sharing state through the module registry, and reported dozens of
phantom differences. When a gate reports something surprising, suspect the gate.

**5. Closures do not see the enclosing scope wholesale.** Python only creates
cells for names a function actually references, so extracting a nested function
means writing its captured names out explicitly, one by one.

**6. Variables bound on only some branches** have to be written back only if
they ended up bound. Passing them as ordinary arguments invents errors on paths
the original never took.

**7. A green test proves nothing until it can fail.** Every safety net was
validated by injecting the bug and confirming it went red.

## The measurement discipline

Alongside the refactor, the project built a set of gates that now define how any
strategy change is judged: unit tests, a golden corpus of past decisions,
self-play winrate, and a matchup matrix against real leaderboard lists. The
policy that came out of it is short:

- measure whether the **decision** changed before measuring winrate;
- a neutral result gets reverted, unless it fixes a demonstrably wrong value;
- confirm the opponent can actually execute the mechanism you are testing.

See [Improving the agent](improving-the-agent.md).

## Where the older documentation went

This documentation set replaces a much larger Spanish one that described the
code region by region, with line ranges. It was accurate when written and stale
soon after. It remains in the repository's git history if you ever need it; the
strategy it described is unchanged and is summarised in
[Strategy](strategy.md).

---

Next: [Improving the agent](improving-the-agent.md) · [Code map](code-map.md)
