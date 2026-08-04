"""Extracts the PURE bindings of a line range from main.py into a package module.

It is the mechanism of waves 1-2 of the refactor (docs/project-history.md).
It moves contiguous LINE RANGES, not individual statements, so the comments
travel with what they document: in main.py the comments are real
documentation (the why of every constant, with references to concrete games), and
losing them would be the worst possible outcome of a refactor that exists to make the
code more readable.

WHAT COUNTS AS PURE
  A binding `NAME = <expr>` whose expression only uses literals and other names
  already classified as pure. Excluded are:
    * anything that depends on runtime (`card_table`, `all_card_data()`, deck.csv...);
    * any attribute access or call that is not to a safe builtin;
    * and -- the trap that really matters -- the names MUTATED somewhere.

THE TRAP OF THE MUTATED NAMES
  `my_deck = []` looks like a perfect constant: the value is a literal. But three
  lines below it is filled by reading deck.csv, and `agent()` returns it whole on the
  mulligan. Moving it would have left the agent's deck in another module with
  main.py mutating the same object by accident. That is why every name that
  receives `.append/.update/.add/...`, a subscript store, a `global` or an
  `augassign` is detected, and left where it is.

Usage:
    python utils/extraer_puros.py --desde 40 --hasta 1008 --destino ptcg/cartas/ids.py
    python utils/extraer_puros.py ... --aplicar     # without this, it only reports
"""

import argparse
import ast
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Builtins whose call introduces no runtime dependencies.
SEGUROS = {"frozenset", "set", "dict", "tuple", "list", "range", "len",
           "sorted", "int", "str"}

# Methods that reveal a name is NOT a constant.
MUTADORES = {"append", "extend", "update", "add", "pop", "clear", "insert",
             "remove", "discard", "setdefault", "sort"}

HEADER = '''"""{titulo}

Extraido VERBATIM de main.py por utils/extraer_puros.py
(docs/project-history.md). Aqui NO hay logica: solo constantes que
dependen unicamente de literales. Este modulo no puede importar estado ni tocar
el simulador -- lo vigila utils/lint_arquitectura.py (R2).

main.py lo reexporta con `import *`, asi que el `__all__` del final tiene que
listar TODOS los nombres, incluidos los que empiezan por `_` (que `import *`
omitiria si no).
"""

'''


def mutated_names(arbol):
    """Names that are mutated at some point of the module: they are not constants."""
    mutados = set()
    for n in ast.walk(arbol):
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute):
            if n.func.attr in MUTADORES and isinstance(n.func.value, ast.Name):
                mutados.add(n.func.value.id)
        elif isinstance(n, ast.Subscript) and isinstance(n.ctx, (ast.Store, ast.Del)):
            if isinstance(n.value, ast.Name):
                mutados.add(n.value.id)
        elif isinstance(n, ast.Global):
            mutados.update(n.names)
        elif isinstance(n, ast.AugAssign) and isinstance(n.target, ast.Name):
            mutados.add(n.target.id)
    return mutados


def _es_puro(nodo, puros):
    for n in ast.walk(nodo):
        if isinstance(n, ast.Name):
            if n.id not in puros and n.id not in SEGUROS:
                return False
        elif isinstance(n, ast.Call):
            f = n.func
            if not (isinstance(f, ast.Name) and f.id in SEGUROS):
                return False
        elif isinstance(n, ast.Attribute):
            return False
    return True


def planificar(main_py, desde, hasta):
    """Returns (ranges, names): which lines would move and which bindings they contain."""
    src = main_py.read_text(encoding="utf-8")
    lines = src.splitlines(keepends=True)
    arbol = ast.parse(src)
    mutados = mutated_names(arbol)

    # What has ALREADY been extracted to the package counts as available: after the first wave,
    # `EVO_LINES = (Chikorita, Bayleef, ...)` references IDs that are no longer in
    # main.py, and without this it would look impure and would never be moved.
    import sys as _sys
    _sys.path.insert(0, str(PROJECT_ROOT / "utils"))
    from pureza import _constantes_del_paquete
    puros = {n: True for n in _constantes_del_paquete()}
    bloqueadas, movibles = set(), {}
    for nodo in arbol.body:
        a, b = nodo.lineno, nodo.end_lineno
        ok = False
        if (isinstance(nodo, ast.Assign) and len(nodo.targets) == 1
                and isinstance(nodo.targets[0], ast.Name)):
            name = nodo.targets[0].id
            if _es_puro(nodo.value, puros) and name not in mutados:
                puros[name] = True
                ok = True
                if desde <= a <= hasta:
                    movibles[a] = (b, name)
        if not ok or not (desde <= a <= hasta):
            bloqueadas.update(range(a, b + 1))

    es_movible = [False] * (len(lines) + 2)
    for a, (b, _) in movibles.items():
        for ln in range(a, b + 1):
            es_movible[ln] = True

    def suelta(ln):
        t = lines[ln - 1].strip()
        return t == "" or t.startswith("#")

    rangos, ln = [], desde
    while ln <= hasta:
        if not es_movible[ln]:
            ln += 1
            continue
        ini = ln
        while ini - 1 >= desde and suelta(ini - 1) and (ini - 1) not in bloqueadas:
            ini -= 1
        fin = ln
        while fin + 1 <= hasta and (es_movible[fin + 1]
                                    or (suelta(fin + 1) and (fin + 1) not in bloqueadas)):
            fin += 1
        while fin > ini and suelta(fin):      # the trailing comments belong to the
            fin -= 1                          # node that comes AFTERWARDS
        if not rangos or ini > rangos[-1][1]:
            rangos.append([ini, fin])
        else:
            rangos[-1][1] = max(rangos[-1][1], fin)
        ln = fin + 1

    names = [n for a, (b, n) in sorted(movibles.items())]

    # Names the moved code takes from modules that have ALREADY been extracted: they have to
    # be imported in the target or the new module blows up when loaded.
    from pureza import _mapa_paquete
    mapa = _mapa_paquete()
    propios = set(names)
    necesarios = {}
    for a, b in rangos:
        fragmento = "".join(lines[a - 1:b])
        try:
            sub = ast.parse(fragmento)
        except SyntaxError:
            continue
        for n in ast.walk(sub):
            if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load):
                if n.id in mapa and n.id not in propios:
                    necesarios.setdefault(mapa[n.id], set()).add(n.id)
    return lines, rangos, names, necesarios


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--desde", type=int, required=True)
    ap.add_argument("--hasta", type=int, required=True)
    ap.add_argument("--destino", required=True, help="ruta relativa, p.ej. ptcg/cartas/ids.py")
    ap.add_argument("--titulo", default="Constantes extraidas de main.py.")
    ap.add_argument("--main", default="main.py")
    ap.add_argument("--aplicar", action="store_true")
    args = ap.parse_args()

    main_py = PROJECT_ROOT / args.main
    lines, rangos, names, necesarios = planificar(main_py, args.desde, args.hasta)

    total = sum(b - a + 1 for a, b in rangos)
    print(f"rangos: {len(rangos)}   lineas: {total}   bindings: {len(names)}")
    for a, b in rangos:
        print(f"  {a:6d}-{b:<6d} ({b - a + 1:4d} l)  {lines[a - 1].strip()[:56]}")

    if not args.apply:
        print("\n(dry run; usa --aplicar para escribir)")
        return 0

    destino = PROJECT_ROOT / args.destino
    destino.parent.mkdir(parents=True, exist_ok=True)
    for paquete in (destino.parent, destino.parent.parent):
        ini = paquete / "__init__.py"
        if paquete != PROJECT_ROOT and not ini.exists():
            ini.write_text('"""Paquete del agente. Ver docs/project-history.md."""\n')

    body = ["".join(lines[a - 1:b]) for a, b in rangos]
    imports = "".join(
        f"from {mod} import {', '.join(sorted(ns))}\n"
        for mod, ns in sorted(necesarios.items()))
    if imports:
        imports += "\n\n"
    all_list = "__all__ = [\n" + "".join(f"    {n!r},\n" for n in names) + "]\n"
    destino.write_text(HEADER.format(titulo=args.titulo) + imports
                       + "\n".join(body) + "\n\n" + all_list)

    borrar = set()
    for a, b in rangos:
        borrar.update(range(a, b + 1))
    modulo = args.destino.replace("/", ".").removesuffix(".py")
    marca = f"from {modulo} import *  # noqa: F401,F403\n"
    salida, puesto = [], False
    for i, line in enumerate(lines, start=1):
        if i in borrar:
            if not puesto:
                salida.append(marca)
                puesto = True
            continue
        salida.append(line)
    main_py.write_text("".join(salida))

    print(f"\nescrito {destino}")
    print(f"{args.main}: {len(lines)} -> {len(salida)} lineas")
    print("OJO: el import se inserta donde estaba el primer rango; muevelo al "
          "bloque de cabecera (en Kaggle el dir del agente solo esta en sys.path "
          "mientras se ejecuta main.py).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
