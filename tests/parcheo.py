"""Patching agent names that live spread between `main` and `ptcg/`.

THE PROBLEM
  `from ptcg.cartas.tablas import card_table` BINDS THE NAME IN THE MODULE THAT
  IMPORTS IT. It is not a view of the original variable: it is another reference. When
  main.py does `import *`, it takes its own copy; and thirteen modules of `ptcg/`
  have theirs. That is why `monkeypatch.setattr(m, "card_table", ...)` stops
  reaching `_our_effective_damage` as soon as that function moves to
  `ptcg/calculo/dano.py`: the function reads the binding of ITS module.

  It is not a production problem -- there nobody reassigns these names -- but a problem
  for the tests, which inject doubles to isolate a case.

THE SOLUTION
  `parchear()` sets the name in ALL the loaded modules that have it, so
  the test does not need to know where the function that consumes it lives. That makes
  it immune to the refactor waves still to come: moving a function from one
  module no longer breaks the test that isolated it.

  For mutable state it is NOT needed: it lives in `ESTADO`, which is an object and is
  never reassigned (see ptcg/estado/agente.py).
"""

import sys
from contextlib import contextmanager


def _agent_modules():
    for mod in list(sys.modules.values()):
        if mod is None:
            continue
        name = getattr(mod, "__name__", "")
        if name == "main" or name == "ptcg" or name.startswith("ptcg."):
            yield mod


def patch_name(monkeypatch, name, value):
    """Sets `nombre = valor` in every agent module that has it.

    It returns how many modules were touched; 0 means the name does not exist in
    any of them, almost always a typo in the test.
    """
    tocados = 0
    for mod in _agent_modules():
        if hasattr(mod, name):
            monkeypatch.setattr(mod, name, value, raising=False)
            tocados += 1
    return tocados


@contextmanager
def parcheado(name, value):
    """Like `parchear`, but without `monkeypatch` and as a context manager.

    For the tests that install a spy by hand with try/finally:

        with parcheado("_debug_log_decision", espia):
            m.agent(obs)
    """
    previos = [(mod, getattr(mod, name))
               for mod in _agent_modules() if hasattr(mod, name)]
    for mod, _ in previos:
        setattr(mod, name, value)
    try:
        yield len(previos)
    finally:
        for mod, viejo in previos:
            setattr(mod, name, viejo)


def instalar(name, value):
    """Sets `nombre = valor` in every module and returns the restorer.

    A variant for the tests that already have their try/finally set up: it replaces the
    assignment and the restoration line by line, without restructuring the test.

        _restaurar = instalar("_debug_log_decision", espia)
        try:
            m.agent(obs)
        finally:
            _restaurar()
    """
    previos = [(mod, getattr(mod, name))
               for mod in _agent_modules() if hasattr(mod, name)]
    for mod, _ in previos:
        setattr(mod, name, value)

    def restaurar():
        for mod, viejo in previos:
            setattr(mod, name, viejo)
    return restaurar
