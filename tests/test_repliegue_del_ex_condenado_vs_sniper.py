"""El repliegue del ex condenado solo niega premios si el ex SOBREVIVE abajo.

Es la otra mitad de la estrategia del registro_004 t4 vs Marnie's Grimmsnarl
(ver `test_pesca_de_remate_probabilistica.py`): si la pesca falla y el turno se
cierra sin ataque, el plan del user es RETIRAR el ex condenado para poner
delante un cuerpo de 1 premio. Eso ya lo hace `_doomed_ex_sac_pivot` (score
6530)... pero su aritmetica daba por hecho que en la banca el ex esta a salvo.

Contra un atacante que ADEMAS pega a la banca no lo esta. Shadow Bullet del
Marnie's Grimmsnarl ex hace 180 al activo Y 30 a un banquillo, y nuestro Teal
Mask Ogerpon ex venia a 30 PV:

    quedarse   -> le noquean el ex activo                        = 2 premios
    retirarse  -> le noquean el cuerpo promovido (1 premio) Y el
                  snipe remata al ex escondido (2 premios)       = 3 premios

Retirarse nunca gana en ese caso: como mucho empata (cuando el snipe iba a
matar igual otro cuerpo de banca del mismo precio). La guarda apaga el pivote.

Se mide con el ATACANTE que tenemos delante (`OP_BENCH_SNIPE_DAMAGE` del activo
rival), no con el flag de mesa `_op_bench_snipe_dmg`: ese cae a un 30 por
defecto en cuanto hay cualquier amenaza de goteo en juego, y apagar el pivote
por un sniper que esta en la BANCA rival costo -3.1 puntos vs crustle/Kangaskhan
en self-play (n=1500). Con la version estrecha los deltas vuelven al ruido.
"""

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import main as m
from state_builder import Escenario, G, pk

GRIMMSNARL = 648      # Shadow Bullet: 180 al activo + 30 a un banquillo
MORGREM = 647         # Corkscrew Punch: 60, sin snipe
IMPIDIMP = 646
SNORUNT = 860
DARK = 7


@pytest.fixture(autouse=True)
def reset_main_state():
    m._init_cartas_tracking()
    m._cartas_first_scan_done = False
    m._cartas_prizes_identified = False
    m._cartas_last_turn = -1
    m.plan = m.AttackPlan()
    m.pre_turn = 0
    m.ko_last_turn = False
    m._ko_detected_this_turn = False
    m._prev_op_prize = 6
    m.meganium_in_play = False
    m.forest_in_play = False
    m.we_go_first = False
    m.op_is_crustle_deck = False
    m.op_is_cornerstone_deck = False
    m.op_has_mega_kangaskhan = False
    m._field_at_turn_start = {}
    yield
    m._init_cartas_tracking()


def _cierre_de_turno(activo_rival="grimmsnarl", hp_ogerpon=30):
    """Fin de turno tras una pesca fallida: Supporter gastado, sin energia y
    con el Ogerpon ex condenado delante. El menu solo ofrece RETIRAR y END,
    como el paso 55 real."""
    grimm = pk(GRIMMSNARL, hp=320, max_hp=320, energias=[DARK, DARK],
               pre_evo=[IMPIDIMP])
    morgrem = pk(MORGREM, hp=100, max_hp=100, energias=[DARK, DARK],
                 pre_evo=[IMPIDIMP])
    if activo_rival == "grimmsnarl":
        act_rival, banca_rival = grimm, morgrem
    else:
        act_rival, banca_rival = morgrem, grimm

    esc = (Escenario(turno=4, paso=55, tac=8, primer_jugador=1,
                     partidario_jugado=True)
           .mi_activo(pk(m.Teal_Mask_Ogerpon_ex, hp=hp_ogerpon,
                         energias=[G], fisicas=1))
           .mi_banca(pk(m.Meowth_ex),
                     pk(m.Fezandipiti_ex, hp=180, energias=[G], fisicas=1),
                     pk(m.Applin),
                     pk(m.Teal_Mask_Ogerpon_ex),
                     pk(m.Bayleef, pre_evo=[m.Chikorita]))
           .mi_mano(m.Ultra_Ball, m.Bug_Catching_Set, m.Night_Stretcher)
           .op_activo(act_rival)
           .op_banca(banca_rival, pk(SNORUNT, hp=70, max_hp=70),
                     pk(IMPIDIMP, hp=70, max_hp=70, energias=[DARK, DARK]))
           .op_zonas(mano=5, mazo=32, premios=6))
    esc.mazo(*sorted(esc._pool.elements())[:34]).resto_al_descarte()
    obs = esc.menu_mano(con_retirada=True).construir()
    obs["select"]["option"] = [
        o for o in obs["select"]["option"]
        if o["type"] in (int(m.OptionType.RETREAT), int(m.OptionType.END))]
    return obs


def _elige(obs):
    return obs["select"]["option"][m.agent(obs)[0]]["type"]


def test_el_ex_a_30_pv_no_se_esconde_del_shadow_bullet():
    """Con el sniper DELANTE, retirarse regala el tercer premio: se aguanta."""
    obs = _cierre_de_turno(activo_rival="grimmsnarl", hp_ogerpon=30)
    assert m.OP_BENCH_SNIPE_DAMAGE[GRIMMSNARL] >= 30, "el snipe alcanza los 30 PV"
    assert _elige(obs) == int(m.OptionType.END)


def test_con_vida_por_encima_del_snipe_el_repliegue_sigue_vivo():
    """Control: el MISMO tablero con el ex a 60 PV -- el snipe de 30 ya no lo
    mata en la banca-- vuelve a retirar y sacrificar el cuerpo de 1 premio."""
    obs = _cierre_de_turno(activo_rival="grimmsnarl", hp_ogerpon=60)
    assert _elige(obs) == int(m.OptionType.RETREAT)


def test_con_un_atacante_sin_snipe_delante_se_repliega():
    """Control: Morgrem (60 de dano, sin snipe) tambien condena al ex de 30 PV,
    pero no llega a la banca -> esconderlo SI niega el premio."""
    obs = _cierre_de_turno(activo_rival="morgrem", hp_ogerpon=30)
    assert MORGREM not in m.OP_BENCH_SNIPE_DAMAGE
    assert _elige(obs) == int(m.OptionType.RETREAT)
