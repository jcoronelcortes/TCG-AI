"""The gate's own self-test, checked the way it checks everything else.

`utils/gate_mutation.py::self_test()` exists because this project has now had
FOUR detectors report their own bugs as defects of the agent -- the differential
oracle over three rounds, the invariant monitor's DECK_BELIEF and ENERGY_CAP,
and the gate itself, twice, for two unrelated reasons. The doctrine "validate
the harness" was written down before all of them and stopped none. What stops
them is a check that runs first and refuses to continue.

Which puts the obvious question one level up: what checks THAT? A self-test that
always passes is exactly the thing it was built to prevent, one turn of the
screw further in. So both of its halves are exercised here against a
deliberately broken gate:

  * with a companion test that pins NOTHING, every site must survive and the
    self-test must refuse -- that is the sensitivity half failing;
  * with the blind marker gone, it must refuse rather than guess -- a self-test
    that cannot locate its own expected survivor cannot judge one.

The honest arm is here too, and it is the slow one (five mutants, each a pytest
run), which is why the file is short.
"""

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "utils") not in sys.path:
    sys.path.insert(0, str(ROOT / "utils"))

import gate_mutation as gate  # noqa: E402


def test_the_target_still_has_the_answer_the_gate_expects():
    """The honest arm: four watched sites die, the one blind site lives."""
    assert gate.self_test() is True


def test_it_refuses_when_nothing_can_kill_anything(tmp_path, monkeypatch, capsys):
    """Sensitivity broken: a companion test that pins nothing.

    Every site then survives, which is what a gate whose test selection is
    broken produces -- and it is the shape that reads as a pile of findings.
    """
    empty = tmp_path / "test_pins_nothing.py"
    empty.write_text("def test_nothing():\n    assert True\n", encoding="utf-8")
    monkeypatch.setattr(gate, "SELFTEST_TESTS", [str(empty)])
    assert gate.self_test() is False
    assert "AUTO-TEST FALLIDO" in capsys.readouterr().err


def test_it_refuses_when_it_cannot_find_its_own_blind_spot(monkeypatch, capsys):
    """It has to know WHICH survivor it expects, not just how many.

    The first version matched on the parameter name, which also appears in the
    target's docstring, so it resolved to a comment line and refused a run that
    was in fact correct. Refusing was the right failure -- guessing would not
    have been -- and this pins that behaviour.
    """
    monkeypatch.setattr(gate, "SELFTEST_BLIND", "no aparece en el fichero")
    assert gate.self_test() is False
    assert "AUTO-TEST IMPOSIBLE" in capsys.readouterr().err


def test_the_target_is_left_exactly_as_it_was():
    """The probe rewrites the file in place; it has to put it back.

    A run killed halfway once left a module unparsed on disk, which is why
    `mutation_probe._protect` exists. This is that guarantee, asserted on the
    one file the gate mutates on every single invocation.
    """
    before = gate.SELFTEST_TARGET.read_text(encoding="utf-8")
    gate.self_test()
    assert gate.SELFTEST_TARGET.read_text(encoding="utf-8") == before
