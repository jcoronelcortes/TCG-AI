"""The rollout policy: stateless, a few lines, and strictly better than random.

Phase S2 (docs/plan-la-busqueda-en-juego-2026-08-15.md §5.2). The obvious
candidate -- `main.agent` -- measured 43 ms per rollout and LOST to the random
policy on the sensitivity board, because it writes to `AGENT_STATE` (so a
rollout corrupts the belief of the real game that called it) and because
`search_oracle._choose` drives BOTH seats with the policy it is given (so our
agent pilots the opponent's deck too). Two oracles later measured the same
sign inversion from the opponent's rollout policy alone. Hence this module:
no imports of state, no module-level mutables, rule R12 enforced by the
linter.

What it plays, in order:
  1. an ATTACK option if the menu shows one (a rollout that never attacks
     never ends a game inside `max_steps`, and random ends turns instead);
  2. anything that is not END and not RETREAT, uniformly at random;
  3. END / RETREAT only when the menu offers nothing else.

Multi-pick menus (minCount/maxCount) fall back to a uniform legal sample,
exactly like `search_oracle._choose` -- error 4 of the engine is an arity
error and the bounds are honoured before anything else.

MEASURED (night of 16 August, sensitivity board of `search_oracle.self_test`,
K=100, noise floor 2 pp / 0.40 margin from two independent random batches):

  fast_policy on BOTH seats   11/100, margin -3.63  -> LOSES to random
  MIXED (ours fast, theirs
  random, `as_mixed_agent`)   42/100 vs 29/100, margin +0.19 vs -0.67
                              -> +13 pp and +0.86, both above the floor

The both-seats arm is the same defect the two oracles measured: the policy
helps THEIR seat more than ours. The arbiter therefore rolls `as_mixed_agent`
and never the symmetric form.
"""

OPTION_RETREAT = 12
OPTION_ATTACK = 13
OPTION_END = 14


def fast_policy(obs, rng):
    """One legal `select` (a list of option indices) for this observation."""
    select = obs.get("select") or {}
    options = select.get("option") or []
    n = len(options)
    if n == 0:
        return None
    lo = max(1, select.get("minCount") or 1)
    hi = min(n, select.get("maxCount") or 1)
    hi = max(lo, hi)
    if lo > 1 or hi > 1:
        return sorted(rng.sample(range(n), rng.randint(lo, hi)))

    attacks, middle, last_resort = [], [], []
    for idx, opt in enumerate(options):
        kind = opt.get("type")
        if kind == OPTION_ATTACK:
            attacks.append(idx)
        elif kind in (OPTION_END, OPTION_RETREAT):
            last_resort.append(idx)
        else:
            middle.append(idx)
    for pool in (attacks, middle, last_resort):
        if pool:
            return [rng.choice(pool)]
    return [rng.choice(range(n))]


def as_agent(rng):
    """Adapter for `search_oracle.rollout(policy="agent", agent=...)`.

    The returned callable closes over ITS OWN rng -- the module keeps no
    state, so two rollouts never share a generator unless the caller says so.
    ⚠️ This drives BOTH seats and measured WORSE than random (see the module
    docstring); it exists for experiments. Play-time code uses
    `as_mixed_agent`.
    """
    def agent(obs):
        return fast_policy(obs, rng)
    return agent


def as_mixed_agent(us, rng):
    """The measured configuration: OUR seat plays fast, theirs rolls random.

    `search_oracle._choose` calls the agent for every seat and falls back to
    a uniform legal sample when the callable raises -- raising on the
    opponent's turn IS the documented fallback channel, not a hack around it.
    """
    def agent(obs):
        if obs["current"]["yourIndex"] == us:
            return fast_policy(obs, rng)
        raise LookupError("their seat rolls random")
    return agent
