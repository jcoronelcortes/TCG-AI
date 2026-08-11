"""Moves PURE definitions out of main.py into package modules (waves 2 and 4).

It complements `utils/extract_pure.py` (which moves constants): this moves
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

Purity is decided by `utils/purity.py`; here only what that one already
declared movable is moved, and it aborts if something in the batch is not.

The batch is described in a Python file with a `MODULOS` dict:

    MODULOS = {
        "ptcg/engine/rules.py": {
            "titulo": "Rules engine: ...",
            "nombres": ["_FixedRule", "_Adjustment", "_resolve_rules"],
        },
    }

Usage:
    python utils/extract_definitions.py batch.py            # a dry run
    python utils/extract_definitions.py batch.py --apply
"""

import argparse
import ast
import builtins
import runpy
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "utils"))

from purity import analyse, BUILTINS, _mapa_paquete, free_names  # noqa: E402

HEADER = '''"""{titulo}

Extraido VERBATIM de main.py por utils/extract_definitions.py
(docs/project-history.md). Su pureza esta comprobada por
utils/purity.py: nada de aqui toca el estado mutable ni las tablas de runtime.
"""

'''


def _origen_de_imports(tree):
    """imported name -> the import statement that brings it."""
    source_path = {}
    for n in tree.body:
        if isinstance(n, ast.Import):
            for a in n.names:
                source_path[a.asname or a.name.split(".")[0]] = (
                    f"import {a.name}" + (f" as {a.asname}" if a.asname else ""))
        elif isinstance(n, ast.ImportFrom) and n.module:
            for a in n.names:
                if a.name == "*":
                    continue
                source_path[a.asname or a.name] = ("from", n.module, a.name, a.asname)
    return source_path


def _block_with_comments(lines, node):
    """The (start, end) range of the definition, dragging its header comment along.

    The comment right above a function documents it: if it stays
    in main.py, the function reaches the new module without its why.
    """
    ini = node.lineno
    for d in getattr(node, "decorator_list", []):
        ini = min(ini, d.lineno)
    while ini - 1 >= 1:
        t = lines[ini - 2].strip()
        if t.startswith("#"):
            ini -= 1
        else:
            break
    return ini, node.end_lineno


def plan_extraction(batch, main_py):
    a = analyse(main_py)
    src = Path(main_py).read_text(encoding="utf-8")
    lines = src.splitlines(keepends=True)
    tree = ast.parse(src)
    source_path = _origen_de_imports(tree)
    mapa = _mapa_paquete()

    where = {}
    for mod, spec in batch.items():
        for n in spec["nombres"]:
            where[n] = mod

    # A batch can list `def`/`class` and also ASSIGNMENTS: the
    # `_REGLAS_*`/`_AJUSTES_*` tables of the rules engine are data belonging to the
    # module of their card, and without them the scorer cannot move.
    nodes = dict(a["definiciones"])
    free_by_name = dict(a["libres"])
    for n, node in a["asignaciones"].items():
        nodes.setdefault(n, node)
        free_by_name.setdefault(n, free_names(node))

    problems = []
    for n in where:
        if n not in nodes:
            problems.append(f"{n}: no esta a nivel de modulo en main.py")
        elif n in a["definiciones"] and n not in a["movibles"]:
            problems.append(f"{n}: NO es puro ({a['razon'].get(n, '?')})")
        elif n in a["asignaciones"] and n in a["mutables"]:
            problems.append(f"{n}: es estado MUTABLE, no una tabla constante")

    plan = {}
    for mod, spec in batch.items():
        names = spec["nombres"]
        imports_stdlib, imports_from, of_the_package, cruzados = set(), {}, {}, {}
        for n in names:
            if n not in free_by_name:
                continue
            for free in free_by_name[n]:
                if free in BUILTINS or free in names:
                    continue
                if free in where and where[free] != mod:
                    cruzados.setdefault(where[free], set()).add(free)
                elif free in where:
                    continue
                elif free in a["of_the_package"]:
                    # from WHICH package module it comes: `card_table` is in
                    # ptcg.cartas.tablas, not in ptcg.cartas.ids.
                    origen_mod = mapa.get(free)
                    # When MERGING, the name may already live in the target module
                    # itself (an earlier batch put it there): importing it would be a
                    # self-import and blows up with "partially initialized module".
                    if origen_mod == mod.replace("/", ".").removesuffix(".py"):
                        continue
                    if origen_mod is None:
                        problems.append(f"{mod}: `{free}` esta en el paquete pero "
                                         "no se sabe en que modulo")
                    else:
                        of_the_package.setdefault(origen_mod, set()).add(free)
                elif free in source_path:
                    o = source_path[free]
                    if isinstance(o, str):
                        imports_stdlib.add(o)
                    else:
                        imports_from.setdefault(o[1], set()).add((o[2], o[3]))
                elif free in a["const_main"]:
                    problems.append(
                        f"{mod}: `{n}` usa la constante `{free}`, que sigue en main.py "
                        f"(muevela antes con extraer_puros.py)")
                else:
                    problems.append(f"{mod}: `{n}` usa `{free}`, sin resolver")

        ranges = []
        for n in names:
            ranges.append((_block_with_comments(lines, nodes[n]), n))
        ranges.sort()
        plan[mod] = {
            "title": spec.get("title", "Extraido de main.py."),
            "nombres": names, "rangos": ranges,
            "imports_stdlib": sorted(imports_stdlib),
            "imports_from": imports_from, "of_the_package": of_the_package,
            "cruzados": cruzados,
        }
    return plan, problems, lines


def _imports_header(info, mod_actual):
    partes = []
    for imp in info["imports_stdlib"]:
        partes.append(imp)
    for module_name, names in sorted(info["imports_from"].items()):
        ns = ", ".join(sorted(n if not alias else f"{n} as {alias}" for n, alias in names))
        partes.append(f"from {module_name} import {ns}")
    for module_name, names in sorted(info["of_the_package"].items()):
        partes.append(f"from {module_name} import " + ", ".join(sorted(names)))
    for otro, names in sorted(info["cruzados"].items()):
        dotted = otro.replace("/", ".").removesuffix(".py")
        partes.append(f"from {dotted} import " + ", ".join(sorted(names)))
    return ("\n".join(partes) + "\n\n\n") if partes else ""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("batch", help="a .py file holding the MODULOS dict")
    ap.add_argument("--main", default=str(PROJECT_ROOT / "main.py"))
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    batch = runpy.run_path(args.batch)["MODULOS"]
    plan, problems, lines = plan_extraction(batch, args.main)

    total = 0
    for mod, info in plan.items():
        n_lines = sum(b - a + 1 for (a, b), _ in info["rangos"])
        total += n_lines
        print(f"{mod}: {len(info['nombres'])} definiciones, {n_lines} lines")
        print(f"    paquete  : {sum(len(v) for v in info['of_the_package'].values())} nombres")
        if info["cruzados"]:
            print(f"    cruzados : { {k: sorted(v) for k, v in info['cruzados'].items()} }")
    print(f"\nTOTAL: {total} lines")

    if problems:
        print("\n⚠ PROBLEMS (nothing is applied):")
        for p in problems:
            print("  -", p)
        return 1

    if not args.apply:
        print("\n(dry run; use --apply to write)")
        return 0

    borrar, marcas = set(), []
    for mod, info in plan.items():
        target_path = PROJECT_ROOT / mod
        target_path.parent.mkdir(parents=True, exist_ok=True)
        p = target_path.parent
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
        if target_path.exists():
            # MERGE with what is already there: a module is filled over several batches
            # (e.g. dano.py first receives what does not depend on card_table and
            # then the rest). Its header is kept and the import lines it is missing
            # are added.
            previo = target_path.read_text()
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
            text = (HEADER.format(title=info["title"])
                     + _imports_header(info, mod) + nuevos)

        text += "\n\n__all__ = [\n" + "".join(f"    {n!r},\n" for n in all_names) + "]\n"
        target_path.write_text(text)
        dotted = mod.replace("/", ".").removesuffix(".py")
        marca = f"from {dotted} import *  # noqa: F401,F403\n"
        if marca not in marcas:
            marcas.append(marca)
        print(f"{'fusionado' if target_path.exists() else 'written'} {mod}"
              f" (+{len(info['nombres'])} definiciones)")

    main_py = Path(args.main)
    output, puesto = [], False
    for i, line in enumerate(lines, start=1):
        if i in borrar:
            if not puesto:
                output.extend(marcas)
                puesto = True
            continue
        output.append(line)
    main_py.write_text("".join(output))
    print(f"\nmain.py: {len(lines)} -> {len(output)} lines")
    print("NOTE: move the imports into the header block (I1a).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
