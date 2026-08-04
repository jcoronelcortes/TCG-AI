"""Runs the refactor's architecture rules with the suite.

See utils/lint_arquitectura.py and docs/project-history.md. The four
rules cover failures that do not show up as a red test: they break the
submission on Kaggle, or they make the agent read frozen state and decide badly in a
game without raising any exception.
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
    """The list of globals is not hand-written.

    It comes from main.py's `global` statements PLUS the fields of `EstadoAgente`.
    As wave 3 advances, the state moves from the former to the latter,
    so what is checked is that the linter follows it WHEREVER IT LIVES -- not
    how many are left in main.py, which legitimately goes down at every step.
    """
    mutables = la.nombres_mutables()
    assert len(mutables) >= 30, f"solo {len(mutables)} mutables detectados"
    for esperado in ("plan", "ko_last_turn", "ACTIVE_CARDS_IN_DECK"):
        assert esperado in mutables, f"{esperado} dejo de vigilarse"


def test_el_estado_ya_migrado_sigue_vigilado():
    """The fields that already live in EstadoAgente cannot escape R1."""
    mutables = la.nombres_mutables()
    migrados = [n for n in ("_ub_meowth_pending", "_poke_pad_target_id",
                            "_ld_supp_comprometido") if n in mutables]
    assert len(migrados) == 3, f"solo se vigilan {migrados}"


# ---------------------------------------------------------------------------
# The rules have to BITE: a linter that cannot fail is worth nothing.
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
    """Failure mode I1b: the container would keep the re-export."""
    fuente = "def agent(obs):\n    return [0]\n\nfrom cg.api import Card\n"
    fallos = _fallos_de_r3(fuente, tmp_path, monkeypatch)
    assert len(fallos) == 1 and fallos[0][0] == "R3"


def test_r3_detecta_una_clase_despues_de_agent(tmp_path, monkeypatch):
    """A class is callable too, so it also hijacks the entry point."""
    fuente = "def agent(obs):\n    return [0]\n\nclass Ayuda:\n    pass\n"
    fallos = _fallos_de_r3(fuente, tmp_path, monkeypatch)
    assert len(fallos) == 1 and fallos[0][0] == "R3"


def test_r4_detecta_import_perezoso_de_paquete_propio(tmp_path, monkeypatch):
    """Failure mode I1a."""
    archivo = tmp_path / "main.py"
    archivo.write_text("def agent(obs):\n    from ptcg.calculo import x\n    return [0]\n")
    monkeypatch.setattr(la, "MAIN_PY", archivo)
    monkeypatch.setattr(la, "PAQUETE", tmp_path / "ptcg")
    fallos = la.regla_4_imports_perezosos()
    assert [f[0] for f in fallos] == ["R4"]


def test_r1_detecta_un_mutable_importado_por_nombre(tmp_path, monkeypatch):
    """Failure mode I5: `from x import ko_last_turn` freezes the value."""
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
    """`calculo/` is NOT pure and must not pretend to be.

    The effective energy depends on whether Meganium is in play and the attack
    cost on the Nighttime Mine tax: `_can_attack_eff` and `_physical_energy`
    read ESTADO by nature. The boundary at `calculo/` was attempted and the code
    rejected it; the useful boundary is data (`cartas/`) + rules (`motor/`).
    """
    paquete = tmp_path / "ptcg"
    (paquete / "calculo").mkdir(parents=True)
    (paquete / "__init__.py").write_text("")
    (paquete / "calculo" / "energia.py").write_text("from ptcg.estado.agente import ESTADO\n")
    monkeypatch.setattr(la, "PAQUETE", paquete)
    assert la.regla_2_pureza() == []
