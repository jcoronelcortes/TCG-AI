"""Migra estado de modulo de main.py a `ESTADO.<campo>` (Ola 3 del refactor).

POR QUE ES DISTINTO DE LAS OLAS ANTERIORES
  Las olas 1, 2 y 4 MUEVEN lineas sin tocarlas. Esta las REESCRIBE: `ko_last_turn`
  pasa a `ESTADO.ko_last_turn` en cada sitio. Por eso el gate de equivalencia
  (utils/sombra.py) deja de ser una red y pasa a ser el instrumento principal.

POR QUE NO `ast.unparse`
  Reescribir el arbol y volver a imprimirlo destruiria TODOS los comentarios, que
  en main.py son documentacion de verdad (el porque de cada regla, con
  referencias a partidas concretas). Aqui el AST solo se usa para LOCALIZAR
  (lineno, col_offset) y el texto se edita en sitio, de derecha a izquierda para
  que los desplazamientos no se invaliden. Todo lo demas queda byte a byte igual.

ANALISIS DE AMBITO
  Un `Name` solo se reescribe si de verdad se refiere al global. Dentro de una
  funcion que declara `global X` -> si. Dentro de una que asigna `X` sin
  declararlo global, `X` es LOCAL y no se toca. Los argumentos y las
  comprensiones tambien cuentan como locales. Sin esto, un `plan = ...` local
  en cualquier helper acabaria escribiendo en el estado compartido.

Uso:
    python utils/migrar_estado.py --campos plan,pre_turn          # dry run
    python utils/migrar_estado.py --campos plan,pre_turn --aplicar
    python utils/migrar_estado.py --listar                        # que queda
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
    """Recolecta los Name que SI se refieren a los globales indicados."""

    def __init__(self, campos):
        self.campos = campos
        self.hits = []          # (lineno, col_offset, nombre)
        self.globales_decl = []  # (lineno, col_offset, end_col, nombres)

    # --- nivel de modulo -----------------------------------------------------
    def visit_Module(self, nodo):
        for hijo in nodo.body:
            self._visitar(hijo, locales=set(), globales=set(self.campos))

    def _locales_de(self, fn):
        """Nombres locales de `fn`: argumentos y asignaciones no declaradas global."""
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
            # no mirar dentro de funciones anidadas: tienen su propio ambito
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
            # visibles como global: lo declarado `global` + lo que no es local
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
            # `ESTADO.plan` ya migrado: no volver a tocar el `plan`
            if isinstance(nodo.value, ast.Name) and nodo.value.id == OBJETO:
                return
        if isinstance(nodo, ast.Name) and nodo.id in self.campos and nodo.id in globales:
            self.hits.append((nodo.lineno, nodo.col_offset, nodo.id))
        for n in ast.iter_child_nodes(nodo):
            self._visitar(n, locales, globales)


def migrar(texto, campos):
    """Devuelve (texto_nuevo, n_reescrituras, n_globals_eliminados)."""
    campos = set(campos)
    arbol = ast.parse(texto)
    v = _Ambito(campos)
    v.visit(arbol)

    lineas = texto.splitlines(keepends=True)

    # 1) reescribir los Name, por linea y de derecha a izquierda
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

    # 2) quitar (o podar) las sentencias `global`
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
    ast.parse(nuevo)          # no escribir algo que no parsea
    main_py.write_text(nuevo)
    print(f"\nescrito {main_py}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
