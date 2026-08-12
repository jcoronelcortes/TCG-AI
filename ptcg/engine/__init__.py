"""THE MACHINERY every decision is expressed in.

Not game rules -- the shapes the agent's own reasoning is written in.

    rules.py    the rule engine: named rules, adjustments, and the two
                resolvers (first-match CHAIN and ARGMAX). Read this first;
                the whole `decision/` layer is written in its vocabulary.
    context.py  `DecisionContext`, the read-only snapshot of the turn that
                every card scorer receives.
    plan.py     `AttackPlan`, the attack the turn has settled on, decided once
                and read by every later phase.
    debug.py    the `PTCG_DEBUG` decision dump.

The point of `rules.py` is auditability. An if/elif ladder answers "what
score"; a list of named rules also answers "WHICH RULE", and every measurement
tool in this repository -- the rule census, the trace, the tier-inversion
audits -- depends on that second answer.
"""
