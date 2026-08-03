"""Corre las reglas de arquitectura del refactor con la suite.

Ver utils/lint_arquitectura.py y docs/main-refactor-arquitectura.md. Las cuatro
reglas cubren fallos que no se manifiestan como un test rojo: rompen la
submission en Kaggle, o hacen que el agente lea estado congelado y decida mal en
partida sin lanzar ninguna excepcion.
"""

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for _p in (str(ROOT), str(ROOT / "utils")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import lint_arquitectura as la  # noqa: E402


def test_sin_infracciones_de_arquitectura():
    fallos = la.revisar()
    detalle = "\n".join(
        f"  {archivo}:{linea}: [{regla}] {mensaje}"
        for regla, archivo, linea, mensaje in fallos
    )
    assert not fallos, f"infracciones de arquitectura:\n{detalle}"


def test_los_mutables_se_derivan_del_codigo():
    """La lista de globals no esta escrita a mano.

    Sale de las sentencias `global` de main.py MAS los campos de `EstadoAgente`.
    A medida que la Ola 3 avanza, el estado se mueve de lo primero a lo segundo,
    asi que lo que se comprueba es que el linter lo sigue ALLA DONDE VIVA -- no
    cuantos quedan en main.py, que legitimamente baja en cada paso.
    """
    mutables = la.nombres_mutables()
    assert len(mutables) >= 30, f"solo {len(mutables)} mutables detectados"
    for esperado in ("plan", "ko_last_turn", "CARTAS_ACTIVAS_EN_MAZO"):
        assert esperado in mutables, f"{esperado} dejo de vigilarse"


def test_el_estado_ya_migrado_sigue_vigilado():
    """Los campos que ya viven en EstadoAgente no pueden salirse de R1."""
    mutables = la.nombres_mutables()
    migrados = [n for n in ("_ub_meowth_pending", "_poke_pad_target_id",
                            "_ld_supp_comprometido") if n in mutables]
    assert len(migrados) == 3, f"solo se vigilan {migrados}"


# ---------------------------------------------------------------------------
# Las reglas tienen que MORDER: un linter que no puede fallar no vale nada.
# ---------------------------------------------------------------------------
def _fallos_de_r3(fuente, tmp_path, monkeypatch):
    archivo = tmp_path / "main.py"
    archivo.write_text(fuente)
    monkeypatch.setattr(la, "MAIN_PY", archivo)
    return la.regla_3_agent_es_lo_ultimo()


def test_r3_acepta_agent_al_final(tmp_path, monkeypatch):
    fuente = "from cg.api import Card\n\ndef agent(obs):\n    return [0]\n"
    assert _fallos_de_r3(fuente, tmp_path, monkeypatch) == []


def test_r3_detecta_un_reexport_despues_de_agent(tmp_path, monkeypatch):
    """El modo de fallo I1b: el contenedor se quedaria con el re-export."""
    fuente = "def agent(obs):\n    return [0]\n\nfrom cg.api import Card\n"
    fallos = _fallos_de_r3(fuente, tmp_path, monkeypatch)
    assert len(fallos) == 1 and fallos[0][0] == "R3"


def test_r3_detecta_una_clase_despues_de_agent(tmp_path, monkeypatch):
    """Una clase tambien es callable, asi que tambien secuestra el entry point."""
    fuente = "def agent(obs):\n    return [0]\n\nclass Ayuda:\n    pass\n"
    fallos = _fallos_de_r3(fuente, tmp_path, monkeypatch)
    assert len(fallos) == 1 and fallos[0][0] == "R3"


def test_r4_detecta_import_perezoso_de_paquete_propio(tmp_path, monkeypatch):
    """El modo de fallo I1a."""
    archivo = tmp_path / "main.py"
    archivo.write_text("def agent(obs):\n    from ptcg.calculo import x\n    return [0]\n")
    monkeypatch.setattr(la, "MAIN_PY", archivo)
    monkeypatch.setattr(la, "PAQUETE", tmp_path / "ptcg")
    fallos = la.regla_4_imports_perezosos()
    assert [f[0] for f in fallos] == ["R4"]


def test_r1_detecta_un_mutable_importado_por_nombre(tmp_path, monkeypatch):
    """El modo de fallo I5: `from x import ko_last_turn` congela el valor."""
    paquete = tmp_path / "ptcg"
    (paquete / "decision").mkdir(parents=True)
    (paquete / "__init__.py").write_text("")
    (paquete / "decision" / "ub.py").write_text(
        "from ptcg.estado import ko_last_turn\n"
    )
    monkeypatch.setattr(la, "PAQUETE", paquete)
    monkeypatch.setattr(la, "nombres_mutables", lambda: {"ko_last_turn"})
    fallos = la.regla_1_mutables_importados()
    assert [f[0] for f in fallos] == ["R1"]


def test_r2_detecta_estado_en_un_modulo_puro(tmp_path, monkeypatch):
    paquete = tmp_path / "ptcg"
    (paquete / "cartas").mkdir(parents=True)
    (paquete / "__init__.py").write_text("")
    (paquete / "cartas" / "ids.py").write_text("from ptcg.estado import ESTADO\n")
    monkeypatch.setattr(la, "PAQUETE", paquete)
    fallos = la.regla_2_pureza()
    assert [f[0] for f in fallos] == ["R2"]


def test_r2_permite_estado_en_calculo(tmp_path, monkeypatch):
    """`calculo/` NO es puro y no debe fingirlo.

    La energia efectiva depende de si Meganium esta en juego y el coste de
    ataque del impuesto de Nighttime Mine: `_can_attack_eff` y `_physical_energy`
    leen ESTADO por naturaleza. Se intento la frontera en `calculo/` y el codigo
    la rechazo; la frontera util es datos (`cartas/`) + reglas (`motor/`).
    """
    paquete = tmp_path / "ptcg"
    (paquete / "calculo").mkdir(parents=True)
    (paquete / "__init__.py").write_text("")
    (paquete / "calculo" / "energia.py").write_text("from ptcg.estado.agente import ESTADO\n")
    monkeypatch.setattr(la, "PAQUETE", paquete)
    assert la.regla_2_pureza() == []
