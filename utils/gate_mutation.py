"""Mutation as a pre-merge gate: does the test you just wrote watch the line?

T0.3 of docs/testing-plan-2026-08.md, and the strongest quality lever available
here because it measures the SUITE rather than the agent. The measurement that
put it at the top of the plan: of fourteen mutants injected into code that had
just been written WITH a test, TEN survived. A `>=` rewritten as `>`, a `1` as a
`2`, an `and` as an `or`, and the whole suite stays green.

THE PROBLEM THIS SOLVES. `mutation_probe.py --changed` re-runs the whole suite
against every mutant, and the night of 8-9 August measured a five-commit sweep
heading for ~90 minutes. Nothing anyone will run before a merge.

THE RULE THE DESIGN RESTS ON, and it is worth stating on its own line:

    A KILL IS TRUSTWORTHY WHATEVER YOU RAN. A SURVIVAL IS ONLY TRUSTWORTHY
    AGAINST THE WHOLE SUITE.

If a mutant makes any test fail, that test watches the line, and it does not
matter that ten thousand other tests were not run. But "nothing went red" only
means something if everything had the chance to. So:

  1. each mutant runs first against a CHEAP CANDIDATE SET -- the test files
     whose text mentions the module being mutated. Most mutants die there, in a
     second or two, and their verdict is final;
  2. a mutant that survives that set is re-run against the ENTIRE suite before
     it is reported. Survivors are the minority, so the expensive run is paid
     only where it changes the answer;
  3. a line carrying `# mutation: <reason>` is skipped before it is mutated
     rather than after, so a waiver costs nothing.

WHY NOT COVERAGE CONTEXTS, which is what this file did first and what the
obvious design is. `--cov-context=test` builds an exact line-to-test map, and
two things killed it. It is SLOW: over 15 minutes on this suite, per build,
because the cost is the per-test context switch and narrowing `--cov` to a
single file does not reduce it. And it is FRAGILE in a way that is invisible:
the map has to be rebuilt whenever the tests change, and a stale or truncated
map does not look broken -- it looks like good news, because a line whose tests
are missing comes back as "nothing watches it" and a mutant run against the
wrong tests comes back as SURVIVED.

That is not hypothetical. The first version of this gate reported three
survivors on `ptcg/calc/damage.py` that a test in this very suite demonstrably
kills, because an unrelated test called `sys.settrace(None)` and turned
coverage's context off for the rest of the process: the map held 11 test files
of 153 and nobody could tell. The heuristic candidate set below can be wrong in
the same direction and it does not matter, because step 2 catches it.

THE BUDGET, as the plan states it: zero surviving mutants on added lines. A
survivor is not proof the line is wrong; it is proof that if it ever becomes
wrong nothing will say so, and it prints the exact rewrite that went unnoticed,
which is the missing test's docstring already written.

Usage:
    python utils/gate_mutation.py --changed HEAD~1
    python utils/gate_mutation.py --changed HEAD~1 --report-only
"""

import argparse
import re
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT / "utils") not in sys.path:
    sys.path.insert(0, str(_ROOT / "utils"))

import mutation_probe as mp  # noqa: E402

# A line the author has decided not to guard, and said why. The reason is not
# parsed: it is there for the reader of the diff, which is the only place it can
# do any good.
WAIVER = "# mutation:"

# The whole suite, as pytest names it. What a survivor is confirmed against.
EVERYTHING = ["tests"]


def _identifiers(path, ranges):
    """Names defined or used on the changed lines, to fish for tests with.

    Deliberately crude. This only has to produce a set of tests that is often
    right; when it is wrong the mutant survives the candidate set and gets the
    full suite anyway, so a miss costs seconds and never an answer.
    """
    try:
        source = (_ROOT / path).read_text(encoding="utf-8").splitlines()
    except OSError:
        return set()
    names = set()
    for low, high in ranges:
        for line in source[low - 1:high]:
            names.update(re.findall(r"[A-Za-z_][A-Za-z0-9_]{4,}", line))
    return names


def candidate_tests(path, ranges):
    """Test files that mention the module or the names on its changed lines.

    `main.py` is excluded from the module half on purpose: nearly every test
    mentions it, so it would select everything and save nothing -- there the
    identifiers do the work.
    """
    stem = Path(path).stem
    module = f"{Path(path).parent.name}.{stem}" if Path(path).parent.name else stem
    names = _identifiers(path, ranges)
    wanted = set()
    for test in sorted((_ROOT / "tests").glob("test_*.py")):
        try:
            text = test.read_text(encoding="utf-8")
        except OSError:
            continue
        if stem != "main" and (stem in text or module in text):
            wanted.add(str(test.relative_to(_ROOT)))
            continue
        if any(name in text for name in names):
            wanted.add(str(test.relative_to(_ROOT)))
    return sorted(wanted)


def _waived_lines(path, low, high):
    source = (_ROOT / path).read_text(encoding="utf-8").splitlines()
    return {n for n in range(low, min(high, len(source)) + 1)
            if WAIVER in source[n - 1]}


def confirm(path, survivors):
    """Re-run each survivor of the candidate set against the WHOLE suite.

    This is the step that makes the cheap selection safe. It returns the ones
    that survive that too, which are the real findings.
    """
    if not survivors:
        return []
    print(f"\nConfirmando {len(survivors)} supervivientes contra la suite "
          f"entera ...", flush=True)
    real = []
    for line, kind, description in survivors:
        again = mp.probe(_ROOT / path, line, line, EVERYTHING)
        still = [s for s in again if s[1] == kind and s[2] == description]
        if still:
            real += still
        else:
            print(f"  {path}:{line} {kind} lo mataba la suite entera: "
                  f"el conjunto barato no la incluia")
    return real


def gate(since, report_only=False):
    files = mp.changed_files(since)
    if not files:
        print(f"Ningun fichero del agente cambio desde {since}.")
        return 0

    survivors, waived = [], []
    for name in files:
        ranges = mp.changed_line_ranges(since, name)
        if not ranges:
            continue
        candidates = candidate_tests(name, ranges)
        tests = candidates or EVERYTHING
        print(f"\n### {name}: {sum(h - l + 1 for l, h in ranges)} lineas nuevas, "
              f"{len(candidates) or 'todos los'} ficheros de test candidatos")

        cheap = []
        for low, high in ranges:
            skip = _waived_lines(name, low, high)
            waived += [(name, n) for n in sorted(skip)]
            cheap += mp.probe(_ROOT / name, low, high, tests, skip_lines=skip)
        survivors += [(name, *s) for s in confirm(name, cheap)]

    print("\n" + "=" * 70)
    if waived:
        print(f"\nDispensados por `{WAIVER} <razon>` ({len(waived)}):")
        for name, line in waived:
            print(f"  {name}:{line}")
    if not survivors:
        print("\nCero supervivientes contra la suite entera. El gate pasa.")
        return 0
    print(f"\nSUPERVIVIENTES -- lineas nuevas que ningun test vigila "
          f"({len(survivors)}):")
    for name, line, kind, description in survivors:
        print(f"  {name}:{line}  {kind}: {description}")
    print("\nCada linea de arriba es la frase del test que falta. El presupuesto "
          "del plan es CERO: escribe el test, o dispensa la linea con "
          f"`{WAIVER} <razon>` y di por que.")
    return 0 if report_only else 1


def main(argv):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--changed", default=None,
                        help="ref de git: vigila solo las lineas anadidas desde el")
    parser.add_argument("--report-only", action="store_true",
                        help="informa pero sale con 0")
    args = parser.parse_args(argv)

    if not args.changed:
        parser.error("da --changed <ref>")
    return gate(args.changed, report_only=args.report_only)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
