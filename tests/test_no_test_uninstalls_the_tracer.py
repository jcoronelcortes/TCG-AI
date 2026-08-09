"""`sys.settrace(None)` in a test turns off coverage for everything after it.

FOUND while the mutation gate was reporting three survivors that a test in this
same suite demonstrably kills. The gate picks the tests to run against each
mutant from a line-to-test map built with coverage CONTEXTS, and the map was
missing almost everything: **225 contexts for 1 843 tests, 11 test files of
153**, all of them alphabetically before
`tests/test_comfey_relief_against_bench_out.py`.

THE MECHANISM. Three tests read a LOCAL variable of `agent()` by installing a
trace function, which is a legitimate and rather good technique -- it is how
this project checks a flag that never reaches the output. The problem is the
cleanup:

    sys.settrace(tr)
    try:
        m.agent(obs)
    finally:
        sys.settrace(None)          # <- not "off", but "OFF FOR EVERYONE"

There is only one trace function per thread. Under `--cov-context=test`
coverage owns it, and `None` does not restore coverage's tracer, it removes it.
Line coverage recovers (only 0.8 points were lost overall, which is why nobody
noticed), but the dynamic CONTEXT does not: every test that runs afterwards is
recorded under the empty context, and the map the gate depends on is a map of
the first eleven files.

The fix is one line -- keep `sys.gettrace()` and put it back -- and this test is
what stops it from coming back, because the symptom is invisible: the suite
stays green, coverage barely moves, and only a tool that reads contexts ever
finds out.

It is a source check rather than a runtime one on purpose. At runtime the damage
is done by whichever test ran first, and attributing it means running the whole
suite in the right order; in the source it is a single unambiguous string.
"""

import re
from pathlib import Path

TESTS = Path(__file__).resolve().parent

# `sys.settrace(None)` anywhere, however it is spaced.
UNINSTALL = re.compile(r"sys\s*\.\s*settrace\s*\(\s*None\s*\)")

# What the three fixed call sites do instead, and what a new one should do.
RESTORE_HINT = """
    _previous_tracer = sys.gettrace()
    sys.settrace(my_tracer)
    try:
        ...
    finally:
        sys.settrace(_previous_tracer)
"""


def _offenders():
    out = []
    for path in sorted(TESTS.glob("test_*.py")):
        if path.name == Path(__file__).name:
            continue
        text = path.read_text(encoding="utf-8")
        for number, line in enumerate(text.splitlines(), 1):
            if UNINSTALL.search(line):
                out.append(f"{path.name}:{number}")
    return out


def test_no_test_turns_the_tracer_off_for_everyone():
    offenders = _offenders()
    assert not offenders, (
        "estos sitios desinstalan el tracer del proceso entero, y con el se "
        "lleva el contexto de coverage que utils/gate_mutation.py usa para "
        "elegir tests:\n  " + "\n  ".join(offenders)
        + "\nGuarda el anterior y devuelvelo:" + RESTORE_HINT)


def test_the_check_can_actually_fail():
    """The other half: a pattern that matches nothing proves nothing."""
    assert UNINSTALL.search("    sys.settrace(None)")
    assert UNINSTALL.search("sys . settrace( None )")
    assert not UNINSTALL.search("sys.settrace(_previous_tracer)")
    assert not UNINSTALL.search("sys.settrace(tr)")


def test_the_three_known_sites_restore_instead():
    """Name them, so a revert is loud rather than quiet."""
    fixed = ["test_comfey_relief_against_bench_out.py",
             "test_cornerstone_cubchoo_brings_up_tapu.py",
             "test_the_dead_turn_is_not_a_teal_dance_we_cannot_pay.py"]
    for name in fixed:
        text = (TESTS / name).read_text(encoding="utf-8")
        assert "sys.gettrace()" in text, f"{name} ya no guarda el tracer previo"
        assert "sys.settrace(_previous_tracer)" in text, (
            f"{name} ya no lo devuelve")
