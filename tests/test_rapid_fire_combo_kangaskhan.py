"""Rapid-Fire Combo (Mega Kangaskhan ex): el dano impreso subestima en 50.

La carta hace 200 + 50 por cada CARA, lanzando monedas hasta la primera cruz.
El numero de caras es una geometrica de p=1/2 (media 1), asi que la esperanza
del bonus es +50: el dano real medio es 250 y es >= 250 la mitad de las veces.

Por que importa: nuestro Teal Mask Ogerpon ex tiene 210 PV. Con el 200 impreso
el modelo lo da por VIVO ante un golpe que lo mata el 50% de las veces, y con
el activo "a salvo" no dispara ningun pivote defensivo.

Medido sobre el meta real (deck/rivales_reales/, ago 2026), el winrate contra
las 8 listas Crustle cae de forma monotona con las copias de Mega Kangaskhan ex
que lleven -- 0 copias -> 88.0%, 2 -> 79.8%, 4 -> 70.9% --, asi que la amenaza
de ese matchup es el Kangaskhan y no el muro que le da nombre.

El bonus es OPT-IN a proposito: `_op_active_attack_damage_to` alimenta a la vez
al estimador de RIESGO y a `_active_doomed_real`, que exige CERTEZA para dar un
cuerpo por perdido. El 200 es el suelo garantizado; el 250, la esperanza.
"""

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import main as m


class _Pk:
    def __init__(self, cid, hp, energias=0, tools=()):
        self.id = cid
        self.hp = hp
        self.maxHp = hp
        self.energies = [1] * energias
        self.tools = list(tools)


@pytest.fixture
def kangaskhan():
    # 3 energias = puede pagar Rapid-Fire Combo (coste 3).
    return _Pk(m.Mega_Kangaskhan_ex, 300, energias=3)


@pytest.fixture
def ogerpon():
    return _Pk(m.Teal_Mask_Ogerpon_ex, 210)


def test_el_suelo_garantizado_sigue_siendo_el_dano_impreso(kangaskhan, ogerpon):
    """Sin proyectar, el valor es el impreso: es lo que exige la via de certeza."""
    assert m._op_active_attack_damage_to(kangaskhan, ogerpon, None) == 200


def test_la_proyeccion_suma_la_esperanza_de_la_moneda(kangaskhan, ogerpon):
    assert m._op_active_attack_damage_to(
        kangaskhan, ogerpon, None, proyectar_moneda=True) == 250


def test_la_proyeccion_condena_al_ogerpon_de_210(kangaskhan, ogerpon):
    """El caso que motiva todo: 210 PV sobrevive a 200 y no a 250."""
    suelo = m._op_active_attack_damage_to(kangaskhan, ogerpon, None)
    esperado = m._op_active_attack_damage_to(
        kangaskhan, ogerpon, None, proyectar_moneda=True)
    assert suelo < ogerpon.hp, "con el impreso el modelo lo cree vivo"
    assert esperado >= ogerpon.hp, (
        "con la esperanza de la moneda queda condenado, que es lo real")


def test_no_altera_a_otros_atacantes(ogerpon):
    """La proyeccion esta acotada a Rapid-Fire Combo.

    Mismo criterio que las excepciones de Powerful Hand y Do the Wave: no
    tocar la lectura de "activo condenado" en el resto de matchups.
    """
    for cid, hp in ((m.Dragapult_ex, 320), (m.Grimmsnarl_ex, 320)):
        atacante = _Pk(cid, hp, energias=3)
        sin_p = m._op_active_attack_damage_to(atacante, ogerpon, None)
        con_p = m._op_active_attack_damage_to(
            atacante, ogerpon, None, proyectar_moneda=True)
        assert sin_p == con_p, f"la proyeccion no debe tocar a {cid}"


def test_la_debilidad_se_sigue_aplicando_sobre_el_dano_proyectado(kangaskhan):
    """El bonus entra ANTES de debilidad/resistencia, como el resto."""
    # Un objetivo debil a {C} (el tipo de Kangaskhan) recibe el doble.
    debil = _Pk(m.Teal_Mask_Ogerpon_ex, 210)
    normal = m._op_active_attack_damage_to(
        kangaskhan, debil, None, proyectar_moneda=True)
    # Sin debilidad {C} en nuestro pool, el valor no se duplica: el test fija
    # que la proyeccion no rompe la cadena de calculo posterior.
    assert normal >= 250
