"""A table of ids rots silently, and three of them had nobody diffing them.

`utils/op_scaling_census.py` audits the attacks whose printed number is a
placeholder. `utils/op_buff_census.py` audits the flat bonus that is not on the
attacker at all. Nothing audited the tables that say **our damage is cancelled**,
and one of them was wrong:

    EX_IMMUNE_IDS carried Crustle 533, whose ability is STURDY

The two Crustle share a name and nothing else. 345 prints "Mysterious Rock Inn"
-- prevent all damage from your opponent's Pokémon {ex} -- and 533 prints
"Sturdy", at full HP it survives a lethal hit at 10. Listed as ex-immune, 533
made every attack from our ex read as ZERO against a 150 HP body that falls in
one hit, and we would have walked around a wall that is not there.

**It cost nothing**: 0 of the 87 real lists play it. That is the point of running
a census instead of arguing about it -- the honest report was the exposure, and
the entry is removed because the meta rotates, not because it was bleeding.

The census also asks the expensive half of the question, which is the one no
table can answer on its own: text that DOES claim an immunity and sits in no
table. It found `Acerola's Mischief` in four decks, and that one is an argued
EXCLUSION rather than a defect -- it is a Trainer that lives in their hand until
played, lasts one turn, and lets THEM choose which body it protects. Modelling it
means assuming a card we cannot see and a target we cannot know, the same reading
the buff census already applies to Premium Power Pro and Black Belt's Training.

This file is the ratchet: it fails the day a table and a card stop agreeing.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for p in (ROOT, ROOT / "utils"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import op_immunity_census as censo
from ptcg.cards.ids import (ABILITY_IMMUNE_IDS, EX_IMMUNE_IDS,
                            FULL_HP_SURVIVE_IDS)

CRUSTLE_MYSTERIOUS_ROCK, CRUSTLE_STURDY = 345, 533


def _por_bucket():
    filas, _ = censo.census()
    salida = {}
    for bucket, _n, _name, cid, tabla, _skill, _text in filas:
        salida.setdefault(bucket, []).append((cid, tabla))
    return salida


def test_ninguna_tabla_contradice_el_texto_de_su_carta():
    """The ratchet. Every id in the three tables prints what the table claims."""
    malas = _por_bucket().get("TABLA EQUIVOCADA") or []
    assert not malas, (
        "una tabla dice algo que la carta no dice: " + str(malas))


def test_ningun_id_de_las_tablas_falta_del_catalogo():
    huerfanos = _por_bucket().get("SIN CARTA") or []
    assert not huerfanos, f"ids que ya no existen: {huerfanos}"


def test_no_queda_ninguna_inmunidad_sin_modelar_ni_argumentada():
    """The other half, and the one that costs a game: a wall we do not know
    about is a wall we walk into. An exclusion is allowed, in writing, in
    `_EXCLUDED`."""
    faltan = _por_bucket().get("SIN MODELAR") or []
    assert not faltan, (
        f"texto que reclama inmunidad y no esta en ninguna tabla: {faltan}")


def test_cada_exclusion_lleva_su_motivo_escrito():
    assert censo._EXCLUDED, "sin exclusiones no hace falta el diccionario"
    for card_id, motivo in censo._EXCLUDED.items():
        assert isinstance(motivo, str) and len(motivo) > 30, (
            f"la exclusion de {card_id} no esta argumentada")


# ---------------------------------------------------------------------------
# The specific defect, pinned so it cannot come back by hand
# ---------------------------------------------------------------------------

def test_la_crustle_de_STURDY_no_es_inmune_a_nuestros_ex():
    assert CRUSTLE_STURDY not in EX_IMMUNE_IDS, (
        "533 imprime Sturdy, no Mysterious Rock Inn: en esta tabla convierte un "
        "cuerpo de 150 PV en un muro inventado")
    assert CRUSTLE_STURDY in FULL_HP_SURVIVE_IDS, (
        "y sigue sobreviviendo a HP lleno, que es lo que SI dice su texto")


def test_la_otra_crustle_si_lo_es():
    """The control: removing the wrong one must not remove the real wall. 345 is
    in 51 opposing decks and it is the ex-immune wall this whole project is
    built around."""
    assert CRUSTLE_MYSTERIOUS_ROCK in EX_IMMUNE_IDS
    assert CRUSTLE_MYSTERIOUS_ROCK not in FULL_HP_SURVIVE_IDS


def test_las_tres_tablas_siguen_teniendo_a_quien_vigilar():
    """A census that passes because its tables are empty proves nothing."""
    assert EX_IMMUNE_IDS and ABILITY_IMMUNE_IDS and FULL_HP_SURVIVE_IDS
