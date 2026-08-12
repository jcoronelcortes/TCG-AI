"""THE PHASES OF A TURN: what used to be the body of `agent()`.

Every call to `agent()` answers ONE MENU. The engine offers a list of options
and we return an index. Everything in this package exists to turn a board into
that index.

THE PIPELINE, in the order main.py runs it:

    game_plan.py      WHAT IS THIS TURN FOR? Decided FIRST, from the prize
                      count: WIN_NOW / DENY / RACE / DEVELOP. Everything below
                      reads it.
    supporters.py     which Supporter is worth the turn's single slot
    energy.py         which body the turn's energy should go to
    ctx_scoring.py    `ScoringCtx` -- built ONCE, before the option loop
    scoring.py        dispatch each option to its branch, by `OptionType`
    options/          one module per branch: card, play, retreat, ability,
                      attach, evolve, attack, minor
    ctx.py            `TurnCtx` -- what the tail still needs afterwards
    finalize.py       order the scored options by TIER and pick one

WHY THE TURN PLAN COMES FIRST. Every "does this win?" flag already existed, but
each lived alone and was consulted by whichever rule remembered it. Nothing put
the prize count in front of the turn and asked, once and before the first
decision, whether the game can be CLOSED today. Without that, a perfectly sound
ordering rule ("play the resource card before the gust") vetoed a winning play.
`game_plan.py` carries the game that cost, and its `mode` is the sentence the
rest of the turn reads.

TIERS BEAT SCORES. `finalize.py` does not simply take the highest number: it
groups options into tiers and picks within the winning one. A tier is a claim
about KIND -- "attacking to win outranks everything" -- and it exists so a
carefully tuned score in a lesser category can never outbid a decisive action.

THE CONTEXT OBJECTS AND WHY THEY LOOK ODD. `agent()` was a single enormous
function whose phases talked through local variables; splitting it meant giving
those variables an explicit home. `ScoringCtx` and `TurnCtx` are those homes,
and main.py fills them from `locals()` rather than by keyword. That is
deliberate: some of these names are only bound on certain paths, and passing
them explicitly would force their evaluation and raise on exactly the paths
where the original code never read them. Unbound stays None, guarded as before.

Each option branch UNPACKS only the fields it reads and RETURNS only the ones
it reassigns -- equivalent to the single write-back of the original loop, since
a branch that does not touch a field leaves it alone.

A branch may return the `_SALTAR` sentinel (`scoring_sentinel.py`) to mean "I
already appended my own score" -- what used to be a `continue`.
"""
