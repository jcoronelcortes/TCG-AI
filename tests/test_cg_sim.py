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
    sys.modules.pop("cg.sim", None)

    module = importlib.import_module("cg.sim")

    assert module.lib is fake_lib
    assert module.lib_path.endswith(expected_suffix)
    assert "GameInitialize" in fake_lib.calls
