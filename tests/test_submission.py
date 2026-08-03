"""Humo de la submission: que el paquete FUNCIONE en el contenedor de Kaggle.

Este archivo cubre el unico hueco que el resto de la suite NO puede ver. Bajo
pytest, `main` es un modulo importado normalmente y la raiz del proyecto esta en
`sys.path` de forma permanente; en el contenedor no pasa ninguna de las dos
cosas. `kaggle_environments.agent.get_last_callable` COMPILA main.py y lo
ejecuta con `exec` en un dict vacio, con el directorio del agente en `sys.path`
SOLO durante ese exec, y se queda con el ULTIMO callable del namespace.

De ahi los tres modos de fallo que se verifican aqui (docs/main-refactor-arquitectura.md, I1):

  I1a  un paquete propio importado por primera vez en tiempo de DECISION
       -> ModuleNotFoundError en mitad de la partida.
  I1b  cualquier cosa que ligue un callable nuevo DESPUES de `def agent`
       (incluido un re-export de compatibilidad, y ojo: una clase tambien es
       callable) -> el contenedor toma ESA como agente. Silencioso y letal.
  I1c  `main.py` nunca entra en sys.modules -> ningun submodulo puede hacer
       `import main`.

`kaggle_environments` NO se anade a requirements-dev.txt: el agente no depende de
nada externo y esa restriccion del proyecto se mantiene. El cargador se copia
VERBATIM en `tests/kaggle_loader.py`; si Kaggle lo cambiara, ese es el unico
sitio que hay que actualizar.

POR QUE SUBPROCESOS: `cg/sim.py` llama a `lib.GameInitialize()` al importarse, y
hacerlo dos veces en el mismo proceso ABORTA el interprete -- asi que no se puede
descargar `cg` de sys.modules para recargarlo desde la copia empaquetada. Ademas,
si `ptcg` ya estuviese importado por otro test, el fallo I1a no se reproduciria.
Un interprete limpio por caso resuelve las dos cosas.
"""

import json
import os
import subprocess
import sys
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TESTS_DIR = Path(__file__).resolve().parent
for _p in (str(ROOT), str(ROOT / "utils")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import empaquetar_proyecto as ep  # noqa: E402

FIXTURE = TESTS_DIR / "fixtures" / "alakazam_boss_before_ub_step64.json"


# Runner que se ejecuta en un interprete LIMPIO: carga el agente como lo hace el
# contenedor y escribe el resultado en JSON.
#
# Importa `kaggle_loader` y NO este modulo: test_submission.py mete la raiz del
# proyecto en sys.path para alcanzar utils/, y eso haria que un paquete propio
# importado tarde SI se resolviese en el subproceso -- enmascarando justo el
# fallo I1a que este archivo existe para detectar.
_RUNNER = """
import json, os, sys
sys.path.insert(0, {tests_dir!r})
from kaggle_loader import get_last_callable

main_py, cwd_carga, cwd_decision, fixture, salida = sys.argv[1:6]
resultado = {{}}
try:
    os.chdir(cwd_carga)
    with open(main_py) as f:
        fn = get_last_callable(f.read(), path=main_py)
    resultado["nombre"] = getattr(fn, "__name__", repr(fn))
    os.chdir(cwd_decision)          # el contenedor NO hace chdir al dir del agente
    with open(fixture) as f:
        obs = json.load(f)["observation"]
    resultado["decision"] = fn(obs)
    resultado["main_en_sys_modules"] = "main" in sys.modules
except BaseException as e:
    resultado["error"] = "{{}}: {{}}".format(type(e).__name__, e)
# Si el callable secuestro el punto de entrada (I1b), lo que devuelve puede no
# ser serializable: degradar a repr en vez de morir con un JSONDecodeError
# opaco en el test.
try:
    json.dumps(resultado.get("decision"))
except TypeError:
    resultado["decision"] = "<no serializable: {{}}>".format(
        type(resultado["decision"]).__name__)
with open(salida, "w") as f:
    json.dump(resultado, f)
"""


def _cargar_en_subproceso(main_py, cwd_carga, cwd_decision, tmp_path, etiqueta):
    """Carga `main_py` con el cargador de Kaggle en un interprete limpio."""
    script = tmp_path / f"runner_{etiqueta}.py"
    script.write_text(_RUNNER.format(tests_dir=str(TESTS_DIR)))
    salida = tmp_path / f"salida_{etiqueta}.json"

    proc = subprocess.run(
        [sys.executable, str(script), str(main_py), str(cwd_carga),
         str(cwd_decision), str(FIXTURE), str(salida)],
        capture_output=True, text=True, timeout=300,
    )
    assert salida.exists(), (
        f"el runner ({etiqueta}) murio sin escribir resultado.\n"
        f"returncode={proc.returncode}\nstdout={proc.stdout}\nstderr={proc.stderr}"
    )
    return json.loads(salida.read_text())


# ===========================================================================
# I1b -- el punto de entrada
# ===========================================================================
def test_el_cargador_de_kaggle_se_queda_con_agent(tmp_path):
    """El ULTIMO callable de main.py tiene que ser `agent`.

    Si esto falla, algo liga un callable nuevo despues de `def agent` (un
    re-export de compatibilidad al final del archivo es la causa tipica). El
    contenedor tomaria ESA funcion como agente y la partida moriria con un
    TypeError, sin que ningun otro test se entere.
    """
    r = _cargar_en_subproceso(ROOT / "main.py", ROOT, ROOT, tmp_path, "entrada")
    assert "error" not in r, r["error"]
    assert r["nombre"] == "agent", (
        f"el cargador de Kaggle se quedaria con {r['nombre']!r} en vez de con "
        "'agent': mueve los re-exports ARRIBA, antes de `def agent`"
    )


def test_main_no_es_un_modulo_para_el_contenedor(tmp_path):
    """I1c: tras el exec, `main` NO esta en sys.modules.

    Congela la razon por la que ningun submodulo de un paquete propio puede
    hacer `import main` -- y por la que el estado global no puede quedarse en
    main.py cuando se modularice (Ola 3).
    """
    r = _cargar_en_subproceso(ROOT / "main.py", ROOT, ROOT, tmp_path, "modulo")
    assert "error" not in r, r["error"]
    assert r["main_en_sys_modules"] is False


# ===========================================================================
# empaquetado -- lo que main.py importa tiene que viajar
# ===========================================================================
def test_la_submission_incluye_los_paquetes_que_main_importa(tmp_path):
    """Todo paquete local importado por main.py aparece en el tar."""
    destino = tmp_path / "submission.tar.gz"
    incluidos = ep.construir(destino=destino)

    with tarfile.open(destino) as tar:
        raices = {Path(m.name).parts[0] for m in tar.getmembers()}

    assert "main.py" in raices and "deck.csv" in raices
    for ruta in incluidos:
        assert ruta.name in raices, (
            f"{ruta.name} lo importa main.py pero no viaja en la submission"
        )
    # cg/ es el minimo historico; si desaparece, la deteccion se rompio
    assert "cg" in raices


def test_la_submission_no_lleva_pycache(tmp_path):
    destino = tmp_path / "submission.tar.gz"
    ep.construir(destino=destino)
    with tarfile.open(destino) as tar:
        nombres = [m.name for m in tar.getmembers()]
    assert not [n for n in nombres if "__pycache__" in n or n.endswith((".pyc", ".pyo"))]


# ===========================================================================
# I1a / I1c -- end-to-end: empaquetar, descomprimir y DECIDIR
# ===========================================================================
def test_la_submission_empaquetada_decide_igual_que_el_arbol(tmp_path):
    """Empaqueta, descomprime en un dir limpio, carga con el cargador real y
    compara la decision con la del main.py del arbol de trabajo.

    Es la prueba que atrapa I1a (paquete propio no importable en tiempo de
    decision): revienta aqui con ModuleNotFoundError y en ningun otro sitio.
    """
    destino = tmp_path / "submission.tar.gz"
    ep.construir(destino=destino)

    agente_dir = tmp_path / "kaggle_simulations" / "agent"
    agente_dir.mkdir(parents=True)
    with tarfile.open(destino) as tar:
        tar.extractall(agente_dir, filter="data")

    # Referencia: el main.py del arbol.
    ref = _cargar_en_subproceso(ROOT / "main.py", ROOT, ROOT, tmp_path, "ref")
    assert "error" not in ref, ref["error"]

    # Candidato: el de la submission; la DECISION se toma con el CWD fuera del
    # directorio del agente, porque el contenedor no hace chdir.
    cand = _cargar_en_subproceso(
        agente_dir / "main.py", agente_dir, tmp_path, tmp_path, "cand"
    )
    assert "error" not in cand, cand["error"]

    assert cand["nombre"] == "agent"
    assert cand["decision"] == ref["decision"], (
        f"la submission decide {cand['decision']} y el arbol {ref['decision']}"
    )
    assert isinstance(cand["decision"], list) and cand["decision"]
