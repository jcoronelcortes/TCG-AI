"""Mutation as a pre-merge gate: does the test you just wrote watch the line?

T0.3 of docs/testing-plan-2026-08.md, and the strongest quality lever available
here because it measures the SUITE rather than the agent. The measurement that
put it at the top of the plan: of fourteen mutants injected into code that had
just been written WITH a test, TEN survived. A `>=` rewritten as `>`, a `1` as a
`2`, an `and` as an `or`, and the whole suite stays green.

WHY A WRAPPER AND NOT JUST `mutation_probe.py --changed`. Because that was
measured too, on the night of 8-9 August: the sweep of a five-commit diff was
heading for ~90 MINUTES, which does not fit in anything anyone will run before a
merge. The cost is not the mutating, it is that every one of the ~100 mutants
re-runs 1 800 tests, and all but a handful of them have nothing to do with the
line being mutated.

So this narrows it in three ways, in descending order of how much they save:

  1. TESTS BY COVERAGE. A line-to-test map is built once with coverage
     CONTEXTS (`--cov-context=test`), and each mutant runs only the tests that
     actually execute its line. That is typically a handful instead of 1 815,
     and it costs nothing in strength: a test that never runs the line cannot
     be the one that would have caught it.

  2. UNCOVERED LINES ARE NOT MUTATED, THEY ARE REPORTED. If no test executes a
     changed line, the answer is already known -- nothing is watching it -- so
     spending a mutant to prove it is waste. Those come back as `UNCOVERED`,
     which is a stronger finding than a survivor and a cheaper one.

  3. WAIVERS COST NOTHING. A line carrying `# mutation: <reason>` is skipped
     before it is mutated, not after.

THE BUDGET, as the plan states it: zero surviving mutants on added lines. A
survivor is not proof the line is wrong; it is proof that if it ever becomes
wrong nothing will say so, and it prints the exact rewrite that went unnoticed,
which is the missing test's docstring already written.

Usage:
    python utils/gate_mutation.py --map                # build the line -> tests map
    python utils/gate_mutation.py --changed HEAD~1     # gate the last commit
    python utils/gate_mutation.py --changed HEAD~1 --report-only
"""

import argparse
import subprocess
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT / "utils") not in sys.path:
    sys.path.insert(0, str(_ROOT / "utils"))

import mutation_probe as mp  # noqa: E402

CONTEXT_DATA = _ROOT / ".coverage-contexts"

# A line the author has decided not to guard, and said why. The reason is not
# parsed: it is there for the reader of the diff, which is the only place it can
# do any good.
WAIVER = "# mutation:"

# Above this many tests for one line, running "the tests that cover it" stops
# being a saving. It happens on lines inside main.agent(), which nearly every
# test reaches; there the file's own test file is a better bet than 1 800 runs.
MAX_TESTS_PER_LINE = 40


def build_map():
    """Run the suite once recording which test executes which line."""
    print("Midiendo con contextos (una vez; tarda mas que la suite normal) ...",
          flush=True)
    env_data = str(CONTEXT_DATA)
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "--cov=main", "--cov=ptcg",
         "--cov-context=test", "--cov-report="],
        cwd=_ROOT, capture_output=True, text=True,
        env={**_os_environ(), "COVERAGE_FILE": env_data})
    print(result.stdout.strip().splitlines()[-1] if result.stdout else "")
    if not CONTEXT_DATA.exists():
        print("No se escribio el mapa de contextos.", file=sys.stderr)
        return 2
    print(f"Mapa escrito en {CONTEXT_DATA.name}")
    return 0


def _os_environ():
    import os
    return dict(os.environ)


def _contexts_for(path):
    """{line: [test node id, ...]} for one file, or None if there is no map."""
    if not CONTEXT_DATA.exists():
        return None
    import coverage
    data = coverage.CoverageData(str(CONTEXT_DATA))
    data.read()
    absolute = str((_ROOT / path).resolve())
    if absolute not in set(data.measured_files()):
        return {}
    out = {}
    for line, contexts in data.contexts_by_lineno(absolute).items():
        tests = sorted({c.split("|")[0] for c in contexts if c})
        if tests:
            out[line] = tests
    return out


def _waived_lines(path, low, high):
    source = (_ROOT / path).read_text(encoding="utf-8").splitlines()
    return {n for n in range(low, min(high, len(source)) + 1)
            if WAIVER in source[n - 1]}


def gate(since, report_only=False):
    files = mp.changed_files(since)
    if not files:
        print(f"Ningun fichero del agente cambio desde {since}.")
        return 0

    contexts_available = CONTEXT_DATA.exists()
    if not contexts_available:
        print(f"AVISO: no hay mapa de contextos ({CONTEXT_DATA.name}). Cada "
              f"mutante correra la suite entera; corre --map una vez.\n")

    survivors, uncovered, waived = [], [], []
    for name in files:
        contexts = _contexts_for(name) if contexts_available else None
        for low, high in mp.changed_line_ranges(since, name):
            skip = _waived_lines(name, low, high)
            waived += [(name, n) for n in sorted(skip)]

            tests = ["tests"]
            if contexts is not None:
                covering = sorted({t for line in range(low, high + 1)
                                   for t in contexts.get(line, ())})
                if not covering:
                    uncovered.append((name, low, high))
                    continue
                if len(covering) <= MAX_TESTS_PER_LINE:
                    tests = covering
            survivors += [(name, *s) for s in
                          mp.probe(_ROOT / name, low, high, tests,
                                   skip_lines=skip)]

    print("\n" + "=" * 70)
    if waived:
        print(f"\nDispensados por `{WAIVER} <razon>` ({len(waived)}):")
        for name, line in waived:
            print(f"  {name}:{line}")
    if uncovered:
        print(f"\nSIN COBERTURA -- ningun test ejecuta estas lineas nuevas "
              f"({len(uncovered)} rangos):")
        for name, low, high in uncovered:
            print(f"  {name}:{low}-{high}")
    if survivors:
        print(f"\nSUPERVIVIENTES -- lineas nuevas que ningun test vigila "
              f"({len(survivors)}):")
        for name, line, kind, description in survivors:
            print(f"  {name}:{line}  {kind}: {description}")
    if not survivors and not uncovered:
        print("\nCero supervivientes y cero lineas sin cobertura. El gate pasa.")
        return 0
    print("\nCada linea de arriba es la frase del test que falta. El presupuesto "
          "del plan es CERO: escribe el test, o dispensa la linea con "
          f"`{WAIVER} <razon>` y di por que.")
    return 0 if report_only else 1


def main(argv):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--changed", default=None,
                        help="ref de git: vigila solo las lineas anadidas desde el")
    parser.add_argument("--map", action="store_true",
                        help="reconstruye el mapa linea -> tests (una vez)")
    parser.add_argument("--report-only", action="store_true",
                        help="informa pero sale con 0")
    args = parser.parse_args(argv)

    if args.map:
        return build_map()
    if not args.changed:
        parser.error("da --changed <ref> o --map")
    return gate(args.changed, report_only=args.report_only)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
