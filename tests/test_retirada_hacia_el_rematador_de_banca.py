"""The Grass pays the ACTIVE's RETREAT so the benched finisher can attack.

Scenario (user, registro_006 step 101, episode 88492701 vs Alakazam, LOST):
turn 6 with an **ACTIVE Applin at 0 energies** (retreat cost 1) and a **Teal
Mask Ogerpon ex on the bench at 6 effective energies** that KNOCKS OUT the active
Alakazam (Myriad Leaf Shower 240 against 140 HP). The manual attachment was already spent, but
the charging ability of the benched Hydrapple ex was still alive and there was a Grass in
hand. The correct line was three steps long:

    Ripening Charge -> Grass to the ACTIVE -> RETREAT -> promote the Ogerpon -> KO

The agent activated the ability, sent the Grass to a BENCHED Ogerpon and closed the
turn without attacking, with the finisher trapped behind the Applin.

Two chained failures, both deck-agnostic:

1. `_grass_unlocks_active_retreat` aborted the whole line with
   `_can_attack_eff(active, e + 1)`: since the Applin "reaches its attack cost"
   with one Grass, the detector returned (False, False) -- even though the damage
   model does not grant the Applin A SINGLE point. Now DAMAGE is compared.
2. `energy_score` -- which decides WHICH Pokemon the energy goes to, both in the manual
   attachment and in the target of the abilities (SelectContext.ATTACH_FROM) --
   had no branch for this line: the ACTIVE fell into the generic development
   band (~8000) and any benched body beat it. As a bonus, the Ogerpon charging
   focus (41700) pointed at a SECOND finisher just as trapped.

The tests are deck-agnostic on purpose: the trapped active and the benched
finisher are parameterised, and the central case uses an active (Applin) whose "attack" is
exactly what fooled the detector.
"""

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import main as m
from state_builder import G, Escenario, pk

APPLIN = m.Applin                   # the trapped active: 0 energies, cost 1
DIPPLIN = m.Dipplin
OGERPON = m.Teal_Mask_Ogerpon_ex    # the benched finisher (Myriad Leaf Shower)
TAPU = m.Tapu_Bulu                  # a finisher WITHOUT a charging ability
HYDRAPPLE = m.Hydrapple_ex          # the bearer of Ripening Charge
MEOWTH = m.Meowth_ex
ULTRA_BALL = m.Ultra_Ball
GRASS = m.Basic_Grass_Energy

FEZANDIPITI = m.Fezandipiti_ex      # the trapped active of episode 88603018
MEGANIUM = m.Meganium

ALAKAZAM = 743                      # 140 HP: the opposing active of the record
KADABRA = 742
ABRA = 741
DUNSPARCE = 305
SHAYMIN = 343                       # 80 HP: the opposing active of 88603018


@pytest.fixture(autouse=True)
def reset_main_state():
    m._init_cards_tracking()
    m._cards_first_scan_done = False
    m._cards_prizes_identified = False
    m._cards_last_turn = -1
    m.plan = m.AttackPlan()
    m.pre_turn = 0
    m.meganium_in_play = False
    m.forest_in_play = False
    m.ko_last_turn = False
    m._ko_detected_this_turn = False
    m._prev_op_prize = 6
    m.we_go_first = False
    m.op_is_crustle_deck = False
    m.op_is_cornerstone_deck = False
    m.op_has_mega_kangaskhan = False
    m._field_at_turn_start = {}
    m._poke_pad_target_id = 0
    m._ub_meowth_pending = False
    m._grass_attaches_this_turn = 0
    m._dodge_immune_serial = None
    m._dodge_immune_turn = -1
    yield
    m._init_cards_tracking()


def _escenario(activo=None, banca=None, mano=(GRASS, ULTRA_BALL),
               energia_jugada=True, op_hp=140, op_energias=1):
    """The record's board: a trapped active + a ready benched finisher."""
    activo = activo if activo is not None else pk(APPLIN)
    banca = banca if banca is not None else [
        pk(OGERPON, energias=[G] * 6, fisicas=3),   # ALREADY lethal: 30+30*(6+1)=240
        pk(HYDRAPPLE),                              # the bearer of Ripening Charge
        pk(MEOWTH),
    ]
    return (Escenario(turno=6, paso=101, energia_jugada=energia_jugada)
            .mi_activo(activo)
            .mi_banca(*banca)
            .mi_mano(*mano)
            .op_activo(pk(ALAKAZAM, hp=op_hp, energias=[G] * op_energias))
            .op_zonas(mano=6, mazo=20, prizes=3))


def _destino(obs, eleccion):
    """The area of the Pokemon chosen as the charge's destination."""
    o = obs["select"]["option"][eleccion[0]]
    return o.get("area", o.get("inPlayArea"))


# ---------------------------------------------------------------------------
# The record's failure: the target of the charging ABILITY (ATTACH_FROM)
# ---------------------------------------------------------------------------

def test_la_habilidad_de_carga_pone_la_planta_en_el_activo_atrapado():
    """The exact case of step 101: the Ripening Charge Grass goes to the ACTIVE
    to pay its retreat, not to a benched body."""
    obs = _escenario().objetivo_carga_habilidad(banca_idx=1).construir()
    assert _destino(obs, m.agent(obs)) == int(m.AreaType.ACTIVE)


def test_el_foco_de_ogerpon_no_roba_la_planta_de_la_retirada():
    """A direct regression: with a SECOND half-charged Ogerpon, the lethal
    charging focus (41700) took the Grass and left both finishers
    trapped behind the active. While the retreat is not paid for, charging
    the bench promotes nobody."""
    banca = [pk(OGERPON, energias=[G] * 6, fisicas=3),
             pk(HYDRAPPLE),
             pk(OGERPON, energias=[G, G], fisicas=1)]   # the focus's bait
    obs = _escenario(banca=banca).objetivo_carga_habilidad(banca_idx=1).construir()
    assert _destino(obs, m.agent(obs)) == int(m.AreaType.ACTIVE)


def test_deck_agnostico_cualquier_rematador_de_banca_sirve():
    """The line does not depend on Ogerpon or on its ability: with an already charged
    Tapu Bulu (220 >= 140) the Grass must still go to the ACTIVE."""
    banca = [pk(TAPU, energias=[G] * 4), pk(HYDRAPPLE), pk(MEOWTH)]
    obs = _escenario(banca=banca).objetivo_carga_habilidad(banca_idx=1).construir()
    assert _destino(obs, m.agent(obs)) == int(m.AreaType.ACTIVE)


# ---------------------------------------------------------------------------
# The same line through the MANUAL attachment
# ---------------------------------------------------------------------------

def test_el_adjunte_manual_tambien_va_al_activo_atrapado():
    obs = (_escenario(energia_jugada=False)
           .menu_mano(con_adjunte=True).construir())
    eleccion = m.agent(obs)
    o = obs["select"]["option"][eleccion[0]]
    assert o["type"] == int(m.OptionType.ATTACH)
    assert o["inPlayArea"] == int(m.AreaType.ACTIVE)


# ---------------------------------------------------------------------------
# The same line with MEGANIUM in play (episode 88603018 step 106, vs Alakazam)
# ---------------------------------------------------------------------------
#
# The production board that had to be pinned: an ACTIVE Fezandipiti ex at 0
# energies (cost 1), a benched Meganium doubling every Grass with Wild Growth,
# THREE already charged Ogerpon ex behind it and a single Grass in hand. The
# uploaded build sent the energy to the MEGANIUM and closed the turn without attacking.
#
# Meganium in play matters because it opens a whole branch of `energy_score`
# (the Grass distribution across the bench, with Meganium in its priority table)
# that competes with this line's ACTIVE destination. None of the tests
# above had it on the field.


def _escenario_meganium(activo=None, mano=(GRASS, ULTRA_BALL)):
    activo = activo if activo is not None else pk(FEZANDIPITI)
    return (Escenario(turno=10, paso=106, energia_jugada=False)
            .mi_activo(activo)
            .mi_banca(pk(MEGANIUM, energias=[G, G], fisicas=1),
                      pk(OGERPON, energias=[G] * 6, fisicas=3),
                      pk(OGERPON, energias=[G] * 4, fisicas=2),
                      pk(MEOWTH),
                      pk(OGERPON, hp=70, energias=[G] * 6, fisicas=3))
            .mi_mano(*mano)
            .op_activo(pk(SHAYMIN))
            .op_banca(pk(KADABRA, pre_evo=[ABRA]), pk(DUNSPARCE), pk(ABRA),
                      pk(DUNSPARCE))
            .op_zonas(mano=8, mazo=20, prizes=5))


def test_con_meganium_en_juego_la_planta_sigue_yendo_al_activo_atrapado():
    """Regression of episode 88603018 step 106: with Wild Growth active and the
    bench full of charged Ogerpon, the only Grass must pay the retreat of the
    Fezandipiti ex -- not fatten the Meganium."""
    obs = _escenario_meganium().menu_mano(con_adjunte=True).construir()
    o = obs["select"]["option"][m.agent(obs)[0]]
    assert o["type"] == int(m.OptionType.ATTACH)
    assert o["inPlayArea"] == int(m.AreaType.ACTIVE)


def test_con_meganium_el_detector_ve_la_linea_letal():
    obs = _escenario_meganium().menu_mano(con_adjunte=True).construir()
    assert _detector(obs) == (True, False)


def test_con_meganium_el_activo_que_ya_se_retira_no_dispara_la_linea():
    """A detector boundary: with one physical Grass on it, the Fezandipiti ex already
    pays its cost-1 retreat and there is nothing to unlock.

    Careful when reading it: the attachment STILL goes to the active on that board, but through
    another rule (`_carga_activo_remata`) -- with 4 effective units Cruel Arrow becomes
    playable and knocks out the 80 HP Shaymin. Attacking beats pivoting."""
    obs = (_escenario_meganium(activo=pk(FEZANDIPITI, energias=[G, G], fisicas=1))
           .menu_mano(con_adjunte=True).construir())
    assert _detector(obs) == (False, False)


def test_con_meganium_sin_nada_que_desbloquear_la_planta_vuelve_a_la_banca():
    """A DESTINATION boundary: the active does not win for being the active. With the
    Fezandipiti ex already able to retreat AND to attack, the Grass unlocks
    nothing and goes back to the normal bench distribution."""
    obs = (_escenario_meganium(activo=pk(FEZANDIPITI, energias=[G] * 4, fisicas=2))
           .menu_mano(con_adjunte=True).construir())
    o = obs["select"]["option"][m.agent(obs)[0]]
    assert o["type"] == int(m.OptionType.ATTACH)
    assert o["inPlayArea"] == int(m.AreaType.BENCH)


# ---------------------------------------------------------------------------
# Closing the chain: with the energy placed, it retreats and promotes
# ---------------------------------------------------------------------------

def test_con_la_planta_puesta_el_activo_se_retira():
    obs = (_escenario(activo=pk(APPLIN, energias=[G]), mano=(ULTRA_BALL,))
           .menu_mano(con_retirada=True).construir())
    o = obs["select"]["option"][m.agent(obs)[0]]
    assert o["type"] == int(m.OptionType.RETREAT)


def test_al_promover_sube_el_rematador():
    obs = (_escenario(activo=pk(APPLIN, energias=[G]), mano=(ULTRA_BALL,))
           .promocion_desde_banca().construir())
    idx = obs["select"]["option"][m.agent(obs)[0]]["index"]
    assert obs["current"]["players"][0]["bench"][idx]["id"] == OGERPON


# ---------------------------------------------------------------------------
# Detector boundaries (`_grass_unlocks_active_retreat`)
# ---------------------------------------------------------------------------

def _detector(obs):
    """(ko, chip) of the shared core over the built state."""
    o = m.to_observation_class(obs)
    st = o.current
    mio, rival = st.players[0], st.players[1]
    m.meganium_in_play = False
    total_grass = sum(len(p.energies)
                      for p in ([mio.active[0]] if mio.active else []) + list(mio.bench)
                      if p is not None)
    return m._grass_unlocks_active_retreat(
        mio, rival, False, total_grass, len(mio.bench), False, False)


def test_detector_ve_la_linea_letal():
    obs = _escenario().objetivo_carga_habilidad(banca_idx=1).construir()
    assert _detector(obs) == (True, False)


def test_si_el_activo_remata_con_esa_planta_no_se_retira():
    """Boundary: attacking with the active comes first. With an active Dipplin whose
    attack (20 x bench) knocks the opponent out, the retreat line does NOT switch on."""
    obs = (_escenario(activo=pk(DIPPLIN), op_hp=60)
           .objetivo_carga_habilidad(banca_idx=1).construir())
    assert _detector(obs) == (False, False)


def test_sin_rematador_de_banca_no_hay_linea():
    """Boundary: if there is nobody ready on the bench, the Grass has no reason to
    go to the active (there is nothing to promote)."""
    banca = [pk(OGERPON), pk(HYDRAPPLE), pk(MEOWTH)]
    obs = _escenario(banca=banca).objetivo_carga_habilidad(banca_idx=1).construir()
    assert _detector(obs) == (False, False)


def test_si_el_activo_ya_paga_su_retirada_no_hay_nada_que_desbloquear():
    obs = (_escenario(activo=pk(APPLIN, energias=[G]))
           .objetivo_carga_habilidad(banca_idx=1).construir())
    assert _detector(obs) == (False, False)


# ---------------------------------------------------------------------------
# The production board of episode 88631738 step 77 (WON, with turn
# 8 given away): an ACTIVE Meowth ex at 0 energies (retreat cost 1) that cannot
# attack, a benched Hydrapple ex at 4 effective that KNOCKS OUT the Mega Starmie ex, the
# manual attachment ALREADY spent and two Grass in hand. The uploaded build closed
# the turn (END) with a 3-prize finisher on the table: the only live route was the
# ABILITY (Ripening Charge does not consume the turn's attachment).
# ---------------------------------------------------------------------------

MEGA_STARMIE = 1031                 # 330 HP, at 240 in the record


def _escenario_88631738(activo=None, mano=(GRASS, GRASS, ULTRA_BALL),
                        energia_jugada=True):
    activo = activo if activo is not None else pk(MEOWTH, hp=50)
    return (Escenario(turno=8, paso=77, energia_jugada=energia_jugada,
                      partidario_jugado=True)
            .mi_activo(activo)
            .mi_banca(pk(OGERPON, energias=[G] * 4, fisicas=2),
                      pk(HYDRAPPLE, hp=280, energias=[G] * 4, fisicas=2),
                      pk(FEZANDIPITI),
                      pk(MEGANIUM),
                      pk(OGERPON, energias=[G] * 2, fisicas=1))
            .mi_mano(*mano)
            .op_activo(pk(MEGA_STARMIE, hp=240))
            .op_banca(pk(1030))
            .op_zonas(mano=2, mazo=39, prizes=4))


def test_88631738_la_habilidad_carga_al_activo_con_el_adjunte_ya_gastado():
    """The record's failure: with `energyAttached` set, the only live route is
    Ripening Charge -- and its Grass has to go to the ACTIVE to pay the
    retreat, not to a benched Ogerpon."""
    obs = _escenario_88631738().objetivo_carga_habilidad(banca_idx=1).construir()
    assert _destino(obs, m.agent(obs)) == int(m.AreaType.ACTIVE)


def test_88631738_con_la_planta_puesta_el_activo_se_retira():
    obs = (_escenario_88631738(activo=pk(MEOWTH, hp=50, energias=[G, G],
                                         fisicas=1),
                               mano=(ULTRA_BALL,))
           .menu_mano(con_retirada=True).construir())
    o = obs["select"]["option"][m.agent(obs)[0]]
    assert o["type"] == int(m.OptionType.RETREAT)


def test_88631738_al_promover_sube_el_hydrapple_que_remata():
    obs = (_escenario_88631738(activo=pk(MEOWTH, hp=50, energias=[G, G],
                                         fisicas=1),
                               mano=(ULTRA_BALL,))
           .promocion_desde_banca().construir())
    idx = obs["select"]["option"][m.agent(obs)[0]]["index"]
    assert obs["current"]["players"][0]["bench"][idx]["id"] == HYDRAPPLE


# ---------------------------------------------------------------------------
# The charging BUDGET: a retreat of 2 or 3 symbols is paid for too
# ---------------------------------------------------------------------------
#
# The detector measured exactly ONE Grass (`e + unit < rc` -> no line), so
# a trapped active with a retreat cost >1 was invisible even when the turn's live
# routes covered it easily. Now the real charging BUDGET towards the ACTIVE is
# measured (a free manual attachment + `_grass_ability_slots_activo`,
# bounded by the Grass in hand), just like `_carga_activo_remata` does for the
# ATTACK cost.


def _detector_presupuesto(obs, budget):
    o = m.to_observation_class(obs)
    st = o.current
    mio, rival = st.players[0], st.players[1]
    m.meganium_in_play = False
    total_grass = sum(len(p.energies)
                      for p in ([mio.active[0]] if mio.active else []) + list(mio.bench)
                      if p is not None)
    return m._grass_unlocks_active_retreat(
        mio, rival, False, total_grass, len(mio.bench), False, False,
        budget=budget)


def _escenario_coste_3(activo_e=1, mano=(GRASS, GRASS, ULTRA_BALL),
                       energia_jugada=False):
    """An active with a retreat cost of 3 (Tapu Bulu) at `activo_e` energies: it is
    TWO Grass short, and there are two live routes (the manual attachment + Ripening)."""
    return (Escenario(turno=8, paso=40, energia_jugada=energia_jugada)
            .mi_activo(pk(TAPU, energias=[G] * activo_e))
            .mi_banca(pk(OGERPON, energias=[G] * 6, fisicas=3),
                      pk(HYDRAPPLE),
                      pk(MEOWTH))
            .mi_mano(*mano)
            .op_activo(pk(ALAKAZAM, hp=140, energias=[G]))
            .op_zonas(mano=6, mazo=20, prizes=3))


def test_con_presupuesto_de_una_planta_no_hay_linea():
    """A preserved boundary: if only ONE Grass fits, two symbols of retreat
    are still unreachable."""
    obs = _escenario_coste_3().menu_mano(con_adjunte=True).construir()
    assert _detector_presupuesto(obs, 1) == (False, False)


def test_con_presupuesto_de_dos_plantas_el_detector_ve_la_linea():
    obs = _escenario_coste_3().menu_mano(con_adjunte=True).construir()
    assert _detector_presupuesto(obs, 2) == (True, False)


def test_el_adjunte_manual_abre_la_retirada_de_dos_simbolos():
    """The complete chain, step 1: with the manual attachment free and a benched
    Hydrapple ex (Ripening Charge) the 3-symbol retreat is payable, so the
    first Grass goes to the ACTIVE -- not to fatten the bench."""
    obs = _escenario_coste_3().menu_mano(con_adjunte=True).construir()
    o = obs["select"]["option"][m.agent(obs)[0]]
    assert o["type"] == int(m.OptionType.ATTACH)
    assert o["inPlayArea"] == int(m.AreaType.ACTIVE)


def test_la_habilidad_remata_la_segunda_planta_en_el_activo():
    """Step 2: with the attachment already spent and the active one Grass from the cost,
    Ripening Charge points at the ACTIVE again."""
    obs = (_escenario_coste_3(activo_e=2, mano=(GRASS, ULTRA_BALL),
                              energia_jugada=True)
           .objetivo_carga_habilidad(banca_idx=1).construir())
    assert _destino(obs, m.agent(obs)) == int(m.AreaType.ACTIVE)


def test_sin_plantas_suficientes_en_la_mano_no_se_abre_la_linea():
    """The budget is bounded by the HAND: with a single Grass a retreat of two
    cannot be paid for, and the energy is not wasted on the trapped active."""
    obs = (_escenario_coste_3(mano=(GRASS, ULTRA_BALL))
           .menu_mano(con_adjunte=True).construir())
    o = obs["select"]["option"][m.agent(obs)[0]]
    assert not (o["type"] == int(m.OptionType.ATTACH)
                and o["inPlayArea"] == int(m.AreaType.ACTIVE))


WATCHTOWER = m.Team_Rockets_Watchtower   # it switches our charging abilities off


def test_con_las_habilidades_apagadas_el_presupuesto_vuelve_a_una_planta():
    """A budget boundary: with Team Rocket's Watchtower on the field, Ripening
    Charge is switched off, so the second route does NOT exist and the first Grass must
    not be left stranded on an active that will still be unable to retreat."""
    obs = (_escenario_coste_3()
           .estadio(WATCHTOWER, del_rival=True)
           .menu_mano(con_adjunte=True).construir())
    o = obs["select"]["option"][m.agent(obs)[0]]
    assert not (o["type"] == int(m.OptionType.ATTACH)
                and o["inPlayArea"] == int(m.AreaType.ACTIVE))
