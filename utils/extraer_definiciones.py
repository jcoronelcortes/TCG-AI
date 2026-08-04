"""Moves PURE definitions out of main.py into package modules (waves 2 and 4).

It complements `utils/extraer_puros.py` (which moves constants): this moves
functions and classes, which bring two problems constants do not have.

  1. CLOSURE. If a moved function calls another that stays in main.py, it blows up
     at decision time. Before writing anything it is checked that EVERYTHING the
     chosen set references resolves: builtins, imports, constants already
     extracted, another module of the same batch, or constants that are still in main.py
     (those get re-imported from there... no: they are required to be in the package, see
     `--permitir-const-main`).

  2. IMPORTS. Each target module needs exactly the imports it uses. They are
     derived from the free names of the moved set and distributed according to where
     each name came from in main.py (stdlib, cg.api, ptcg.cartas.ids).

Purity is decided by `utils/pureza.py`; here only what that one already
declared movable is moved, and it aborts if something in the batch is not.

The batch is described in a Python file with a `MODULOS` dict:

    MODULOS = {
        "ptcg/motor/reglas.py": {
            "titulo": "Rules engine: ...",
            "nombres": ["_ReglaFija", "_Ajuste", "_resolver_reglas"],
        },
    }

Usage:
    python utils/extraer_definiciones.py lote.py            # a dry run
    python utils/extraer_definiciones.py lote.py --aplicar
"""

import argparse
import ast
import builtins
import runpy
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "utils"))

from pureza import analizar, BUILTINS, _mapa_paquete, free_names  # noqa: E402

HEADER = '''"""{titulo}

Extraido VERBATIM de main.py por utils/extraer_definiciones.py
(docs/project-history.md). Su pureza esta comprobada por
utils/pureza.py: nada de aqui toca el estado mutable ni las tablas de runtime.
"""

'''


def _origen_de_imports(arbol):
    """imported name -> the import statement that brings it."""
    origen = {}
    for n in arbol.body:
        if isinstance(n, ast.Import):
            for a in n.names:
                origen[a.asname or a.name.split(".")[0]] = (
                    f"import {a.name}" + (f" as {a.asname}" if a.asname else ""))
        elif isinstance(n, ast.ImportFrom) and n.module:
            for a in n.names:
                if a.name == "*":
                    continue
                origen[a.asname or a.name] = ("from", n.module, a.name, a.asname)
    return origen


def _bloque_con_comentarios(lines, nodo):
    """The (start, end) range of the definition, dragging its header comment along.

    The comment right above a function documents it: if it stays
    in main.py, the function reaches the new module without its why.
    """
    ini = nodo.lineno
    for d in getattr(nodo, "decorator_list", []):
        ini = min(ini, d.lineno)
    while ini - 1 >= 1:
        t = lines[ini - 2].strip()
        if t.startswith("#"):
            ini -= 1
        else:
            break
    return ini, nodo.end_lineno


def planificar(lote, main_py):
    a = analizar(main_py)
    src = Path(main_py).read_text(encoding="utf-8")
    lines = src.splitlines(keepends=True)
    arbol = ast.parse(src)
    origen = _origen_de_imports(arbol)
    mapa = _mapa_paquete()

    donde = {}
    for mod, spec in lote.items():
        for n in spec["nombres"]:
            donde[n] = mod

    # A batch can list `def`/`class` and also ASSIGNMENTS: the
    # `_REGLAS_*`/`_AJUSTES_*` tables of the rules engine are data belonging to the
    # module of their card, and without them the scorer cannot move.
    nodos = dict(a["definiciones"])
    libres = dict(a["libres"])
    for n, nodo in a["asignaciones"].items():
        nodos.setdefault(n, nodo)
        libres.setdefault(n, free_names(nodo))

    problemas = []
    for n in donde:
        if n not in nodos:
            problemas.append(f"{n}: no esta a nivel de modulo en main.py")
        elif n in a["definiciones"] and n not in a["movibles"]:
            problemas.append(f"{n}: NO es puro ({a['razon'].get(n, '?')})")
        elif n in a["asignaciones"] and n in a["mutables"]:
            problemas.append(f"{n}: es estado MUTABLE, no una tabla constante")

    plan = {}
    for mod, spec in lote.items():
        names = spec["nombres"]
        imports_stdlib, imports_from, del_paquete, cruzados = set(), {}, {}, {}
        for n in names:
            if n not in libres:
                continue
            for free in libres[n]:
                if free in BUILTINS or free in names:
                    continue
                if free in donde and donde[free] != mod:
                    cruzados.setdefault(donde[free], set()).add(free)
                elif free in donde:
                    continue
                elif free in a["del_paquete"]:
                    # from WHICH package module it comes: `card_table` is in
                    # ptcg.cartas.tablas, not in ptcg.cartas.ids.
                    origen_mod = mapa.get(free)
                    # When MERGING, the name may already live in the target module
                    # itself (an earlier batch put it there): importing it would be a
                    # self-import and blows up with "partially initialized module".
                    if origen_mod == mod.replace("/", ".").removesuffix(".py"):
                        continue
                    if origen_mod is None:
                        problemas.append(f"{mod}: `{free}` esta en el paquete pero "
                                         "no se sabe en que modulo")
                    else:
                        del_paquete.setdefault(origen_mod, set()).add(free)
                elif free in origen:
                    o = origen[free]
                    if isinstance(o, str):
                        imports_stdlib.add(o)
                    else:
                        imports_from.setdefault(o[1], set()).add((o[2], o[3]))
                elif free in a["const_main"]:
                    problemas.append(
                        f"{mod}: `{n}` usa la constante `{free}`, que sigue en main.py "
                        f"(muevela antes con extraer_puros.py)")
                else:
                    problemas.append(f"{mod}: `{n}` usa `{free}`, sin resolver")

        rangos = []
        for n in names:
            rangos.append((_bloque_con_comentarios(lines, nodos[n]), n))
        rangos.sort()
        plan[mod] = {
            "titulo": spec.get("titulo", "Extraido de main.py."),
            "nombres": names, "rangos": rangos,
            "imports_stdlib": sorted(imports_stdlib),
            "imports_from": imports_from, "del_paquete": del_paquete,
            "cruzados": cruzados,
        }
    return plan, problemas, lines


def _imports_header(info, mod_actual):
    partes = []
    for imp in info["imports_stdlib"]:
        partes.append(imp)
    for modulo, names in sorted(info["imports_from"].items()):
        ns = ", ".join(sorted(n if not alias else f"{n} as {alias}" for n, alias in names))
        partes.append(f"from {modulo} import {ns}")
    for modulo, names in sorted(info["del_paquete"].items()):
        partes.append(f"from {modulo} import " + ", ".join(sorted(names)))
    for otro, names in sorted(info["cruzados"].items()):
        dotted = otro.replace("/", ".").removesuffix(".py")
        partes.append(f"from {dotted} import " + ", ".join(sorted(names)))
    return ("\n".join(partes) + "\n\n\n") if partes else ""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("lote", help="fichero .py con el dict MODULOS")
    ap.add_argument("--main", default=str(PROJECT_ROOT / "main.py"))
    ap.add_argument("--aplicar", action="store_true")
    args = ap.parse_args()

    lote = runpy.run_path(args.lote)["MODULOS"]
    plan, problemas, lines = planificar(lote, args.main)

    total = 0
    for mod, info in plan.items():
        n_lines = sum(b - a + 1 for (a, b), _ in info["rangos"])
        total += n_lines
        print(f"{mod}: {len(info['nombres'])} definiciones, {n_lines} lineas")
        print(f"    paquete  : {sum(len(v) for v in info['del_paquete'].values())} nombres")
        if info["cruzados"]:
            print(f"    cruzados : { {k: sorted(v) for k, v in info['cruzados'].items()} }")
    print(f"\nTOTAL: {total} lineas")

    if problemas:
        print("\n⚠ PROBLEMAS (no se aplica nada):")
        for p in problemas:
            print("  -", p)
        return 1

    if not args.apply:
        print("\n(dry run; usa --aplicar para escribir)")
        return 0

    borrar, marcas = set(), []
    for mod, info in plan.items():
        destino = PROJECT_ROOT / mod
        destino.parent.mkdir(parents=True, exist_ok=True)
        p = destino.parent
        while p != PROJECT_ROOT:
            ini = p / "__init__.py"
            if not ini.exists():
                ini.write_text('"""Paquete del agente. Ver docs/project-history.md."""\n')
            p = p.parent

        body = []
        for (a, b), _ in info["rangos"]:
            body.append("".join(lines[a - 1:b]).rstrip("\n"))
            borrar.update(range(a, b + 1))

        nuevos = "\n\n\n".join(body)
        if destino.exists():
            # MERGE with what is already there: a module is filled over several batches
            # (e.g. dano.py first receives what does not depend on card_table and
            # then the rest). Its header is kept and the import lines it is missing
            # are added.
            previo = destino.read_text()
            cabeza, _, cola = previo.rpartition("\n\n__all__ = [")
            viejos = [ln.strip().strip("',") for ln in cola.splitlines()
                      if ln.strip().startswith(("'", '"'))]
            for line in _imports_header(info, mod).rstrip("\n").splitlines():
                if line and line not in cabeza:
                    marca_doc = cabeza.index('"""', cabeza.index('"""') + 3) + 4
                    cabeza = cabeza[:marca_doc] + "\n" + line + cabeza[marca_doc:]
            all_names = viejos + info["nombres"]
            text = cabeza.rstrip("\n") + "\n\n\n" + nuevos
        else:
            all_names = info["nombres"]
            text = (HEADER.format(titulo=info["titulo"])
                     + _imports_header(info, mod) + nuevos)

        text += "\n\n__all__ = [\n" + "".join(f"    {n!r},\n" for n in all_names) + "]\n"
        destino.write_text(text)
        dotted = mod.replace("/", ".").removesuffix(".py")
        marca = f"from {dotted} import *  # noqa: F401,F403\n"
        if marca not in marcas:
            marcas.append(marca)
        print(f"{'fusionado' if destino.exists() else 'escrito'} {mod}"
              f" (+{len(info['nombres'])} definiciones)")

    main_py = Path(args.main)
    salida, puesto = [], False
    for i, line in enumerate(lines, start=1):
        if i in borrar:
            if not puesto:
                salida.extend(marcas)
                puesto = True
            continue
        salida.append(line)
    main_py.write_text("".join(salida))
    print(f"\nmain.py: {len(lines)} -> {len(salida)} lineas")
    print("OJO: mueve los imports al bloque de cabecera (I1a).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
