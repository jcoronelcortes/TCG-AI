"""The agent's brain, split by WHAT A MODULE IS ALLOWED TO TOUCH.

`main.py` is the entry point the competition calls; this package is everything
it decides with. The split is not by feature but by permission, and an
architecture linter (`utils/lint_architecture.py`) enforces it. Reading the
layers bottom-up is the fastest way in:

    cards/     DATA. Ids, groups, tables, score bands. No logic, no state.
    calc/      PURE READINGS. Damage, energy, probability, the board and the
               opponent. Takes what it needs as arguments; writes nothing.
    engine/    THE MACHINERY. The rule engine every decision is written in,
               the decision context, the attack plan.
    state/     WHAT PERSISTS. `AGENT_STATE` and the deck belief -- the only
               things here that survive between calls.
    decision/  PER-CARD DECISIONS. One module per hard card: Ultra Ball,
               Boss's Orders, Night Stretcher, the disruption pair...
    turn/      THE TURN ITSELF. The plan the prize count implies, the scoring
               of each menu option, and the final choice.

DEPENDENCIES POINT DOWNWARD ONLY. `calc/` may not import `decision/`; nothing
in `cards/` or `calc/` may touch mutable state (rule R2). That is what keeps
the readings reusable and the pure layers testable without staging a game.

THREE CONVENTIONS worth knowing before reading any single file:

  * A DECISION IS A LIST OF NAMED RULES, not an if/elif ladder -- see
    `ptcg/engine/rules.py`. Naming the rungs is what lets a census count them
    and a test assert on which rule decided.
  * A SCORER PRICES AN OPTION AND WRITES NOTHING (rule R9). Anything that has
    to survive belongs in `state/`.
  * COMMENTS EXPLAIN WHY, AND CITE THE GAME. Nearly every rule here exists
    because a specific game was lost without it, and the comment naming that
    game is the rule's evidence. A rule with no game behind it is a guess.

See docs/code-map.md for the same map in prose, and docs/project-history.md
for how the code got this shape.
"""
