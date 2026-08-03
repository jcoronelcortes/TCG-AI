"""Extrae de main.py los bindings PUROS de un rango de lineas a un modulo del paquete.

Es el mecanismo de las olas 1-2 del refactor (docs/main-refactor-arquitectura.md).
Mueve RANGOS DE LINEAS contiguos, no sentencias sueltas, para que los comentarios
viajen con lo que documentan: en main.py los comentarios son documentacion de
verdad (el porque de cada constante, con referencias a partidas concretas), y
perderlos seria el peor resultado posible de un refactor que existe para hacer el
codigo mas legible.

QUE CUENTA COMO PURO
  Un binding `NOMBRE = <expr>` cuya expresion solo usa literales y otros nombres
  ya clasificados como puros. Se excluyen:
    * lo que depende de runtime (`card_table`, `all_card_data()`, deck.csv...);
    * cualquier acceso a atributo o llamada que no sea a un builtin seguro;
    * y -- la trampa que de verdad importa -- los nombres MUTADOS en algun sitio.

LA TRAMPA DE LOS MUTADOS
  `my_deck = []` parece una constante perfecta: el valor es un literal. Pero tres
  lineas mas abajo se llena leyendo deck.csv, y `agent()` lo devuelve entero en el
  mulligan. Moverlo habria dejado el mazo del agente en otro modulo con
  main.py mutando el mismo objeto por accidente. Por eso se detecta todo nombre
  que reciba `.append/.update/.add/...`, un subscript-store, un `global` o un
  `augassign`, y se deja donde esta.

Uso:
    python utils/extraer_puros.py --desde 40 --hasta 1008 --destino ptcg/cartas/ids.py
    python utils/extraer_puros.py ... --aplicar     # sin esto, solo informa
"""

import argparse
import ast
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Builtins cuya llamada no introduce dependencias de runtime.
SEGUROS = {"frozenset", "set", "dict", "tuple", "list", "range", "len",
           "sorted", "int", "str"}

# Metodos que revelan que un nombre NO es constante.
MUTADORES = {"append", "extend", "update", "add", "pop", "clear", "insert",
             "remove", "discard", "setdefault", "sort"}

CABECERA = '''"""{titulo}

Extraido VERBATIM de main.py por utils/extraer_puros.py
(docs/main-refactor-arquitectura.md). Aqui NO hay logica: solo constantes que
dependen unicamente de literales. Este modulo no puede importar estado ni tocar
el simulador -- lo vigila utils/lint_arquitectura.py (R2).

main.py lo reexporta con `import *`, asi que el `__all__` del final tiene que
listar TODOS los nombres, incluidos los que empiezan por `_` (que `import *`
omitiria si no).
"""

'''


def nombres_mutados(arbol):
    """Nombres que en algun punto del modulo se mutan: no son constantes."""
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
    """Devuelve (rangos, nombres): que lineas moverian y que bindings contienen."""
    src = main_py.read_text(encoding="utf-8")
    lineas = src.splitlines(keepends=True)
    arbol = ast.parse(src)
    mutados = nombres_mutados(arbol)

    # Lo YA extraido al paquete cuenta como disponible: tras la primera ola,
    # `EVO_LINES = (Chikorita, Bayleef, ...)` referencia IDs que ya no estan en
    # main.py, y sin esto pareceria impura y no se moveria nunca.
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
            nombre = nodo.targets[0].id
            if _es_puro(nodo.value, puros) and nombre not in mutados:
                puros[nombre] = True
                ok = True
                if desde <= a <= hasta:
                    movibles[a] = (b, nombre)
        if not ok or not (desde <= a <= hasta):
            bloqueadas.update(range(a, b + 1))

    es_movible = [False] * (len(lineas) + 2)
    for a, (b, _) in movibles.items():
        for ln in range(a, b + 1):
            es_movible[ln] = True

    def suelta(ln):
        t = lineas[ln - 1].strip()
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
        while fin > ini and suelta(fin):      # los comentarios finales son del
            fin -= 1                          # nodo que viene DESPUES
        if not rangos or ini > rangos[-1][1]:
            rangos.append([ini, fin])
        else:
            rangos[-1][1] = max(rangos[-1][1], fin)
        ln = fin + 1

    nombres = [n for a, (b, n) in sorted(movibles.items())]

    # Nombres que el codigo movido toma de modulos YA extraidos: hay que
    # importarlos en el destino o el modulo nuevo revienta al cargarse.
    from pureza import _mapa_paquete
    mapa = _mapa_paquete()
    propios = set(nombres)
    necesarios = {}
    for a, b in rangos:
        fragmento = "".join(lineas[a - 1:b])
        try:
            sub = ast.parse(fragmento)
        except SyntaxError:
            continue
        for n in ast.walk(sub):
            if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load):
                if n.id in mapa and n.id not in propios:
                    necesarios.setdefault(mapa[n.id], set()).add(n.id)
    return lineas, rangos, nombres, necesarios


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
    lineas, rangos, nombres, necesarios = planificar(main_py, args.desde, args.hasta)

    total = sum(b - a + 1 for a, b in rangos)
    print(f"rangos: {len(rangos)}   lineas: {total}   bindings: {len(nombres)}")
    for a, b in rangos:
        print(f"  {a:6d}-{b:<6d} ({b - a + 1:4d} l)  {lineas[a - 1].strip()[:56]}")

    if not args.aplicar:
        print("\n(dry run; usa --aplicar para escribir)")
        return 0

    destino = PROJECT_ROOT / args.destino
    destino.parent.mkdir(parents=True, exist_ok=True)
    for paquete in (destino.parent, destino.parent.parent):
        ini = paquete / "__init__.py"
        if paquete != PROJECT_ROOT and not ini.exists():
            ini.write_text('"""Paquete del agente. Ver docs/main-refactor-arquitectura.md."""\n')

    cuerpo = ["".join(lineas[a - 1:b]) for a, b in rangos]
    imports = "".join(
        f"from {mod} import {', '.join(sorted(ns))}\n"
        for mod, ns in sorted(necesarios.items()))
    if imports:
        imports += "\n\n"
    all_lista = "__all__ = [\n" + "".join(f"    {n!r},\n" for n in nombres) + "]\n"
    destino.write_text(CABECERA.format(titulo=args.titulo) + imports
                       + "\n".join(cuerpo) + "\n\n" + all_lista)

    borrar = set()
    for a, b in rangos:
        borrar.update(range(a, b + 1))
    modulo = args.destino.replace("/", ".").removesuffix(".py")
    marca = f"from {modulo} import *  # noqa: F401,F403\n"
    salida, puesto = [], False
    for i, linea in enumerate(lineas, start=1):
        if i in borrar:
            if not puesto:
                salida.append(marca)
                puesto = True
            continue
        salida.append(linea)
    main_py.write_text("".join(salida))

    print(f"\nescrito {destino}")
    print(f"{args.main}: {len(lineas)} -> {len(salida)} lineas")
    print("OJO: el import se inserta donde estaba el primer rango; muevelo al "
          "bloque de cabecera (en Kaggle el dir del agente solo esta en sys.path "
          "mientras se ejecuta main.py).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
