"""Genera submission.tar.gz en la raiz del proyecto para el PTCG AI Battle.

Adaptado del notebook `notebook/empaquetar.ipynb`: empaqueta el main.py, el
deck.csv y la carpeta cg/ DE ESTE PROYECTO (rutas resueltas desde la ubicacion
de este script, sin depender del directorio de trabajo). Se excluyen los
__pycache__ para no ensuciar el paquete.

Uso:
    python utils/empaquetar_proyecto.py
"""

import os
import tarfile
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent

MAIN_PY = PROJECT_ROOT / "main.py"
DECK_CSV = PROJECT_ROOT / "deck.csv"
CG_DIR = PROJECT_ROOT / "cg"
OUTPUT = PROJECT_ROOT / "submission.tar.gz"


def _filtro_sin_pycache(tarinfo):
    """Excluye __pycache__ y compilados del paquete."""
    nombre = Path(tarinfo.name)
    if "__pycache__" in nombre.parts or nombre.suffix in (".pyc", ".pyo"):
        return None
    return tarinfo


def main():
    for ruta in (MAIN_PY, DECK_CSV):
        if not ruta.exists():
            raise FileNotFoundError(f"Archivo requerido no encontrado: {ruta}")
    if not CG_DIR.is_dir():
        raise FileNotFoundError(f"Carpeta cg no encontrada: {CG_DIR}")

    with tarfile.open(OUTPUT, "w:gz") as tar:
        tar.add(MAIN_PY, arcname="main.py")
        tar.add(DECK_CSV, arcname="deck.csv")
        tar.add(CG_DIR, arcname="cg", filter=_filtro_sin_pycache)

    tam = OUTPUT.stat().st_size
    print("main.py :", MAIN_PY)
    print("deck.csv:", DECK_CSV)
    print("cg      :", CG_DIR)
    print("Creado  :", OUTPUT, f"({tam:,} bytes)")

    with tarfile.open(OUTPUT, "r:gz") as tar:
        print("Contenido:")
        for miembro in tar.getmembers():
            if miembro.isfile():
                print(f"  {miembro.name}  ({miembro.size:,} bytes)")


if __name__ == "__main__":
    main()
