import ctypes
import importlib
import platform
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


class FakeLib:
    def __init__(self):
        self.calls = []

    def GameInitialize(self):
        self.calls.append("GameInitialize")

    def __getattr__(self, name):
        def _(*args, **kwargs):
            self.calls.append(name)
            return None

        return _


@pytest.mark.parametrize(
    ("system_name", "machine_name", "expected_suffix"),
    [
        ("Darwin", "x86_64", "libcg.dylib"),
        ("Windows", "x86_64", "cg.dll"),
        ("Linux", "aarch64", "libcg-arm64.so"),
        ("Linux", "x86_64", "libcg.so"),
    ],
)
def test_sim_selects_expected_library_path(monkeypatch, system_name, machine_name, expected_suffix):
    fake_lib = FakeLib()

    monkeypatch.setattr(platform, "system", lambda: system_name)
    monkeypatch.setattr(platform, "machine", lambda: machine_name)
    monkeypatch.setattr(ctypes.cdll, "LoadLibrary", lambda path: fake_lib)
    # The REAL cg.sim is put back afterwards. Without this the fake module -- and
    # with it a FakeLib in place of the engine -- stays in sys.modules for the
    # rest of the session, and anything importing `cg.sim` LATER gets the stub.
    # `cg/game.py` never noticed because it binds `lib` at its own import time,
    # which happens first; `cg/battle.py` did, and the mirror game died on a
    # BattleStart that returned None
    # ([[from-import-liga-una-copia-no-una-vista]]).
    # TWO places remember the module, and restoring only one leaves the fake
    # reachable: `importlib.import_module("cg.sim")` both inserts into
    # sys.modules AND sets `sim` as an attribute of the `cg` package, which is
    # what `from . import sim` resolves through.
    import cg as cg_pkg
    real = sys.modules.get("cg.sim")
    if real is not None:
        monkeypatch.setitem(sys.modules, "cg.sim", real)
        monkeypatch.setattr(cg_pkg, "sim", real, raising=False)
    else:
        monkeypatch.delitem(sys.modules, "cg.sim", raising=False)
        monkeypatch.delattr(cg_pkg, "sim", raising=False)
    sys.modules.pop("cg.sim", None)

    module = importlib.import_module("cg.sim")

    assert module.lib is fake_lib
    assert module.lib_path.endswith(expected_suffix)
    assert "GameInitialize" in fake_lib.calls
