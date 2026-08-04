"""Migrates module state from main.py to `AGENT_STATE.<field>` (wave 3 of the refactor).

WHY IT IS DIFFERENT FROM THE PREVIOUS WAVES
  Waves 1, 2 and 4 MOVE lines without touching them. This one REWRITES them: `ko_last_turn`
  becomes `AGENT_STATE.ko_last_turn` in every place. That is why the equivalence gate
  (utils/shadow.py) stops being a safety net and becomes the main instrument.

WHY NOT `ast.unparse`
  Rewriting the tree and printing it again would destroy ALL the comments, which
  in main.py are real documentation (the why of every rule, with
  references to concrete games). Here the AST is only used to LOCATE
  (lineno, col_offset) and the text is edited in place, from right to left so
  that the offsets are not invalidated. Everything else stays byte for byte the same.

SCOPE ANALYSIS
  A `Name` is only rewritten if it really refers to the global. Inside a
  function that declares `global X` -> yes. Inside one that assigns `X` without
  declaring it global, `X` is LOCAL and is not touched. Arguments and
  comprehensions also count as locals. Without this, a local `plan = ...`
  in any helper would end up writing to the shared state.

Usage:
    python utils/migrate_state.py --fields plan,pre_turn          # a dry run
    python utils/migrate_state.py --fields plan,pre_turn --apply
    python utils/migrate_state.py --list                        # what is left
"""

import argparse
import ast
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "utils"))

from purity import analizar  # noqa: E402

OBJETO = "AGENT_STATE"


class _Ambito(ast.NodeVisitor):
    """Collects the Name nodes that DO refer to the given globals."""

    def __init__(self, fields):
        self.fields = fields
        self.hits = []          # (lineno, col_offset, name)
        self.globales_decl = []  # (lineno, col_offset, end_col, names)

    # --- module level --------------------------------------------------------
    def visit_Module(self, node):
        for hijo in node.body:
            self._visitar(hijo, locales=set(), globales=set(self.fields))

    def _locales_de(self, fn):
        """Local names of `fn`: arguments and assignments not declared global."""
        decl_global = set()
        for n in ast.walk(fn):
            if isinstance(n, ast.Global):
                decl_global.update(n.names)
        locales = set()
        a = fn.args if isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)) else None
        if a is not None:
            locales |= {x.arg for x in a.args + a.kwonlyargs + a.posonlyargs}
            if a.vararg:
                locales.add(a.vararg.arg)
            if a.kwarg:
                locales.add(a.kwarg.arg)
        for n in ast.walk(fn):
            # do not look inside nested functions: they have their own scope
            if isinstance(n, ast.Name) and isinstance(n.ctx, (ast.Store, ast.Del)):
                if n.id not in decl_global:
                    locales.add(n.id)
            elif isinstance(n, (ast.Import, ast.ImportFrom)):
                for al in n.names:
                    locales.add(al.asname or al.name.split(".")[0])
            elif isinstance(n, ast.ExceptHandler) and n.name:
                locales.add(n.name)
        return locales, decl_global

    def _visitar(self, node, locales, globales):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
            loc, decl = self._locales_de(node)
            # visible as global: what is declared `global` + what is not local
            g = (globales - loc) | (decl & self.fields)
            for n in ast.iter_child_nodes(node):
                self._visitar(n, loc, g)
            return
        if isinstance(node, ast.ClassDef):
            for n in ast.iter_child_nodes(node):
                self._visitar(n, locales, globales)
            return
        if isinstance(node, ast.Global):
            if set(node.names) & self.fields:
                self.globales_decl.append(node)
            return
        if isinstance(node, ast.Attribute):
            # `AGENT_STATE.plan` already migrated: do not touch the `plan` again
            if isinstance(node.value, ast.Name) and node.value.id == OBJETO:
                return
        if isinstance(node, ast.Name) and node.id in self.fields and node.id in globales:
            self.hits.append((node.lineno, node.col_offset, node.id))
        for n in ast.iter_child_nodes(node):
            self._visitar(n, locales, globales)


def migrate(text, fields):
    """Returns (new_text, n_rewrites, n_globals_removed)."""
    fields = set(fields)
    tree = ast.parse(text)
    v = _Ambito(fields)
    v.visit(tree)

    lines = text.splitlines(keepends=True)

    # 1) rewrite the Name nodes, per line and from right to left
    per_line = {}
    for ln, col, name in v.hits:
        per_line.setdefault(ln, []).append((col, name))
    for ln, sitios in per_line.items():
        line = lines[ln - 1]
        for col, name in sorted(sitios, reverse=True):
            if line[col:col + len(name)] != name:
                raise AssertionError(
                    f"linea {ln} col {col}: se esperaba {name!r} y hay "
                    f"{line[col:col + len(name)]!r}")
            line = line[:col] + f"{OBJETO}.{name}" + line[col + len(name):]
        lines[ln - 1] = line

    # 2) remove (or prune) the `global` statements
    quitados = 0
    for node in sorted(v.globales_decl, key=lambda n: -n.lineno):
        restantes = [n for n in node.names if n not in fields]
        ln = node.lineno - 1
        sangria = lines[ln][:len(lines[ln]) - len(lines[ln].lstrip())]
        if restantes:
            lines[ln] = f"{sangria}global {', '.join(restantes)}\n"
        else:
            lines[ln] = ""
        quitados += 1

    return "".join(lines), len(v.hits), quitados


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fields", help="comma-separated list")
    ap.add_argument("--list", dest="list_only", action="store_true")
    ap.add_argument("--main", default=str(PROJECT_ROOT / "main.py"))
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    main_py = Path(args.main)
    text = main_py.read_text(encoding="utf-8")

    if args.list_only:
        a = analizar(main_py)
        tree = ast.parse(text)
        cuenta = {}
        for n in ast.walk(tree):
            if isinstance(n, ast.Name) and n.id in a["mutables"]:
                cuenta[n.id] = cuenta.get(n.id, 0) + 1
        print(f"{len(a['mutables'])} module-level state pieces:")
        for k, v in sorted(cuenta.items(), key=lambda x: -x[1]):
            print(f"  {v:4d}  {k}")
        return 0

    fields = [c.strip() for c in (args.fields or "").split(",") if c.strip()]
    if not fields:
        print("nothing to migrate (use --fields)")
        return 1

    nuevo, n, g = migrate(text, fields)
    print(f"campos      : {len(fields)}")
    print(f"reescrituras: {n}")
    print(f"`global` podados/eliminados: {g}")
    if not args.apply:
        print("\n(dry run; use --apply to write)")
        return 0
    ast.parse(nuevo)          # do not write something that does not parse
    main_py.write_text(nuevo)
    print(f"\nwritten {main_py}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
