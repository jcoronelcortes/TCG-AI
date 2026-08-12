"""R10: the two halves of "a field somebody computed has to be read".

A lint rule is a detector like any other in this project, and the rule that
governs detectors applies to it: it does not get to report until it has proved,
in the same run, that it catches a planted defect and stays quiet without one.

The plant here is a whole miniature tree -- a carrier module with two fields and
a consumer module that reads exactly one of them -- because that is the only
shape that exercises what R10 actually does: resolve `@property` readers back to
the fields they touch, and count `getattr(x, 'field', ...)` as a read.

THE HISTORICAL CALIBRATION, which is the half that cannot be faked and is
recorded here rather than run (an old tree is not on this repo's test path): on
`710c198^` the rule reports THREE fields of `TurnPlan`, and one of them is
`op_wins_after_ko` -- the sentence the plan published on the board that lost
episode 92260006, with no consumer anywhere. On HEAD it reports two, and
`op_wins_after_ko` is not among them: the rule went quiet exactly where the fix
landed.
"""

import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT / "utils") not in sys.path:
    sys.path.insert(0, str(_ROOT / "utils"))

import lint_architecture as lint  # noqa: E402


CARRIER = '''
from dataclasses import dataclass


@dataclass(frozen=True)
class Carrier:
    """Two fields and a property that resolves one of them."""

    read_directly: int
    read_via_property: int
    read_by_nobody: int
    # R10: on purpose -- this is the exemption path, and the reason has to be
    # a sentence, spread over as many comment lines as it takes.
    exempted: int = 0

    @property
    def derived(self) -> bool:
        return bool(self.read_via_property)
'''

CONSUMER = '''
def use(carrier):
    total = carrier.read_directly
    if carrier.derived:
        total += 1
    return total + getattr(carrier, "by_getattr", 0)
'''


@pytest.fixture
def planted(tmp_path, monkeypatch):
    """A tree of two modules, with `lint` pointed at it."""
    package = tmp_path / "ptcg"
    package.mkdir()
    (package / "carrier.py").write_text(CARRIER, encoding="utf-8")
    (package / "consumer.py").write_text(CONSUMER, encoding="utf-8")
    (tmp_path / "main.py").write_text("", encoding="utf-8")
    monkeypatch.setattr(lint, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(lint, "PACKAGE", package)
    return package / "carrier.py"


def test_sensitivity_the_unread_field_is_caught(planted):
    """The half that proves the rule can see a hole."""
    failures = lint.rule_10_data_has_a_consumer(((planted, "Carrier"),))
    caught = {f[3].split("`")[1] for f in failures}
    assert "Carrier.read_by_nobody" in caught, (
        "un campo que nadie lee tiene que salir: es el defecto plantado")


def test_specificity_reading_it_is_enough_however_it_is_read(planted):
    """The half that proves the rule stays quiet -- and it is the expensive one.

    A version of this rule that only understood plain attribute access accused
    `win_route`, `mode` and two more on a tree where all of them are
    load-bearing, because the agent reads them THROUGH properties. Three ways of
    reading a field, all three silent.
    """
    failures = lint.rule_10_data_has_a_consumer(((planted, "Carrier"),))
    caught = {f[3].split("`")[1] for f in failures}
    assert "Carrier.read_directly" not in caught, "lectura directa"
    assert "Carrier.read_via_property" not in caught, (
        "lo lee una @property que si se lee fuera: cuenta como leido")
    assert "Carrier.exempted" not in caught, "eximido con motivo escrito"


def test_the_exemption_needs_a_written_reason(tmp_path, monkeypatch):
    """`# R10:` with nothing after it is not an argument, and does not exempt."""
    package = tmp_path / "ptcg"
    package.mkdir()
    (package / "carrier.py").write_text(
        CARRIER.replace(
            "    # R10: on purpose -- this is the exemption path, and the "
            "reason has to be\n    # a sentence, spread over as many comment "
            "lines as it takes.",
            "    # R10: x"),
        encoding="utf-8")
    (tmp_path / "main.py").write_text("", encoding="utf-8")
    monkeypatch.setattr(lint, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(lint, "PACKAGE", package)
    failures = lint.rule_10_data_has_a_consumer(((package / "carrier.py", "Carrier"),))
    caught = {f[3].split("`")[1] for f in failures}
    assert "Carrier.exempted" in caught, (
        "una exencion sin motivo escrito no exime: es justo la diferencia "
        "entre una decision y un descuido")


def test_the_real_tree_is_clean():
    """HEAD itself, through the rule as it ships."""
    assert lint.rule_10_data_has_a_consumer() == []
