"""Analisis de pureza a nivel de DEFINICION: que se puede sacar de main.py.

Es la precondicion de las olas 2 y 4 del refactor
(docs/main-refactor-arquitectura.md): antes de mover una funcion hay que
DEMOSTRAR que no toca el estado mutable ni las tablas de runtime, no suponerlo.

Una definicion de nivel de modulo es MOVIBLE si todo lo que referencia y no
define ella misma es:
  * un builtin, o un nombre importado (stdlib / cg.api),
  * una constante ya extraida al paquete (`ptcg.cartas.ids`),
  * una constante pura que sigue en main.py (no bloquea: se puede mover despues),
  * u otra definicion movible.

Es un punto fijo: se parte de "todas son movibles" y van cayendo las que tocan
algo impuro, hasta que no cae ninguna mas. Lo que las bloquea es siempre una de
tres cosas, y saber cual dice a que ola pertenecen:

  * un global mutable (`ko_last_turn`, `plan`, ...)  -> espera a la Ola 3;
  * una tabla de runtime (`card_table`, `attack_table`) -> necesita que esas
    tablas se muevan antes;
  * otra definicion bloqueada -> se arrastra con ella.

Uso:
    python utils/pureza.py                 # resumen
    python utils/pureza.py --detalle       # ademas, por que esta bloqueada cada una
"""

import argparse
import ast
import builtins
import sys
from collections import Counter
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

BUILTINS = set(dir(builtins))

# Nombres de nivel de modulo que dependen de la carga (deck.csv, cg.api) y por
# tanto no son constantes puras.
RUNTIME = {"all_card", "card_table", "attack_table", "my_deck",
           "file_path", "csv", "file"}

# Metodos que delatan que un nombre se MUTA (y por tanto no es constante).
MUTADORES = {"append", "extend", "update", "add", "pop", "clear", "insert",
             "remove", "discard", "setdefault", "sort"}


def nombres_mutados(arbol):
    """Nombres mutados en algun punto del modulo: son estado, no constantes.

    OJO: esto NO se solapa con las sentencias `global`. Reasignar un escalar
    exige `global`; mutar un dict o una lista NO. `ATTACK_ENERGY_REQ` es el caso
    real: `_aplicar_impuesto_tera` le reescribe entradas en CADA llamada a
    agent() (el impuesto de Nighttime Mine) y 56 sitios lo leen, pero no aparece
    en ninguna sentencia `global`. Sin esta comprobacion pasaria por constante
    pura y se movria a un modulo de datos, escondiendo estado de turno dentro de
    lo que parece una tabla fija.
    """
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
    return mutados


def _args_de(nodo):
    a = nodo.args
    nombres = {x.arg for x in a.args + a.kwonlyargs + a.posonlyargs}
    if a.vararg:
        nombres.add(a.vararg.arg)
    if a.kwarg:
        nombres.add(a.kwarg.arg)
    return nombres


def nombres_libres(nodo):
    """Nombres que la definicion usa y no define ella misma.

    Recoge los argumentos de TODAS las funciones/lambdas anidadas, no solo los
    del nodo raiz: si no, el `self` de los metodos de una dataclass aparece como
    nombre libre y bloquea la clase entera (paso de verdad).
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
    """`__all__` de los modulos ya extraidos al paquete."""
    nombres = set()
    paquete = PROJECT_ROOT / "ptcg"
    if not paquete.is_dir():
        return nombres
    if str(PROJECT_ROOT) not in sys.path:
        sys.path.insert(0, str(PROJECT_ROOT))
    for ruta in paquete.rglob("*.py"):
        try:
            arbol = ast.parse(ruta.read_text(encoding="utf-8"))
        except SyntaxError:
            continue
        for nodo in arbol.body:
            if (isinstance(nodo, ast.Assign) and len(nodo.targets) == 1
                    and isinstance(nodo.targets[0], ast.Name)
                    and nodo.targets[0].id == "__all__"):
                try:
                    nombres.update(ast.literal_eval(nodo.value))
                except ValueError:
                    pass
            elif isinstance(nodo, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                nombres.add(nodo.name)
    return nombres


def _mapa_paquete():
    """nombre exportado -> modulo del paquete que lo define (`ptcg.cartas.ids`...)."""
    mapa = {}
    paquete = PROJECT_ROOT / "ptcg"
    if not paquete.is_dir():
        return mapa
    for ruta in sorted(paquete.rglob("*.py")):
        if ruta.name == "__init__.py":
            continue
        dotted = ruta.relative_to(PROJECT_ROOT).with_suffix("")
        dotted = ".".join(dotted.parts)
        try:
            arbol = ast.parse(ruta.read_text(encoding="utf-8"))
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
    # Estado mutable que NO se declara `global`: dicts/listas de nivel de modulo
    # que alguien reescribe (ver `nombres_mutados`).
    mutables |= nombres_mutados(arbol)

    definiciones, asignaciones = {}, {}
    for n in arbol.body:
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            definiciones[n.name] = n
        elif (isinstance(n, ast.Assign) and len(n.targets) == 1
              and isinstance(n.targets[0], ast.Name)):
            asignaciones[n.targets[0].id] = n

    const_main = set(asignaciones) - RUNTIME - mutables
    libres = {k: nombres_libres(v) for k, v in definiciones.items()}

    movibles, razon = set(definiciones), {}
    cambio = True
    while cambio:
        cambio = False
        for nombre in sorted(movibles):
            for libre in libres[nombre]:
                if (libre in BUILTINS or libre in importados or libre in del_paquete
                        or libre in movibles or libre == nombre or libre in const_main):
                    continue
                if libre in mutables:
                    motivo = f"estado mutable `{libre}`"
                elif libre in RUNTIME:
                    motivo = f"runtime `{libre}`"
                elif libre in definiciones:
                    motivo = f"definicion bloqueada `{libre}`"
                else:
                    motivo = f"desconocido `{libre}`"
                movibles.discard(nombre)
                razon[nombre] = motivo
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
    lineas = sum(defs[n].end_lineno - defs[n].lineno + 1 for n in mov)

    print(f"definiciones de nivel de modulo : {len(defs)}")
    print(f"MOVIBLES (puras)                : {len(mov)}  ({lineas} lineas)")
    print(f"bloqueadas                      : {len(defs) - len(mov)}")
    print()
    print("bloqueadas, por causa raiz:")
    for causa, n in Counter(r.split("`")[1] for r in a["razon"].values()).most_common(12):
        print(f"  {n:4d}  {causa}")

    if args.detalle:
        print("\n=== MOVIBLES ===")
        for n in sorted(mov, key=lambda x: defs[x].lineno):
            print(f"  {defs[n].lineno:6d}  {n}")
        print("\n=== BLOQUEADAS ===")
        for n in sorted(a["razon"], key=lambda x: defs[x].lineno):
            print(f"  {defs[n].lineno:6d}  {n:45s} {a['razon'][n]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
