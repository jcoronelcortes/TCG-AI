"""Saca definiciones PURAS de main.py a modulos del paquete (olas 2 y 4).

Complementa a `utils/extraer_puros.py` (que mueve constantes): esto mueve
funciones y clases, que traen dos problemas que las constantes no tienen.

  1. CIERRE. Si una funcion movida llama a otra que se queda en main.py, revienta
     en tiempo de decision. Antes de escribir nada se comprueba que TODO lo que
     el conjunto elegido referencia se resuelve: builtins, imports, constantes ya
     extraidas, otro modulo del mismo lote, o constantes que siguen en main.py
     (esas se reimportan desde alli... no: se exige que sean del paquete, ver
     `--permitir-const-main`).

  2. IMPORTS. Cada modulo destino necesita exactamente los imports que usa. Se
     derivan de los nombres libres del conjunto movido y se reparten segun de
     donde venia cada nombre en main.py (stdlib, cg.api, ptcg.cartas.ids).

La pureza la decide `utils/pureza.py`; aqui solo se mueve lo que aquel ya
declaro movible, y se aborta si algo del lote no lo es.

El lote se describe en un fichero Python con un dict `MODULOS`:

    MODULOS = {
        "ptcg/motor/reglas.py": {
            "titulo": "Motor de reglas: ...",
            "nombres": ["_ReglaFija", "_Ajuste", "_resolver_reglas"],
        },
    }

Uso:
    python utils/extraer_definiciones.py lote.py            # dry run
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

from pureza import analizar, BUILTINS, _mapa_paquete  # noqa: E402

CABECERA = '''"""{titulo}

Extraido VERBATIM de main.py por utils/extraer_definiciones.py
(docs/main-refactor-arquitectura.md). Su pureza esta comprobada por
utils/pureza.py: nada de aqui toca el estado mutable ni las tablas de runtime.
"""

'''


def _origen_de_imports(arbol):
    """nombre importado -> sentencia de import que lo trae."""
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


def _bloque_con_comentarios(lineas, nodo):
    """Rango (ini, fin) de la definicion, arrastrando su comentario de cabecera.

    El comentario que va justo encima de una funcion la documenta: si se queda
    en main.py, la funcion llega al modulo nuevo sin su porque.
    """
    ini = nodo.lineno
    for d in getattr(nodo, "decorator_list", []):
        ini = min(ini, d.lineno)
    while ini - 1 >= 1:
        t = lineas[ini - 2].strip()
        if t.startswith("#"):
            ini -= 1
        else:
            break
    return ini, nodo.end_lineno


def planificar(lote, main_py):
    a = analizar(main_py)
    src = Path(main_py).read_text(encoding="utf-8")
    lineas = src.splitlines(keepends=True)
    arbol = ast.parse(src)
    origen = _origen_de_imports(arbol)
    mapa = _mapa_paquete()

    donde = {}
    for mod, spec in lote.items():
        for n in spec["nombres"]:
            donde[n] = mod

    problemas = []
    for n in donde:
        if n not in a["definiciones"]:
            problemas.append(f"{n}: no es una definicion de nivel de modulo de main.py")
        elif n not in a["movibles"]:
            problemas.append(f"{n}: NO es puro ({a['razon'].get(n, '?')})")

    plan = {}
    for mod, spec in lote.items():
        nombres = spec["nombres"]
        imports_stdlib, imports_from, del_paquete, cruzados = set(), {}, {}, {}
        for n in nombres:
            if n not in a["libres"]:
                continue
            for libre in a["libres"][n]:
                if libre in BUILTINS or libre in nombres:
                    continue
                if libre in donde and donde[libre] != mod:
                    cruzados.setdefault(donde[libre], set()).add(libre)
                elif libre in donde:
                    continue
                elif libre in a["del_paquete"]:
                    # de QUE modulo del paquete viene: `card_table` esta en
                    # ptcg.cartas.tablas, no en ptcg.cartas.ids.
                    origen_mod = mapa.get(libre)
                    if origen_mod is None:
                        problemas.append(f"{mod}: `{libre}` esta en el paquete pero "
                                         "no se sabe en que modulo")
                    else:
                        del_paquete.setdefault(origen_mod, set()).add(libre)
                elif libre in origen:
                    o = origen[libre]
                    if isinstance(o, str):
                        imports_stdlib.add(o)
                    else:
                        imports_from.setdefault(o[1], set()).add((o[2], o[3]))
                elif libre in a["const_main"]:
                    problemas.append(
                        f"{mod}: `{n}` usa la constante `{libre}`, que sigue en main.py "
                        f"(muevela antes con extraer_puros.py)")
                else:
                    problemas.append(f"{mod}: `{n}` usa `{libre}`, sin resolver")

        rangos = []
        for n in nombres:
            rangos.append((_bloque_con_comentarios(lineas, a["definiciones"][n]), n))
        rangos.sort()
        plan[mod] = {
            "titulo": spec.get("titulo", "Extraido de main.py."),
            "nombres": nombres, "rangos": rangos,
            "imports_stdlib": sorted(imports_stdlib),
            "imports_from": imports_from, "del_paquete": del_paquete,
            "cruzados": cruzados,
        }
    return plan, problemas, lineas


def _cabecera_imports(info, mod_actual):
    partes = []
    for imp in info["imports_stdlib"]:
        partes.append(imp)
    for modulo, nombres in sorted(info["imports_from"].items()):
        ns = ", ".join(sorted(n if not alias else f"{n} as {alias}" for n, alias in nombres))
        partes.append(f"from {modulo} import {ns}")
    for modulo, nombres in sorted(info["del_paquete"].items()):
        partes.append(f"from {modulo} import " + ", ".join(sorted(nombres)))
    for otro, nombres in sorted(info["cruzados"].items()):
        dotted = otro.replace("/", ".").removesuffix(".py")
        partes.append(f"from {dotted} import " + ", ".join(sorted(nombres)))
    return ("\n".join(partes) + "\n\n\n") if partes else ""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("lote", help="fichero .py con el dict MODULOS")
    ap.add_argument("--main", default=str(PROJECT_ROOT / "main.py"))
    ap.add_argument("--aplicar", action="store_true")
    args = ap.parse_args()

    lote = runpy.run_path(args.lote)["MODULOS"]
    plan, problemas, lineas = planificar(lote, args.main)

    total = 0
    for mod, info in plan.items():
        n_lineas = sum(b - a + 1 for (a, b), _ in info["rangos"])
        total += n_lineas
        print(f"{mod}: {len(info['nombres'])} definiciones, {n_lineas} lineas")
        print(f"    paquete  : {sum(len(v) for v in info['del_paquete'].values())} nombres")
        if info["cruzados"]:
            print(f"    cruzados : { {k: sorted(v) for k, v in info['cruzados'].items()} }")
    print(f"\nTOTAL: {total} lineas")

    if problemas:
        print("\n⚠ PROBLEMAS (no se aplica nada):")
        for p in problemas:
            print("  -", p)
        return 1

    if not args.aplicar:
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
                ini.write_text('"""Paquete del agente. Ver docs/main-refactor-arquitectura.md."""\n')
            p = p.parent

        cuerpo = []
        for (a, b), _ in info["rangos"]:
            cuerpo.append("".join(lineas[a - 1:b]).rstrip("\n"))
            borrar.update(range(a, b + 1))

        nuevos = "\n\n\n".join(cuerpo)
        if destino.exists():
            # FUSIONAR con lo que ya hay: un modulo se llena en varios lotes
            # (p.ej. dano.py recibe primero lo que no depende de card_table y
            # despues el resto). Se conserva su cabecera y se le anaden las
            # lineas de import que le falten.
            previo = destino.read_text()
            cabeza, _, cola = previo.rpartition("\n\n__all__ = [")
            viejos = [ln.strip().strip("',") for ln in cola.splitlines()
                      if ln.strip().startswith(("'", '"'))]
            for linea in _cabecera_imports(info, mod).rstrip("\n").splitlines():
                if linea and linea not in cabeza:
                    marca_doc = cabeza.index('"""', cabeza.index('"""') + 3) + 4
                    cabeza = cabeza[:marca_doc] + "\n" + linea + cabeza[marca_doc:]
            nombres_all = viejos + info["nombres"]
            texto = cabeza.rstrip("\n") + "\n\n\n" + nuevos
        else:
            nombres_all = info["nombres"]
            texto = (CABECERA.format(titulo=info["titulo"])
                     + _cabecera_imports(info, mod) + nuevos)

        texto += "\n\n__all__ = [\n" + "".join(f"    {n!r},\n" for n in nombres_all) + "]\n"
        destino.write_text(texto)
        dotted = mod.replace("/", ".").removesuffix(".py")
        marca = f"from {dotted} import *  # noqa: F401,F403\n"
        if marca not in marcas:
            marcas.append(marca)
        print(f"{'fusionado' if destino.exists() else 'escrito'} {mod}"
              f" (+{len(info['nombres'])} definiciones)")

    main_py = Path(args.main)
    salida, puesto = [], False
    for i, linea in enumerate(lineas, start=1):
        if i in borrar:
            if not puesto:
                salida.extend(marcas)
                puesto = True
            continue
        salida.append(linea)
    main_py.write_text("".join(salida))
    print(f"\nmain.py: {len(lineas)} -> {len(salida)} lineas")
    print("OJO: mueve los imports al bloque de cabecera (I1a).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
