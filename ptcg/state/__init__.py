"""WHAT SURVIVES between calls to `agent()`. The only mutable layer.

    agent_state.py  `AGENT_STATE`: the one state object, and its `reset()`
    tracking.py     the deck belief -- where each of our 60 cards is
    logs.py         turning the observation's log stream into belief moves
    zones.py        the five zones a card can be in

ONE OBJECT, NEVER REASSIGNED. `AGENT_STATE` is a singleton whose FIELDS change;
the object itself is never replaced. That is not a style choice --
`from ... import ko_last_turn` binds a COPY, so a module importing a loose
mutable keeps reading the value it had at import time. It raises nothing and
fails no test; the agent simply decides badly in a real game. Rule R1 of the
architecture lint watches for it, and it has already caught the same trap twice
with names that were not even meant to be state.

ONE RESET. `AgentState.reset()` is the single definition of a fresh game.
Hand-written copies of it in the test fixtures used to drift every time a new
field was born.
"""
