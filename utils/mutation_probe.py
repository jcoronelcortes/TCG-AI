"""Which of the safety nets can actually fail?

THE PROJECT'S OWN RULE, automated. `docs/testing.md` ends with "a green test
proves nothing until you have seen it fail", and every net in here was validated
by hand: inject the bug, watch the test go red, remove it. That works while the
change is fresh and stops the day the author moves on. What is left afterwards is
a suite whose sensitivity nobody has re-checked.

This does it by machine. It rewrites one expression at a time in a target file,
runs the suite, and records whether anything went red. A mutant that SURVIVES is
a line of the agent that no test in the repository is watching -- not proof that
the line is wrong, but proof that if it ever becomes wrong, nothing will say so.

THE MUTATIONS, chosen to be the ones this codebase actually gets wrong:

  * COMPARISONS   >= <-> >, <= <-> <, == <-> !=      an off-by-one in a threshold
                                                     that was fitted to a board
  * BOUNDARIES    a numeric literal +/- 1            the same, on the constant
  * BOOLEANS      and <-> or, `not` dropped          a gate that stops gating
  * RETURNS       True <-> False on a bare return    a predicate that gives up

Deliberately NOT mutated: the score constants (31150, 20000, ...). Those are
bands, and moving one by 1 changes nothing by design -- every survivor would be a
false alarm. Bands are guarded by the golden corpus, which is a different net.

READING THE OUTPUT. `killed` is the healthy case. A `survivor` prints the file,
the line and the rewrite, which is the exact sentence to put in a new test's
docstring. `error` means the mutant did not even parse or import; it counts as
killed for scoring but tells you nothing.

IT EDITS THE FILE IN PLACE, and there is no way around that: the suite imports
the agent from the tree, so a mutant has to BE the tree for the length of one
run. The rewrite goes through `ast.unparse`, so while a mutant is installed the
file is valid Python with its comments stripped -- unrecognisable, and fatal if
it were committed. Restoring it is therefore not a `finally` and nothing else:
the original is held in memory, registered with `atexit`, and SIGINT/SIGTERM are
trapped so that a kill -- which is how a long run usually ends -- puts the file
back. This paragraph exists because the first version had only the `finally` and
a stopped run left `ptcg/turn/game_plan.py` unparsed on disk.

Usage:
    python utils/mutation_probe.py ptcg/calc/damage.py
    python utils/mutation_probe.py ptcg/turn/game_plan.py --lines 560-640
    python utils/mutation_probe.py ptcg/calc/damage.py --tests tests/test_x.py
    python utils/mutation_probe.py --changed HEAD~5     # the files of the last 5 commits
"""

import argparse
import ast
import atexit
import signal
import subprocess
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]

# The score bands are not thresholds to fit, they are an ordering. Mutating them
# by one produces survivors that mean nothing.
_BAND_FLOOR = 1000

_COMPARISON = {ast.GtE: ast.Gt, ast.Gt: ast.GtE, ast.LtE: ast.Lt,
               ast.Lt: ast.LtE, ast.Eq: ast.NotEq, ast.NotEq: ast.Eq}
_BOOLEAN = {ast.And: ast.Or, ast.Or: ast.And}


class _Collector(ast.NodeVisitor):
    """Every place worth rewriting, as (line, kind, description, mutate)."""

    def __init__(self, low, high):
        self.found = []
        self.low, self.high = low, high

    def _in_range(self, node):
        line = getattr(node, "lineno", 0)
        return self.low <= line <= self.high

    def visit_Compare(self, node):
        if self._in_range(node) and len(node.ops) == 1:
            op = type(node.ops[0])
            if op in _COMPARISON:
                self.found.append((node.lineno, "comparison",
                                   f"{op.__name__} -> {_COMPARISON[op].__name__}",
                                   ("compare", node)))
        self.generic_visit(node)

    def visit_BoolOp(self, node):
        if self._in_range(node) and type(node.op) in _BOOLEAN:
            self.found.append((node.lineno, "boolean",
                               f"{type(node.op).__name__} -> "
                               f"{_BOOLEAN[type(node.op)].__name__}",
                               ("boolop", node)))
        self.generic_visit(node)

    def visit_UnaryOp(self, node):
        if self._in_range(node) and isinstance(node.op, ast.Not):
            self.found.append((node.lineno, "not-dropped", "drop `not`",
                               ("drop_not", node)))
        self.generic_visit(node)

    def visit_Constant(self, node):
        if not self._in_range(node):
            return
        if isinstance(node.value, bool):
            self.found.append((node.lineno, "boolean-literal",
                               f"{node.value} -> {not node.value}",
                               ("flip_bool", node)))
        elif isinstance(node.value, int) and 0 < abs(node.value) < _BAND_FLOOR:
            self.found.append((node.lineno, "boundary",
                               f"{node.value} -> {node.value + 1}",
                               ("bump_int", node)))


class _Mutator(ast.NodeTransformer):
    def __init__(self, kind, target):
        self.kind, self.target = kind, target

    def visit(self, node):
        if node is self.target:
            if self.kind == "compare":
                node.ops = [_COMPARISON[type(node.ops[0])]()]
            elif self.kind == "boolop":
                node.op = _BOOLEAN[type(node.op)]()
            elif self.kind == "drop_not":
                return self.generic_visit(node.operand)
            elif self.kind == "flip_bool":
                return ast.copy_location(ast.Constant(value=not node.value), node)
            elif self.kind == "bump_int":
                return ast.copy_location(ast.Constant(value=node.value + 1), node)
        return super().visit(node)


def _mutate_source(source, kind, target):
    tree = ast.parse(source)
    # The collector ran on a different parse, so the target has to be located
    # again by position: identity does not survive a re-parse.
    for node in ast.walk(tree):
        if (getattr(node, "lineno", None) == target[0]
                and getattr(node, "col_offset", None) == target[1]
                and type(node).__name__ == target[2]):
            mutated = _Mutator(kind, node).visit(tree)
            ast.fix_missing_locations(mutated)
            return ast.unparse(mutated)
    return None


def _position(node):
    return (node.lineno, node.col_offset, type(node).__name__)


def run_suite(tests):
    # `-B`: do not WRITE bytecode. Together with `_drop_bytecode` below this
    # closes a hole that made the probe report false survivors -- see there.
    result = subprocess.run(
        [sys.executable, "-B", "-m", "pytest", "-x", "-q", *tests],
        cwd=_ROOT, capture_output=True, text=True)
    return result.returncode


def _drop_bytecode(path):
    """Delete the cached bytecode of the file about to be mutated.

    THE FALSE SURVIVOR THIS EXISTS TO STOP. CPython validates a `.pyc` against
    the source's mtime IN WHOLE SECONDS and its size in bytes. Two mutants of
    the same file routinely differ in neither: `meganium_active=False -> True`
    and `neutralization_zone=False -> True` produce sources of identical length,
    and the probe writes them milliseconds apart. The second run then imports
    the FIRST mutant's bytecode, the tests pass because that mutant was already
    killed and reverted... and the second is reported as a survivor.

    Found while a test that demonstrably fails against `neutralization_zone=True`
    was being reported as not watching it. It is not a rare corner: every
    boolean-literal pair on one line has this shape, and so does every
    `>= -> >`.
    """
    cache = Path(path).parent / "__pycache__"
    if not cache.is_dir():
        return
    stem = Path(path).stem
    for stale in cache.glob(f"{stem}.*.pyc"):
        try:
            stale.unlink()
        except OSError:
            pass


def _protect(path, source):
    """Put `source` back whatever happens: normal exit, exception, or a kill."""
    def restore(*_args):
        try:
            if path.read_text(encoding="utf-8") != source:
                path.write_text(source, encoding="utf-8")
        except OSError:
            pass

    atexit.register(restore)
    previous = {}
    for sig in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP):
        def handler(signum, frame, _sig=sig):
            restore()
            old = previous.get(_sig)
            if callable(old):
                old(signum, frame)
            raise SystemExit(130)
        try:
            previous[sig] = signal.signal(sig, handler)
        except (ValueError, OSError):
            pass
    return restore


def probe(path, low, high, tests, limit=None, skip_lines=None):
    """Mutate lines `low`-`high` of `path`, one at a time, against `tests`.

    `skip_lines` is the waiver channel used by utils/gate_mutation.py: a line
    marked `# mutation: <reason>` is not mutated at all, so the waiver costs
    nothing rather than costing a full suite run whose result is discarded.
    """
    path = Path(path)
    source = path.read_text(encoding="utf-8")
    restore = _protect(path, source)
    collector = _Collector(low, high)
    collector.visit(ast.parse(source))
    sites = collector.found
    if skip_lines:
        sites = [s for s in sites if s[0] not in skip_lines]
    if limit:
        sites = sites[:limit]

    survivors, killed, errors = [], 0, 0
    print(f"{path}: {len(sites)} mutation sites in lines {low}-{high}")
    try:
        for i, (line, kind_name, description, (kind, node)) in enumerate(sites, 1):
            mutated = _mutate_source(source, kind, _position(node))
            if mutated is None:
                errors += 1
                continue
            path.write_text(mutated, encoding="utf-8")
            _drop_bytecode(path)
            code = run_suite(tests)
            if code == 0:
                survivors.append((line, kind_name, description))
                mark = "SURVIVED"
            elif code == 1:
                killed += 1
                mark = "killed"
            else:
                errors += 1
                mark = "error"
            print(f"  [{i}/{len(sites)}] line {line:5d} {kind_name:15s} "
                  f"{description:28s} {mark}")
    finally:
        restore()

    print(f"\n{path}: killed {killed}, SURVIVED {len(survivors)}, errors {errors}")
    if survivors:
        print("lines no test in the repository is watching:")
        for line, kind_name, description in survivors:
            print(f"  {path}:{line}  {kind_name}: {description}")
    return survivors


def changed_files(since):
    out = subprocess.run(["git", "diff", "--name-only", since],
                         cwd=_ROOT, capture_output=True, text=True).stdout
    return [f for f in out.split()
            if f.endswith(".py") and (f.startswith("ptcg/") or f == "main.py")]


def changed_line_ranges(since, path):
    """The lines a diff ADDED, as (low, high) pairs.

    The mode worth having: mutating a whole file asks "is the agent covered",
    which is a project-sized question. Mutating the lines a change added asks
    "does the test I just wrote actually watch what I just wrote", which is the
    question the author can act on, and it is the one this project answers by
    hand every time.
    """
    out = subprocess.run(
        ["git", "diff", "-U0", since, "--", str(path)],
        cwd=_ROOT, capture_output=True, text=True).stdout
    ranges = []
    for line in out.splitlines():
        if not line.startswith("@@"):
            continue
        # @@ -a,b +c,d @@
        after = line.split("+", 1)[1].split(" ", 1)[0]
        start, _, count = after.partition(",")
        start, count = int(start), int(count or 1)
        if count:
            ranges.append((start, start + count - 1))
    return ranges


def main(argv):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("target", nargs="?", help="file to mutate")
    parser.add_argument("--lines", default=None, help="N-M, only this range")
    parser.add_argument("--tests", nargs="*", default=["tests"],
                        help="what to run against each mutant (default: the suite)")
    parser.add_argument("--limit", type=int, default=None,
                        help="stop after N sites (a quick sample)")
    parser.add_argument("--changed", default=None,
                        help="git ref: mutate ONLY the lines added since it")
    args = parser.parse_args(argv)

    total = []
    if args.changed:
        files = ([args.target] if args.target
                 else changed_files(args.changed))
        if not files:
            print(f"no python files of the agent changed since {args.changed}")
            return 0
        for name in files:
            target = _ROOT / name
            for low, high in changed_line_ranges(args.changed, name):
                total += probe(target, low, high, args.tests, args.limit)
        return 1 if total else 0

    if not args.target:
        parser.error("give a file or --changed <ref>")
    low, high = 1, 10 ** 9
    if args.lines:
        low, high = (int(x) for x in args.lines.split("-"))
    total += probe(Path(args.target), low, high, args.tests, args.limit)
    return 1 if total else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
