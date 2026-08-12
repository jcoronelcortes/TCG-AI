"""Loading the locally built engine, and refusing to trust it blindly.

Phase B of `docs/engine-source-plan-2026-08-12.md`. The shipped `cg/libcg.*`
cannot replay a game: `ApiBattleStart` sets `deviceRand = true`, so every
shuffle and both coin paths draw from a fresh `std::random_device` and the seed
in `GameConfig` is ignored. The local build (see `cg/build_local_engine.sh`)
adds `BattleStartSeeded` and honours the seed.

**This module is for TOOLS ONLY.** The submission runs on the official binaries;
nothing under `main.py` or `ptcg/` may import this, and rule R11 of
`utils/lint_architecture.py` fails the build if it does.

## The drift guard

A locally built engine that quietly diverged from the official one would make
every local measurement lie, and nothing would look wrong -- risk R2 of the
plan, and the reason `verify()` exists and `load()` calls it.

The check is that both libraries report **the same card and attack tables**.
Measured 12 August 2026, they do: `AllCard()` is 459 888 bytes with SHA-256
`d7e29c62...` from both. It is cheap (one call each) and it runs on every load,
because a check that only runs when someone remembers is not a guard.

What it does NOT prove: that the *rules* are identical. It proves the data is,
and the patch is 53 lines that touch only how randomness is drawn. Anything
larger than that needs a real differential run, not this.
"""

import argparse
import ctypes
import hashlib
import platform
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

_LIB = None


class EngineDriftError(RuntimeError):
    """The local build does not agree with the shipped engine. Do not use it."""


def library_path():
    ext = {"Darwin": "dylib", "Windows": "dll"}.get(platform.system(), "so")
    return _ROOT / "cg" / "build" / f"libcg_local.{ext}"


def _declare(lib):
    from cg.sim import SerialData, StartData
    lib.GameInitialize.restype = None
    lib.BattleStart.restype = StartData
    lib.BattleStart.argtypes = [ctypes.POINTER(ctypes.c_int)]
    lib.BattleStartSeeded.restype = StartData
    lib.BattleStartSeeded.argtypes = [ctypes.POINTER(ctypes.c_int),
                                      ctypes.c_uint]
    lib.BattleFinish.argtypes = [ctypes.c_void_p]
    lib.GetBattleData.restype = SerialData
    lib.GetBattleData.argtypes = [ctypes.c_void_p]
    lib.Select.restype = ctypes.c_int
    lib.Select.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_int),
                           ctypes.c_int]
    lib.AllCard.restype = ctypes.c_char_p
    lib.AllAttack.restype = ctypes.c_char_p
    lib._tcgai_seeded_ready = True


def _tables(lib):
    """(sha256 of AllCard, sha256 of AllAttack, byte lengths)."""
    card = lib.AllCard()
    attack = lib.AllAttack()
    return (hashlib.sha256(card).hexdigest(),
            hashlib.sha256(attack).hexdigest(),
            (len(card), len(attack)))


def verify(lib=None):
    """Raises EngineDriftError unless the local tables match the shipped ones.

    Returns the shared (card_sha, attack_sha, lengths) when they agree.
    """
    from cg import sim
    lib = lib or load(verify=False)
    shipped = _tables(sim.lib)
    local = _tables(lib)
    if shipped != local:
        raise EngineDriftError(
            "the local engine does not match the shipped one -- every "
            "measurement taken with it would be wrong.\n"
            f"  shipped: AllCard {shipped[0][:16]} ({shipped[2][0]} B), "
            f"AllAttack {shipped[1][:16]} ({shipped[2][1]} B)\n"
            f"  local:   AllCard {local[0][:16]} ({local[2][0]} B), "
            f"AllAttack {local[1][:16]} ({local[2][1]} B)\n"
            "Rebuild with cg/build_local_engine.sh against the same engine "
            "package the binaries came from.")
    return local


def load(check=True):
    """Loads (once) the local engine and returns its ctypes handle."""
    global _LIB
    if _LIB is not None:
        return _LIB
    path = library_path()
    if not path.exists():
        raise FileNotFoundError(
            f"the local engine is not built: {path}\n"
            "Run cg/build_local_engine.sh (it needs the engine source in "
            "ptcg_engine/, which is deliberately not in the repository).")
    lib = ctypes.cdll.LoadLibrary(str(path))
    lib.GameInitialize()  # its own card tables; separate from the shipped lib's
    _declare(lib)
    _LIB = lib
    if check:
        verify(lib)
    return lib


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--verify", action="store_true",
                    help="(default) check the local build against the shipped "
                         "engine")
    ap.parse_args(argv)
    try:
        lib = load(check=False)
    except FileNotFoundError as e:
        print(f"NO CONSTRUIDO: {e}")
        return 1
    print(f"Motor local: {library_path()}")
    try:
        card, attack, lengths = verify(lib)
    except EngineDriftError as e:
        print(f"DERIVA DETECTADA\n{e}")
        return 2
    print(f"  AllCard   sha256 {card[:16]}  ({lengths[0]} bytes)")
    print(f"  AllAttack sha256 {attack[:16]}  ({lengths[1]} bytes)")
    print("  coincide con el motor enviado: se puede medir con el")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
