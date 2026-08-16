"""El asiento del frente vs Alakazam: primero si se vende, y luego a quien.

Origen (user, `records/registro_008_pasos_112_hasta_119.json`, **episode
93519870 paso 113**, vs Alakazam -- GANADA, con el cuerpo equivocado delante):

    NOSOTROS (4 premios)                   RIVAL (3 premios)
    activo  **Hydrapple ex 330/330, 4 {G}**   activo  Kadabra 80/80, 0 {G}
    banca   Meowth ex 170, Meowth ex 170      mano    DOS cartas
            Meganium 160, 0 {G}
            **Teal Mask Ogerpon ex 210, 6 {G}**
            **Dipplin 80, 2 {G}**  <- 1 premio

        [0] jugar  [1] jugar  [2] ATACAR (Syrup Storm)  [3] RETIRAR  [4] FIN

El Hydrapple ex estaba entero, con su ataque ofrecido y ya noqueando al Kadabra.
El motor retiro: pago dos Grass -- el Hydrapple bajo a la banca a CERO energias
-- cedio el ataque del turno y dejo delante al Ogerpon ex de 210, que sigue
costando DOS premios y tiene 120 de vida menos.

SON DOS DEFECTOS, uno por menu, y este fichero prueba los dos con su control.

PRIMERO: ¿SE VENDE EL ASIENTO? `_alakazam_pivot_1prize` (6000, contra los 1100
del ataque) es una frase de contabilidad de premios -- "retiro el ex y subo un
cuerpo de UN premio; si nos lo noquean entregamos 1 en vez de 2" -- y presupone
el noqueo. Con su mano en DOS, su Powerful Hand proyectado son 20 x (2+2) = 80
contra 330: el cadaver de dos premios que el pivote evita no estaba en oferta.
`THE_PIVOT_NEEDS_A_CORPSE_THEY_CAN_TAKE` lo veta cuando el cuerpo de delante ya
noquea y esa proyeccion no lo alcanza.

    La lectura NO es la de su banca. Una primera version pregunto por la
    respuesta inmediata (`_promoted_reply_damage`) y apagaba `registro_005` paso
    56, un hallazgo ya medido: alli la respuesta inmediata es de **10** y aun
    asi retirar es lo bueno, porque lo que teme es el Powerful Hand que la linea
    Abra -> Kadabra -> Alakazam monta DESPUES. `_powerful_hand_projected` es
    exactamente esa lectura, y separa los cinco tableros de la familia sola.

SEGUNDO: ¿QUIEN SE SIENTA? El retiro y la promocion son menus distintos y solo
el primero conoce la frase. En este mismo turno los dos candidatos entraron en
la misma banda (+PROMO_KO_BONUS) y el ex gano por los adornos -- Ogerpon ex
**20557** contra Dipplin **20525**, treinta y dos puntos -- asi que la premisa
que justificaba el retiro no la cumplio nadie.
`THE_PIVOT_PROMOTES_THE_BODY_IT_PAYS_FOR` le pasa a ese menu la MISMA lista que
justifico el retiro (`_alk_koers`, una sola copia de la aritmetica) con
`PROMO_PIVOT_PAYS_FOR_THE_SEAT` (2200), del tamaño de un desempate.

    Y con el mismo limite: si su proyeccion mata al cuerpo de un premio pero NO
    al asiento de dos que tendria enfrente, el "descuento" es un premio
    regalado y el asiento se queda donde estaba. Sin ese limite la regla le
    quitaba el asiento a un Hydrapple ex de 330 en `registro_010` turno 10 --
    una retirada que habia pagado OTRA regla -- para un Dipplin que su mano
    mata.

MEDIDO: censo sobre 32 partidas de Alakazam, 7 decisiones de 2 416 (1 de ellas
la segunda mitad); FUERA del matchup, 0 de 3 940 en 60 partidas. Corpus local 0
flips; corpus congelado 1 flip en 3 580, revisado (`registro_008_alakazam_8`
turno 16: un Hydrapple ex 330/330 delante de un Alakazam de 140 que deja de
retirarse). Suite completa en verde.
"""

import copy
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
for _p in (str(ROOT), str(ROOT / "tests")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import main as m  # noqa: E402
from golden_corpus import reset_agent  # noqa: E402

HYDRAPPLE = m.Hydrapple_ex
OGERPON = m.Teal_Mask_Ogerpon_ex
DIPPLIN = m.Dipplin
MEGANIUM = m.Meganium
KADABRA = m.Kadabra

ATTACK, RETREAT, END = 0, 1, 2

_FIXTURE = ROOT / "tests" / "fixtures" / "the_front_seat_vs_alakazam_step068.json"
# El mismo patron, en la partida que el usuario trajo: episode 93519870 paso
# 113, `registro_008` (GANADA). Aqui el Hydrapple ex esta ENTERO -- 330/330 --
# la mano rival son DOS cartas y el asiento se lo llevaba un Teal Mask Ogerpon
# ex de 210 con SEIS Grass encima.
_FIXTURE_93519870 = (ROOT / "tests" / "fixtures"
                     / "the_front_seat_vs_alakazam_ep93519870_step113.json")
# Y el menu que ese retiro abre, dos observaciones despues: la SEGUNDA mitad del
# hallazgo, donde se decide quien se sienta.
_FIXTURE_PROMOTION = (ROOT / "tests" / "fixtures"
                      / "the_seat_the_alakazam_pivot_paid_for.json")


@pytest.fixture(autouse=True)
def _reset():
    reset_agent(m)
    yield
    reset_agent(m)


def _observation(path=None):
    with open(path or _FIXTURE, encoding="utf-8") as f:
        return copy.deepcopy(json.load(f)["observation"])


def _sides(obs):
    cur = obs["current"]
    return (cur["players"][cur["yourIndex"]],
            cur["players"][1 - cur["yourIndex"]])


# ---------------------------------------------------------------------------
# 1. El tablero del hallazgo
# ---------------------------------------------------------------------------

def test_the_board_is_the_one_the_finding_describes():
    """El cuerpo de dos premios con mas vida esta delante y cargado; detras
    esperan el cuerpo de un premio que dispara el pivote y el ex cargado que le
    va a quitar el asiento."""
    obs = _observation()
    mine, theirs = _sides(obs)

    active = mine["active"][0]
    assert active["id"] == HYDRAPPLE
    assert (active["hp"], active["maxHp"]) == (300, 330)
    assert len(active["energies"]) == 4      # puede atacar Y pagar la retirada

    # No hay en la mesa ningun cuerpo nuestro con mas vida: el asiento ya lo
    # ocupa el maximo.
    assert max(b["hp"] for b in mine["bench"]) < active["hp"]

    # El cuerpo de un premio que dispara el pivote...
    dipplin = [b for b in mine["bench"] if b["id"] == DIPPLIN]
    assert len(dipplin) == 1 and len(dipplin[0]["energies"]) == 2
    # ...y el ex cargado que, en la promocion, le gana el asiento.
    assert any(b["id"] == OGERPON and len(b["energies"]) >= 3
               for b in mine["bench"])
    # El Meganium de la banca NO llega a su coste (Petal Dance = 4), asi que no
    # es el "designado" de la promocion vs Alakazam.
    assert [len(b["energies"]) for b in mine["bench"] if b["id"] == MEGANIUM] == [2]

    # Su lado: la linea de Alakazam delante, y el menu de siempre.
    assert theirs["active"][0]["id"] == KADABRA and theirs["active"][0]["hp"] == 80
    tipos = [o.get("type") for o in obs["select"]["option"]]
    assert tipos == [m.OptionType.ATTACK, m.OptionType.RETREAT, m.OptionType.END]


# ---------------------------------------------------------------------------
# 2. La decision, y su control
# ---------------------------------------------------------------------------

def test_the_biggest_two_prize_body_keeps_the_seat_and_attacks():
    """El hallazgo en una assertion."""
    assert m.agent(_observation()) == [ATTACK]


def test_without_the_switch_the_board_reproduces_the_recorded_retreat(monkeypatch):
    """El control: apagado el interruptor, el tablero vuelve a jugar lo que se
    jugo -- asi que el fixture es un testigo y no un tablero que se habria
    contestado bien de todas formas."""
    monkeypatch.setattr(m, "THE_PIVOT_NEEDS_A_CORPSE_THEY_CAN_TAKE", False)
    assert m.agent(_observation()) == [RETREAT]


# ---------------------------------------------------------------------------
# 3. El mecanismo: quien se sienta, no quien amenaza
# ---------------------------------------------------------------------------

def test_the_pivot_wakes_up_when_their_hand_reaches_the_body():
    """No es un apagon del pivote, es un umbral. `_powerful_hand_projected` son
    20 x (mano + 2): con TRECE cartas alcanza los 300 del Hydrapple, el cadaver
    de dos premios vuelve a estar en oferta y el motor retira como antes."""
    obs = _observation()
    _, theirs = _sides(obs)
    theirs["handCount"] = 13                  # 20 x 15 = 300 >= 300
    assert m._powerful_hand_projected(13) >= 300
    assert m.agent(obs) == [RETREAT]


def test_one_card_below_the_threshold_the_seat_still_stays():
    """Y el otro lado del mismo umbral, para que la regla no sea una franja
    vaga: con DOCE la proyeccion se queda en 280 y el cuerpo grande no se
    mueve."""
    obs = _observation()
    _, theirs = _sides(obs)
    theirs["handCount"] = 12                  # 20 x 14 = 280 < 300
    assert m._powerful_hand_projected(12) < 300
    assert m.agent(obs) == [ATTACK]


# ---------------------------------------------------------------------------
# 4. El segundo testigo: la partida del usuario, con el cuerpo ENTERO delante
# ---------------------------------------------------------------------------

def test_the_users_record_keeps_the_full_hydrapple_in_front():
    """episode 93519870 paso 113 (`registro_008`, GANADA): Hydrapple ex
    330/330 con cuatro Grass, un Kadabra de 80 enfrente, la mano rival en DOS
    cartas... y un Ogerpon ex de 210 con seis Grass esperando el asiento. El
    motor pagaba la retirada (el Hydrapple bajaba a la banca a CERO energias) y
    dejaba delante al cuerpo pequeño."""
    obs = _observation(_FIXTURE_93519870)
    mine, theirs = _sides(obs)

    active = mine["active"][0]
    assert active["id"] == HYDRAPPLE and active["hp"] == active["maxHp"] == 330
    assert len(active["energies"]) == 4
    assert theirs["active"][0]["id"] == KADABRA
    assert theirs["handCount"] == 2          # Powerful Hand = 20 x 2 = 40
    # El cuerpo de un premio que dispara el pivote, y el ex cargado que le quita
    # el asiento en la promocion.
    assert any(b["id"] == DIPPLIN and b["energies"] for b in mine["bench"])
    assert any(b["id"] == OGERPON and len(b["energies"]) >= 3 for b in mine["bench"])

    indices = {o.get("type"): i for i, o in enumerate(obs["select"]["option"])}
    assert m.agent(obs) == [indices[m.OptionType.ATTACK]]


def test_the_users_record_without_the_switch_retreats_as_it_did(monkeypatch):
    """El control del segundo testigo: apagado el interruptor, vuelve a jugar
    la retirada que quedo grabada."""
    monkeypatch.setattr(m, "THE_PIVOT_NEEDS_A_CORPSE_THEY_CAN_TAKE", False)
    obs = _observation(_FIXTURE_93519870)
    indices = {o.get("type"): i for i, o in enumerate(obs["select"]["option"])}
    assert m.agent(obs) == [indices[m.OptionType.RETREAT]]


# ---------------------------------------------------------------------------
# 5. La segunda mitad: el asiento acaba en el cuerpo que pago la retirada
# ---------------------------------------------------------------------------

def _promotion_menu(hand):
    """El menu de promocion que abre la retirada, con la mano rival dada."""
    obs = _observation(_FIXTURE_PROMOTION)
    _, theirs = _sides(obs)
    theirs["handCount"] = hand
    return obs


def _promoted(obs, choice):
    cur = obs["current"]
    bench = cur["players"][cur["yourIndex"]]["bench"]
    return bench[obs["select"]["option"][choice[0]]["index"]]["id"]


def test_the_seat_goes_to_the_body_the_retreat_paid_for():
    """Con su mano en QUINCE (20 x 17 = 340) el Powerful Hand proyectado alcanza
    tambien al Ogerpon ex de 210: los dos cuerpos son cadaver, elegimos cual, y
    el descuento del pivote es real. El asiento es del Dipplin."""
    obs = _promotion_menu(15)
    assert _promoted(obs, m.agent(obs)) == DIPPLIN


def test_without_the_second_switch_the_ex_takes_the_seat_again(monkeypatch):
    """El control de la segunda mitad: apagado el interruptor, el mismo tablero
    vuelve a sentar al ex de dos premios."""
    monkeypatch.setattr(m, "THE_PIVOT_PROMOTES_THE_BODY_IT_PAYS_FOR", False)
    obs = _promotion_menu(15)
    assert _promoted(obs, m.agent(obs)) == OGERPON


def test_a_cheap_corpse_they_could_not_take_anyway_is_a_gift():
    """Y el limite, que es la misma frase de la primera mitad leida en este
    menu: con su mano en DOS, su Powerful Hand proyectado (80) mata al Dipplin y
    NO al Ogerpon ex. Ahi el cuerpo barato no sustituye a ningun cadaver: regala
    un premio. El asiento se queda donde estaba."""
    obs = _promotion_menu(2)
    assert m._powerful_hand_projected(2) >= 80      # mata al Dipplin
    assert m._powerful_hand_projected(2) < 210      # y no al Ogerpon ex
    assert _promoted(obs, m.agent(obs)) == OGERPON


def test_the_users_record_wakes_the_pivot_at_its_own_threshold():
    """El umbral, sobre el tablero del usuario: el Hydrapple ENTERO son 330, y
    hacen falta QUINCE cartas en su mano para que el Powerful Hand proyectado
    los alcance. Con esa mano el pivote vuelve a ser un descuento y se cobra."""
    obs = _observation(_FIXTURE_93519870)
    _, theirs = _sides(obs)
    assert m._powerful_hand_projected(14) < 330 <= m._powerful_hand_projected(15)
    theirs["handCount"] = 15
    indices = {o.get("type"): i for i, o in enumerate(obs["select"]["option"])}
    assert m.agent(obs) == [indices[m.OptionType.RETREAT]]
