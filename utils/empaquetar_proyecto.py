"""Genera submission.tar.gz en la raiz del proyecto para el PTCG AI Battle.

Adaptado del notebook `notebook/empaquetar.ipynb`: empaqueta el main.py, el
deck.csv y los PAQUETES LOCALES QUE main.py IMPORTA (hoy `cg/`; tras el refactor
tambien `ptcg/`). Se excluyen los __pycache__ para no ensuciar el paquete.

La lista de paquetes NO esta escrita a mano: se deriva leyendo los imports de
nivel de modulo de main.py (ver `paquetes_locales_de`). Asi, cuando el refactor
por olas saque codigo a un paquete nuevo, el empaquetado lo incluye solo con que
main.py lo importe -- sin que nadie tenga que acordarse de tocar este archivo.
Olvidarse era el fallo mas caro posible: la submission arranca rota en Kaggle
con los 930 tests en verde (ver docs/main-refactor-arquitectura.md, I1).

Uso:
    python utils/empaquetar_proyecto.py
"""

import ast
import tarfile
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent

MAIN_PY = PROJECT_ROOT / "main.py"
DECK_CSV = PROJECT_ROOT / "deck.csv"
OUTPUT = PROJECT_ROOT / "submission.tar.gz"


def _raices_importadas(ruta_py):
    """Nombres de nivel superior importados por `ruta_py` (solo imports de modulo).

    `from cg.api import X` -> "cg";  `import os` -> "os".
    Se ignoran los imports dentro de funciones: en el contenedor de Kaggle no
    sirven para paquetes propios (el dir del agente sale de sys.path en cuanto
    termina el exec de main.py), asi que un paquete que solo se importase ahi
    estaria roto de todas formas.
    """
    arbol = ast.parse(ruta_py.read_text(encoding="utf-8"), filename=str(ruta_py))
    raices = []
    for nodo in arbol.body:  # solo nivel de modulo, no ast.walk
        if isinstance(nodo, ast.Import):
            raices += [a.name.split(".")[0] for a in nodo.names]
        elif isinstance(nodo, ast.ImportFrom):
            if nodo.level == 0 and nodo.module:
                raices.append(nodo.module.split(".")[0])
    return raices


def paquetes_locales_de(ruta_py, raiz=PROJECT_ROOT):
    """Paquetes/modulos del PROYECTO que importa `ruta_py`, en orden estable.

    Devuelve rutas a directorios-paquete (`cg/`, `ptcg/`) y a modulos sueltos
    (`algo.py`) que vivan en la raiz. Lo que no exista en el proyecto se asume
    biblioteca estandar y no se empaqueta.
    """
    encontrados = {}
    for nombre in _raices_importadas(ruta_py):
        if nombre in encontrados:
            continue
        pkg = raiz / nombre
        mod = raiz / f"{nombre}.py"
        if (pkg / "__init__.py").is_file():
            encontrados[nombre] = pkg
        elif mod.is_file():
            encontrados[nombre] = mod
    return [encontrados[k] for k in sorted(encontrados)]


def _filtro_sin_pycache(tarinfo):
    """Excluye __pycache__ y compilados del paquete."""
    nombre = Path(tarinfo.name)
    if "__pycache__" in nombre.parts or nombre.suffix in (".pyc", ".pyo"):
        return None
    return tarinfo


def construir(destino=OUTPUT, main_py=MAIN_PY, deck_csv=DECK_CSV):
    """Escribe el tar.gz en `destino` y devuelve la lista de rutas incluidas."""
    for ruta in (main_py, deck_csv):
        if not ruta.exists():
            raise FileNotFoundError(f"Archivo requerido no encontrado: {ruta}")

    paquetes = paquetes_locales_de(main_py)
    if not paquetes:
        raise RuntimeError(
            f"{main_py} no importa ningun paquete local; se esperaba al menos cg/"
        )

    with tarfile.open(destino, "w:gz") as tar:
        tar.add(main_py, arcname="main.py")
        tar.add(deck_csv, arcname="deck.csv")
        for ruta in paquetes:
            tar.add(ruta, arcname=ruta.name, filter=_filtro_sin_pycache)

    return [main_py, deck_csv] + paquetes


def main():
    incluidos = construir()
    for ruta in incluidos:
        print(f"{ruta.name:9s}:", ruta)

    tam = OUTPUT.stat().st_size
    print("Creado  :", OUTPUT, f"({tam:,} bytes)")

    with tarfile.open(OUTPUT, "r:gz") as tar:
        print("Contenido:")
        for miembro in tar.getmembers():
            if miembro.isfile():
                print(f"  {miembro.name}  ({miembro.size:,} bytes)")


if __name__ == "__main__":
    main()
