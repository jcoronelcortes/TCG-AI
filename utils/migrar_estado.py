"""Migrates module state from main.py to `ESTADO.<field>` (wave 3 of the refactor).

WHY IT IS DIFFERENT FROM THE PREVIOUS WAVES
  Waves 1, 2 and 4 MOVE lines without touching them. This one REWRITES them: `ko_last_turn`
  becomes `ESTADO.ko_last_turn` in every place. That is why the equivalence gate
  (utils/sombra.py) stops being a safety net and becomes the main instrument.

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
    python utils/migrar_estado.py --campos plan,pre_turn          # a dry run
    python utils/migrar_estado.py --campos plan,pre_turn --aplicar
    python utils/migrar_estado.py --listar                        # what is left
"""

import argparse
import ast
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "utils"))

from pureza import analizar  # noqa: E402

OBJETO = "ESTADO"


class _Ambito(ast.NodeVisitor):
    """Collects the Name nodes that DO refer to the given globals."""

    def __init__(self, campos):
        self.campos = campos
        self.hits = []          # (lineno, col_offset, name)
        self.globales_decl = []  # (lineno, col_offset, end_col, names)

    # --- module level --------------------------------------------------------
    def visit_Module(self, nodo):
        for hijo in nodo.body:
            self._visitar(hijo, locales=set(), globales=set(self.campos))

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

    def _visitar(self, nodo, locales, globales):
        if isinstance(nodo, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
            loc, decl = self._locales_de(nodo)
            # visible as global: what is declared `global` + what is not local
            g = (globales - loc) | (decl & self.campos)
            for n in ast.iter_child_nodes(nodo):
                self._visitar(n, loc, g)
            return
        if isinstance(nodo, ast.ClassDef):
            for n in ast.iter_child_nodes(nodo):
                self._visitar(n, locales, globales)
            return
        if isinstance(nodo, ast.Global):
            if set(nodo.names) & self.campos:
                self.globales_decl.append(nodo)
            return
        if isinstance(nodo, ast.Attribute):
            # `ESTADO.plan` already migrated: do not touch the `plan` again
            if isinstance(nodo.value, ast.Name) and nodo.value.id == OBJETO:
                return
        if isinstance(nodo, ast.Name) and nodo.id in self.campos and nodo.id in globales:
            self.hits.append((nodo.lineno, nodo.col_offset, nodo.id))
        for n in ast.iter_child_nodes(nodo):
            self._visitar(n, locales, globales)


def migrar(texto, campos):
    """Returns (new_text, n_rewrites, n_globals_removed)."""
    campos = set(campos)
    arbol = ast.parse(texto)
    v = _Ambito(campos)
    v.visit(arbol)

    lineas = texto.splitlines(keepends=True)

    # 1) rewrite the Name nodes, per line and from right to left
    por_linea = {}
    for ln, col, nombre in v.hits:
        por_linea.setdefault(ln, []).append((col, nombre))
    for ln, sitios in por_linea.items():
        linea = lineas[ln - 1]
        for col, nombre in sorted(sitios, reverse=True):
            if linea[col:col + len(nombre)] != nombre:
                raise AssertionError(
                    f"linea {ln} col {col}: se esperaba {nombre!r} y hay "
                    f"{linea[col:col + len(nombre)]!r}")
            linea = linea[:col] + f"{OBJETO}.{nombre}" + linea[col + len(nombre):]
        lineas[ln - 1] = linea

    # 2) remove (or prune) the `global` statements
    quitados = 0
    for nodo in sorted(v.globales_decl, key=lambda n: -n.lineno):
        restantes = [n for n in nodo.names if n not in campos]
        ln = nodo.lineno - 1
        sangria = lineas[ln][:len(lineas[ln]) - len(lineas[ln].lstrip())]
        if restantes:
            lineas[ln] = f"{sangria}global {', '.join(restantes)}\n"
        else:
            lineas[ln] = ""
        quitados += 1

    return "".join(lineas), len(v.hits), quitados


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--campos", help="lista separada por comas")
    ap.add_argument("--listar", action="store_true")
    ap.add_argument("--main", default=str(PROJECT_ROOT / "main.py"))
    ap.add_argument("--aplicar", action="store_true")
    args = ap.parse_args()

    main_py = Path(args.main)
    texto = main_py.read_text(encoding="utf-8")

    if args.listar:
        a = analizar(main_py)
        arbol = ast.parse(texto)
        cuenta = {}
        for n in ast.walk(arbol):
            if isinstance(n, ast.Name) and n.id in a["mutables"]:
                cuenta[n.id] = cuenta.get(n.id, 0) + 1
        print(f"{len(a['mutables'])} piezas de estado de modulo:")
        for k, v in sorted(cuenta.items(), key=lambda x: -x[1]):
            print(f"  {v:4d}  {k}")
        return 0

    campos = [c.strip() for c in (args.campos or "").split(",") if c.strip()]
    if not campos:
        print("nada que migrar (usa --campos)")
        return 1

    nuevo, n, g = migrar(texto, campos)
    print(f"campos      : {len(campos)}")
    print(f"reescrituras: {n}")
    print(f"`global` podados/eliminados: {g}")
    if not args.aplicar:
        print("\n(dry run; usa --aplicar para escribir)")
        return 0
    ast.parse(nuevo)          # do not write something that does not parse
    main_py.write_text(nuevo)
    print(f"\nescrito {main_py}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
