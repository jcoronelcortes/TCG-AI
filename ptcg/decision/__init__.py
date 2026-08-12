"""ONE MODULE PER HARD CARD. Should we play it, and what do we aim it at?

    ultra_ball.py       the two-card search: when to hold it, what it costs,
                        what it fetches. The largest module in the package.
    boss_orders.py      drag a benched Pokemon out: the prize, the trap, the
                        unlock -- and the free retreat it gives them
    night_stretcher.py  recover a body or an energy from the discard
    disruption.py       Xerosic's Machinations and Unfair Stamp, together
                        because their ordering rule makes each consult the other
    meowth.py           a 2-prize body benched to fetch one Supporter
    poke_pad.py         the free search, limited to non-Rule-Box Pokemon
    supporters.py       Dawn, Lana's Aid, and the deck-as-a-clock reading
    bug_catching_set.py look at seven cards; mostly a question of odds
    stadiums.py         Forest of Vitality and the Grand Tree engine

THE SHAPE THEY SHARE (see `ptcg/engine/rules.py`): a `_ctx_<topic>` function
builds a small context holding only what this decision may read, `_v_<topic>_*`
functions price the candidates, and `_RULES_<TOPIC>` orders the rungs with
`_ADJUST_<TOPIC>` correcting afterwards. Narrow contexts are what make these
testable -- a unit test builds one by hand instead of staging a whole game.

TWO RECURRING TRAPS, both of which cost real games and are worth recognising
before adding anything here:

  * PLAYING A CARD AND RESOLVING IT ARE DIFFERENT MENUS. The board changes in
    between, so a condition that justified the play may be unreadable by the
    time the search resolves. Intentions that must cross that gap are written
    on `AGENT_STATE` and reset every turn.
  * ONLY ONE SUPPORTER PER TURN. Every Supporter scorer is really bidding for
    the same slot, which is why they share one value scale and why so many
    rules read "yields to X" -- and why those yields must not override a turn
    that ends the game (`ptcg/turn/game_plan.py`).
"""
