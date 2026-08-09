"""A detector that failed its own self-test does not get to report a number.

`utils/nightly.py` is the pipeline of a night as a script, and this is the rule
it exists to enforce. Over 8-9 August four detectors in this repository reported
their own bugs as defects of the agent -- the differential oracle across three
rounds, the invariant monitor twice in one morning, the mutation gate twice more
for two unrelated causes -- and in every case the numbers looked like findings.

The classification is therefore not cosmetic, and the order inside it is the
argument:

  * a failed SELF-TEST wins over everything, INCLUDING a clean exit code. A
    detector that cannot prove it still works and then says "nothing found" is
    the most misleading of the three outcomes, not the most reassuring;
  * a non-zero exit is FINDINGS for the tools that report by exit code -- the
    permutation probe, the mutation gate, the corpus -- and FAILED for the rest.
    Calling a tool's findings a failure is how a pipeline teaches people to
    ignore its red.

Everything here is a pure function on (output, exit code), so it runs in
milliseconds and needs no games.
"""

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "utils") not in sys.path:
    sys.path.insert(0, str(ROOT / "utils"))

import nightly  # noqa: E402


@pytest.mark.parametrize("mark", nightly.SELF_TEST_FAILURES)
@pytest.mark.parametrize("code", [0, 1, 2])
def test_a_broken_self_test_invalidates_the_stage_whatever_it_exited_with(mark, code):
    """Including exit 0, which is the case worth having a test for."""
    status, quarantined = nightly.classify(
        f"Auto-test 1/2 ...\n{mark}: se esperaba 1 superviviente\n"
        "Hallazgos: NINGUNO\n", code, findings_exit=False)
    assert status == nightly.INVALID
    assert quarantined, "sus numeros no pueden salir en el informe"


def test_a_clean_run_is_ok():
    status, quarantined = nightly.classify(
        "Auto-test 1/2 ...\n  OK: 8 PHANTOM_KO sobre la mentira.\n"
        "Hallazgos: NINGUNO\n", 0, findings_exit=False)
    assert status == nightly.OK
    assert not quarantined


def test_a_tool_that_reports_by_exit_code_is_not_a_failure():
    """The permutation probe exits 1 when it FINDS order-dependent decisions."""
    output = "decisions compared: 5057\norder-dependent    : 32  (0.63%)\n"
    assert nightly.classify(output, 1, findings_exit=True)[0] == nightly.FINDINGS
    assert nightly.classify(output, 1, findings_exit=False)[0] == nightly.FAILED


def test_the_summary_of_an_invalid_stage_is_replaced_and_not_shown():
    """The quarantine has to reach the report, not just the status column."""
    assert nightly.SELF_TEST_FAILED_SUMMARY
    assert "no valen" in nightly.SELF_TEST_FAILED_SUMMARY


def test_the_two_detectors_of_this_repository_abort_with_a_watched_phrase():
    """The classifier greps for a phrase; the phrase has to be the real one.

    A rename in either detector would silently turn every future INVALID into a
    green OK, which is exactly the failure this file is about. So the phrases
    are checked against the sources that print them.
    """
    for name in ("utils/differential_oracle.py", "utils/invariant_monitor.py",
                 "utils/gate_mutation.py"):
        text = (ROOT / name).read_text(encoding="utf-8")
        assert any(mark in text for mark in nightly.SELF_TEST_FAILURES), (
            f"{name} ya no aborta con ninguna de las frases que nightly.py "
            f"vigila: {nightly.SELF_TEST_FAILURES}")
