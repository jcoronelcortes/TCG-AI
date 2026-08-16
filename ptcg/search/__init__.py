"""ptcg.search -- THE ROLLOUT SIDE of the play-time search plan (S2).

`fast_policy.py` is the rollout policy; `arbiter.py` consults rollouts on
close decisions. Rule R12 of `utils/lint_architecture.py` makes the package's
one hard constraint structural: NOTHING here may import `AGENT_STATE` or any
`ptcg.state` module, or call `main.agent` -- two independent oracles measured
that a stateful rollout policy drives BOTH seats out of one belief and can
invert the sign of a verdict (+32 pp to the wrong play in one of them).

The agent does NOT import this package yet: `utils/package_project.py`
includes packages by the AST of main.py's imports, so nothing here reaches
the submission until S0.1 is answered by the owner.
"""
