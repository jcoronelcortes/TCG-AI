"""ptcg.opponent -- WHO WE ARE PLAYING: a posterior over the real lists.

Phase S1 of the play-time search plan (docs/plan-la-busqueda-en-juego-2026-08-15.md).
One module, `prior.py`, and it is pure dict-reading Python: no engine import,
no `AGENT_STATE`, no `main`. The agent does NOT import this package yet --
`utils/package_project.py` includes packages by the AST of main.py's imports,
so nothing here reaches the submission until S0.1 is answered by the owner.
"""
