"""Purity analysis at DEFINITION level: what can be taken out of main.py.

It is the precondition of waves 2 and 4 of the refactor
(docs/project-history.md): before moving a function one has to
PROVE that it does not touch mutable state or the runtime tables, not assume it.

A module-level definition is MOVABLE if everything it references and does not
define itself is:
  * a builtin, or an imported name (stdlib / cg.api),
  * a constant already extracted to the package (`ptcg.cartas.ids`),
  * a pure constant that is still in main.py (it does not block: it can be moved later),
  * or another movable definition.

It is a fixed point: it starts from "all of them are movable" and the ones that touch
something impure fall out, until none falls any more. What blocks them is always one of
three things, and knowing which one says which wave they belong to:

  * a mutable global (`ko_last_turn`, `plan`, ...)  -> it waits for wave 3;
  * a runtime table (`card_table`, `attack_table`) -> those tables have to
    be moved first;
  * another blocked definition -> it is dragged along with it.

Usage:
    python utils/pureza.py                 # a summary
    python utils/pureza.py --detalle       # plus why each one is blocked
"""

import argparse
import ast
import builtins
import sys
from collections import Counter
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

BUILTINS = set(dir(builtins))

# Module-level names that depend on loading (deck.csv, cg.api) and are
# therefore not pure constants.
RUNTIME = {"all_card", "card_table", "attack_table", "my_deck",
           "file_path", "csv", "file"}

# Methods that give away that a name is MUTATED (and therefore is not a constant).
MUTADORES = {"append", "extend", "update", "add", "pop", "clear", "insert",
             "remove", "discard", "setdefault", "sort"}


def mutated_names(arbol):
    """Names mutated at some point of the module: they are state, not constants.

    CAREFUL: this does NOT overlap with the `global` statements. Reassigning a scalar
    requires `global`; mutating a dict or a list does NOT. `ATTACK_ENERGY_REQ` is the real
    case: `_aplicar_impuesto_tera` rewrites entries in it on EVERY call to
    agent() (the Nighttime Mine tax) and 56 places read it, but it does not appear
    in any `global` statement. Without this check it would pass as a pure
    constant and be moved to a data module, hiding turn state inside
    what looks like a fixed table.
    """
    # Only the names BOUND AT MODULE LEVEL count. Without this filter, the
    # locals of `agent()` that get mutated (`score.append(...)`, `hand_counts[x]=y`)
    # would enter the list and would wrongly block definitions that merely
    # share a name with them.
    de_modulo = set()
    for n in arbol.body:
        if isinstance(n, ast.Assign):
            for t in n.targets:
                if isinstance(t, ast.Name):
                    de_modulo.add(t.id)
        elif isinstance(n, (ast.AnnAssign, ast.AugAssign)) and isinstance(n.target, ast.Name):
            de_modulo.add(n.target.id)
        elif isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            de_modulo.add(n.name)

    mutados = set()
    for n in ast.walk(arbol):
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute):
            if n.func.attr in MUTADORES and isinstance(n.func.value, ast.Name):
                mutados.add(n.func.value.id)
        elif isinstance(n, ast.Subscript) and isinstance(n.ctx, (ast.Store, ast.Del)):
            if isinstance(n.value, ast.Name):
                mutados.add(n.value.id)
        elif isinstance(n, ast.AugAssign) and isinstance(n.target, ast.Name):
            mutados.add(n.target.id)
    return mutados & de_modulo


def _args_de(nodo):
    a = nodo.args
    names = {x.arg for x in a.args + a.kwonlyargs + a.posonlyargs}
    if a.vararg:
        names.add(a.vararg.arg)
    if a.kwarg:
        names.add(a.kwarg.arg)
    return names


def free_names(nodo):
    """Names the definition uses and does not define itself.

    It collects the arguments of ALL the nested functions/lambdas, not only those
    of the root node: otherwise, the `self` of the methods of a dataclass appears as a
    free name and blocks the whole class (it really happened).
    """
    locales, usados = set(), set()
    for n in ast.walk(nodo):
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
            locales |= _args_de(n)
        if isinstance(n, ast.Name):
            if isinstance(n.ctx, (ast.Store, ast.Del)):
                locales.add(n.id)
            else:
                usados.add(n.id)
        elif isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and n is not nodo:
            locales.add(n.name)
        elif isinstance(n, (ast.Import, ast.ImportFrom)):
            for a in n.names:
                locales.add(a.asname or a.name.split(".")[0])
        elif isinstance(n, ast.ExceptHandler) and n.name:
            locales.add(n.name)
    return usados - locales


def _constantes_del_paquete():
    """The `__all__` of the modules already extracted to the package."""
    names = set()
    paquete = PROJECT_ROOT / "ptcg"
    if not paquete.is_dir():
        return names
    if str(PROJECT_ROOT) not in sys.path:
        sys.path.insert(0, str(PROJECT_ROOT))
    for path in paquete.rglob("*.py"):
        try:
            arbol = ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError:
            continue
        for nodo in arbol.body:
            if (isinstance(nodo, ast.Assign) and len(nodo.targets) == 1
                    and isinstance(nodo.targets[0], ast.Name)
                    and nodo.targets[0].id == "__all__"):
                try:
                    names.update(ast.literal_eval(nodo.value))
                except ValueError:
                    pass
            elif isinstance(nodo, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                names.add(nodo.name)
    return names


def _mapa_paquete():
    """exported name -> the package module that defines it (`ptcg.cartas.ids`...)."""
    mapa = {}
    paquete = PROJECT_ROOT / "ptcg"
    if not paquete.is_dir():
        return mapa
    for path in sorted(paquete.rglob("*.py")):
        if path.name == "__init__.py":
            continue
        dotted = path.relative_to(PROJECT_ROOT).with_suffix("")
        dotted = ".".join(dotted.parts)
        try:
            arbol = ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError:
            continue
        for nodo in arbol.body:
            if (isinstance(nodo, ast.Assign) and len(nodo.targets) == 1
                    and isinstance(nodo.targets[0], ast.Name)
                    and nodo.targets[0].id == "__all__"):
                try:
                    for n in ast.literal_eval(nodo.value):
                        mapa.setdefault(n, dotted)
                except ValueError:
                    pass
    return mapa


def analizar(main_py=None):
    main_py = Path(main_py or PROJECT_ROOT / "main.py")
    src = main_py.read_text(encoding="utf-8")
    arbol = ast.parse(src)

    importados = set()
    for n in arbol.body:
        if isinstance(n, ast.Import):
            importados.update((a.asname or a.name.split(".")[0]) for a in n.names)
        elif isinstance(n, ast.ImportFrom):
            for a in n.names:
                if a.name != "*":
                    importados.add(a.asname or a.name)

    del_paquete = _constantes_del_paquete()

    mutables = set()
    for n in ast.walk(arbol):
        if isinstance(n, ast.Global):
            mutables.update(n.names)
    # Mutable state that is NOT declared `global`: module-level dicts/lists
    # that somebody rewrites (see `nombres_mutados`).
    mutables |= mutated_names(arbol)

    definiciones, asignaciones = {}, {}
    for n in arbol.body:
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            definiciones[n.name] = n
        elif (isinstance(n, ast.Assign) and len(n.targets) == 1
              and isinstance(n.targets[0], ast.Name)):
            asignaciones[n.targets[0].id] = n

    const_main = set(asignaciones) - RUNTIME - mutables
    libres = {k: free_names(v) for k, v in definiciones.items()}

    movibles, razon = set(definiciones), {}
    cambio = True
    while cambio:
        cambio = False
        for name in sorted(movibles):
            for free in libres[name]:
                if (free in BUILTINS or free in importados or free in del_paquete
                        or free in movibles or free == name or free in const_main):
                    continue
                if free in mutables:
                    motivo = f"estado mutable `{free}`"
                elif free in RUNTIME:
                    motivo = f"runtime `{free}`"
                elif free in definiciones:
                    motivo = f"definicion bloqueada `{free}`"
                else:
                    motivo = f"desconocido `{free}`"
                movibles.discard(name)
                razon[name] = motivo
                cambio = True
                break

    return {
        "movibles": movibles, "razon": razon, "libres": libres,
        "definiciones": definiciones, "asignaciones": asignaciones,
        "importados": importados, "del_paquete": del_paquete,
        "const_main": const_main, "mutables": mutables,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--detalle", action="store_true")
    ap.add_argument("--main", default=None)
    args = ap.parse_args()

    a = analizar(args.main)
    defs, mov = a["definiciones"], a["movibles"]
    lines = sum(defs[n].end_lineno - defs[n].lineno + 1 for n in mov)

    print(f"definiciones de nivel de modulo : {len(defs)}")
    print(f"MOVIBLES (puras)                : {len(mov)}  ({lines} lineas)")
    print(f"bloqueadas                      : {len(defs) - len(mov)}")
    print()
    print("bloqueadas, por causa raiz:")
    for causa, n in Counter(r.split("`")[1] for r in a["razon"].values()).most_common(12):
        print(f"  {n:4d}  {causa}")

    if args.detail:
        print("\n=== MOVIBLES ===")
        for n in sorted(mov, key=lambda x: defs[x].lineno):
            print(f"  {defs[n].lineno:6d}  {n}")
        print("\n=== BLOQUEADAS ===")
        for n in sorted(a["razon"], key=lambda x: defs[x].lineno):
            print(f"  {defs[n].lineno:6d}  {n:45s} {a['razon'][n]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
