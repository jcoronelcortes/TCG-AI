"""Generates submission.tar.gz at the project root for the PTCG AI Battle.

Adapted from the notebook `notebook/empaquetar.ipynb`: it packages main.py, the
deck.csv and the LOCAL PACKAGES THAT main.py IMPORTS (today `cg/`; after the refactor
also `ptcg/`). The __pycache__ directories are excluded so as not to dirty the package.

The package list is NOT hand-written: it is derived by reading the module-level
imports of main.py (see `paquetes_locales_de`). That way, when the wave
refactor moves code into a new package, the packaging includes it as soon as
main.py imports it -- without anyone having to remember to touch this file.
Forgetting was the most expensive possible failure: the submission starts broken on Kaggle
with the 930 tests green (see docs/project-history.md, I1).

Usage:
    python utils/package_project.py
"""

import ast
import tarfile
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent

MAIN_PY = PROJECT_ROOT / "main.py"
DECK_CSV = PROJECT_ROOT / "deck.csv"
OUTPUT = PROJECT_ROOT / "submission.tar.gz"


def _raices_importadas(py_path):
    """Top-level names imported by `ruta_py` (module imports only).

    `from cg.api import X` -> "cg";  `import os` -> "os".
    Imports inside functions are ignored: in the Kaggle container they are
    no use for our own packages (the agent's directory leaves sys.path as soon as
    main.py's exec finishes), so a package imported only there
    would be broken anyway.
    """
    arbol = ast.parse(py_path.read_text(encoding="utf-8"), filename=str(py_path))
    raices = []
    for nodo in arbol.body:  # module level only, not ast.walk
        if isinstance(nodo, ast.Import):
            raices += [a.name.split(".")[0] for a in nodo.names]
        elif isinstance(nodo, ast.ImportFrom):
            if nodo.level == 0 and nodo.module:
                raices.append(nodo.module.split(".")[0])
    return raices


def paquetes_locales_de(py_path, raiz=PROJECT_ROOT):
    """PROJECT packages/modules that `ruta_py` imports, in a stable order.

    It returns paths to package directories (`cg/`, `ptcg/`) and to loose
    modules (`something.py`) that live at the root. Anything that does not exist in the project is
    assumed to be the standard library and is not packaged.
    """
    encontrados = {}
    for name in _raices_importadas(py_path):
        if name in encontrados:
            continue
        pkg = raiz / name
        mod = raiz / f"{name}.py"
        if (pkg / "__init__.py").is_file():
            encontrados[name] = pkg
        elif mod.is_file():
            encontrados[name] = mod
    return [encontrados[k] for k in sorted(encontrados)]


def _filtro_sin_pycache(tarinfo):
    """Excludes __pycache__ and compiled files from the package."""
    name = Path(tarinfo.name)
    if "__pycache__" in name.parts or name.suffix in (".pyc", ".pyo"):
        return None
    return tarinfo


def build(destino=OUTPUT, main_py=MAIN_PY, deck_csv=DECK_CSV):
    """Writes the tar.gz to `destino` and returns the list of included paths."""
    for path in (main_py, deck_csv):
        if not path.exists():
            raise FileNotFoundError(f"Archivo requerido no encontrado: {path}")

    paquetes = paquetes_locales_de(main_py)
    if not paquetes:
        raise RuntimeError(
            f"{main_py} no importa ningun paquete local; se esperaba al menos cg/"
        )

    with tarfile.open(destino, "w:gz") as tar:
        tar.add(main_py, arcname="main.py")
        tar.add(deck_csv, arcname="deck.csv")
        for path in paquetes:
            tar.add(path, arcname=path.name, filter=_filtro_sin_pycache)

    return [main_py, deck_csv] + paquetes


def main():
    incluidos = build()
    for path in incluidos:
        print(f"{path.name:9s}:", path)

    tam = OUTPUT.stat().st_size
    print("Creado  :", OUTPUT, f"({tam:,} bytes)")

    with tarfile.open(OUTPUT, "r:gz") as tar:
        print("Contenido:")
        for miembro in tar.getmembers():
            if miembro.isfile():
                print(f"  {miembro.name}  ({miembro.size:,} bytes)")


if __name__ == "__main__":
    main()
