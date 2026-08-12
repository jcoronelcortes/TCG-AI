"""A battle as an OBJECT, so a process can run more than one at a time.

`cg/game.py` keeps the whole battle in module state: `Battle.battle_ptr` in
`cg/sim.py` is a class attribute, so `battle_start` overwrites whatever battle
was already running. That is a limit of the PYTHON WRAPPER, not of the engine --
measured 12 August 2026: two `BattleStart` calls return two distinct
`battlePtr`, and the two games play interleaved without interfering. Every C
entry point already takes the pointer as its first argument; only Python was
holding it in a global.

This module adds the handle without touching `cg/game.py`, which some twenty
tools and tests import. Nothing here changes what the engine does; it changes
who owns the pointer.

    from cg.battle import Battle

    with Battle(deck0, deck1) as b:
        while b.result == -1:
            b.select(agent(b.obs))
        winner = b.result

`lib` defaults to the shipped engine that `cg/sim.py` loads. Tools that want the
locally built one pass it explicitly (see `utils/local_engine.py`); the agent
never does, and rule R11 of `utils/lint_architecture.py` enforces that.

`seed` requires an engine exporting `BattleStartSeeded` -- the local build only.
Passing it to the shipped engine raises, rather than silently playing an
unseeded game and reporting it as reproducible.
"""

import ctypes
import json

MAX_STEPS = 3000


def _shipped_lib():
    """The engine `cg.sim` currently holds -- resolved late, on purpose.

    `from .sim import lib` would bind a COPY of the name at import time
    ([[from-import-liga-una-copia-no-una-vista]]), and `cg.sim.lib` is not
    stable: `tests/test_cg_sim.py` reimports the module with a fake library to
    check the per-platform path selection. A module that captured `lib` early
    would keep whichever object happened to be there when it was first
    imported, and would silently play its games against a stub.
    """
    from . import sim
    return sim.lib


class BattleError(RuntimeError):
    """battle_start refused the decks, or a selection was rejected."""


def _prototypes(lib):
    """Declares the seeded entry point on a lib that has it. Idempotent."""
    if getattr(lib, "_tcgai_seeded_ready", False):
        return
    try:
        fn = lib.BattleStartSeeded
    except AttributeError:
        return
    from .sim import StartData
    fn.restype = StartData
    fn.argtypes = [ctypes.POINTER(ctypes.c_int), ctypes.c_uint]
    lib._tcgai_seeded_ready = True


class Battle:
    """One battle, owning its own engine pointer.

    The handle is single-use: after `finish()` it cannot be restarted, because
    the engine frees the state and the pointer becomes dangling. Build a new
    handle per game -- that is what the pool in `utils/parallel.py` does.
    """

    def __init__(self, deck0, deck1, seed=None, lib=None, autostart=True):
        if len(deck0) != 60 or len(deck1) != 60:
            raise ValueError("The deck must contain 60 cards.")
        self.lib = lib if lib is not None else _shipped_lib()
        self.seed = seed
        self.ptr = None
        self.obs = None
        self.start_data = None
        self._deck0 = list(deck0)
        self._deck1 = list(deck1)
        if autostart:
            self.start()

    # -- lifecycle ---------------------------------------------------------

    def start(self):
        if self.ptr is not None:
            raise BattleError("this battle has already been started")
        cards = self._deck0 + self._deck1
        arg = (ctypes.c_int * len(cards))(*cards)
        if self.seed is None:
            sd = self.lib.BattleStart(arg)
        else:
            _prototypes(self.lib)
            if not getattr(self.lib, "_tcgai_seeded_ready", False):
                raise BattleError(
                    "this engine does not export BattleStartSeeded: it cannot "
                    "play a reproducible game. Build the local engine with "
                    "cg/build_local_engine.sh and pass its lib.")
            if not 0 < int(self.seed) < 2 ** 32:
                # seed 0 means "roll one" inside the engine, which would make an
                # unseeded game look seeded.
                raise ValueError("seed must be in 1..2**32-1")
            sd = self.lib.BattleStartSeeded(arg, ctypes.c_uint(int(self.seed)))
        self.start_data = sd
        if not sd.battlePtr:
            raise BattleError(
                f"battle_start refused the decks: errorPlayer={sd.errorPlayer} "
                f"errorType={sd.errorType}")
        self.ptr = sd.battlePtr
        self._read()
        return self

    def finish(self):
        """Frees the engine-side state. Safe to call twice."""
        if self.ptr is not None:
            self.lib.BattleFinish(self.ptr)
            self.ptr = None

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.finish()
        return False

    # -- playing -----------------------------------------------------------

    def _read(self):
        sd = self.lib.GetBattleData(self.ptr)
        self.obs = json.loads(sd.json.decode())
        self.obs["search_begin_input"] = ctypes.string_at(
            sd.data, sd.count).decode("ascii")
        return self.obs

    def select(self, select_list):
        """Submits a choice and returns the next observation."""
        if self.ptr is None:
            raise BattleError("this battle is finished")
        if (not isinstance(select_list, list)
                or not all(isinstance(i, int) for i in select_list)):
            raise ValueError("select_list is not list[int]")
        arg = (ctypes.c_int * len(select_list))(*select_list)
        err = self.lib.Select(self.ptr, arg, len(select_list))
        if err != 0:
            if err == 30:
                raise BattleError("battle_ptr broken.")
            raise IndexError(f"the engine rejected the selection (err={err})")
        return self._read()

    # -- reading -----------------------------------------------------------

    @property
    def result(self):
        """-1 while the game is running, otherwise the winning seat."""
        return self.obs["current"]["result"]

    @property
    def your_index(self):
        return self.obs["current"]["yourIndex"]

    @property
    def first_player(self):
        return self.obs["current"]["firstPlayer"]

    def prizes_left(self):
        """Prizes each seat has LEFT, or None if they cannot be read."""
        try:
            players = self.obs["current"]["players"]
            return [len(players[i].get("prize") or []) for i in (0, 1)]
        except (KeyError, IndexError, TypeError):
            return None
