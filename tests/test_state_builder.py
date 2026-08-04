"""Tests of the StateBuilder (`Escenario`) and the first parametric boundary sweep.

Phase 1 of the strategy-improvement architecture: validating that the builder
produces observations that `main.agent()` processes just like the real ones.

Validation "against reality": the synthetic replica of step 69 of
registro_008 (vs Crustle/Kangaskhan) must produce the SAME decision as the
real observation (the Ultra Ball searches for Hydrapple ex to evolve the doomed
active Dipplin). From there, the parametric sweep fabricates variants
that NEVER occurred in games (an immune rival active, a Dipplin with no energy)
and verifies the boundaries of the `_ub_evo_doomed_hittable` rule.
"""

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import main as m
from state_builder import C, G, Escenario, EstadoInconsistente, pk

# IDs that are not in our deck.csv (rival cards).
KANGASKHAN = 756
CRUSTLE = 345
DWEBBLE = 344
HEROS_CAPE = 1159


@pytest.fixture(autouse=True)
def reset_main_state():
    m._init_cartas_tracking()
    m._cartas_first_scan_done = False
    m._cartas_prizes_identified = False
    m._cartas_last_turn = -1
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
    m._dodge_immune_serial = None
    m._dodge_immune_turn = -1
    yield
    m._init_cartas_tracking()


def _escenario_paso69(op_activo="kangaskhan", energia_dipplin=2):
    """A synthetic replica of step 69 of registro_008 with variants.

    op_activo: "kangaskhan" (hittable by ex) or "crustle" (immune to ex,
        with the Kangaskhan relegated to the bench).
    energia_dipplin: 2 = as in the real one (1 physical x Meganium = [G, G], it attacks
        after evolving); 0 = no energy (it does not attack after evolving).
    """
    kang = pk(KANGASKHAN, hp=160, max_hp=400, energias=[C, G, C, C],
              fisicas=4, tools=[HEROS_CAPE])
    crustle = pk(CRUSTLE, pre_evo=[DWEBBLE])
    if op_activo == "kangaskhan":
        activo_rival, banca_rival = kang, crustle
    else:
        activo_rival, banca_rival = crustle, kang

    if energia_dipplin == 2:
        dipplin = pk(m.Dipplin, energias=[G, G], fisicas=1,
                     pre_evo=[m.Applin])
    else:
        dipplin = pk(m.Dipplin, energias=[], fisicas=0, pre_evo=[m.Applin])

    esc = (Escenario(turno=8, paso=69, tac=3, primer_jugador=1)
           .mi_activo(dipplin)
           .mi_banca(pk(m.Meganium, pre_evo=[m.Chikorita, m.Bayleef]),
                     pk(m.Teal_Mask_Ogerpon_ex, energias=[G, G], fisicas=1),
                     m.Meowth_ex)
           .mi_mano()
           .estadio(m.Forest_of_Vitality)
           .op_activo(activo_rival)
           .op_banca(banca_rival)
           .op_zonas(mano=9, mazo=37, premios=2)
           .op_descarte(m.Xerosic_Machinations, m.Lillie_Determination,
                        m.Lillie_Determination, 1264)
           # The visible deck: the real composition of the select.deck of step 69.
           .mazo(m.Hydrapple_ex, m.Tapu_Bulu, m.Lillie_Determination,
                 m.Basic_Grass_Energy, m.Basic_Grass_Energy,
                 m.Basic_Grass_Energy, m.Basic_Grass_Energy,
                 m.Basic_Grass_Energy, m.Basic_Grass_Energy,
                 m.Teal_Mask_Ogerpon_ex, m.Hydrapple_ex, m.Chikorita,
                 m.Bug_Catching_Set, m.Night_Stretcher, m.Night_Stretcher,
                 m.Ultra_Ball, m.Boss_Orders, m.Xerosic_Machinations,
                 m.Lillie_Determination, m.Lillie_Determination,
                 m.Forest_of_Vitality, m.Forest_of_Vitality)
           # NOTE: fetch_ultra_ball() BEFORE resto_al_descarte(), so that
           # the Ultra Ball "in effect" is reserved from the pool and does not end up in the
           # discard (the strict accounting detects it if they are swapped).
           .fetch_ultra_ball()
           .resto_al_descarte())
    return esc.construir()


def _carta_elegida(obs, eleccion):
    assert eleccion, f"el agente cancelo el fetch: {eleccion}"
    opt = obs["select"]["option"][eleccion[0]]
    return obs["select"]["deck"][opt["index"]]["id"]


# ---------------------------------------------------------------------
# Validation of the builder against the real decision (step 69)
# ---------------------------------------------------------------------

def test_replica_sintetica_paso69_coincide_con_decision_real():
    obs = _escenario_paso69()
    eleccion = m.agent(obs)
    assert _carta_elegida(obs, eleccion) == m.Hydrapple_ex, (
        "la replica sintetica del paso 69 debe reproducir la decision del "
        "escenario real: buscar Hydrapple ex para evolucionar al Dipplin "
        "activo condenado")


# ---------------------------------------------------------------------
# Boundary sweep of `_ub_evo_doomed_hittable` (states that NEVER
# occurred in real games)
# ---------------------------------------------------------------------

@pytest.mark.parametrize("op_activo,energia_dipplin,espera_hydrapple", [
    # a hittable rival active + a Dipplin that attacks after evolving -> the exception
    ("kangaskhan", 2, True),
    # a rival active IMMUNE to ex -> the exception does not apply, the clamp returns
    ("crustle", 2, False),
    # a Dipplin with no energy: it evolves but does NOT attack -> no exception
    ("kangaskhan", 0, False),
])
def test_frontera_ub_evo_doomed(op_activo, energia_dipplin, espera_hydrapple):
    obs = _escenario_paso69(op_activo=op_activo,
                            energia_dipplin=energia_dipplin)
    eleccion = m.agent(obs)
    elegida = _carta_elegida(obs, eleccion)
    if espera_hydrapple:
        assert elegida == m.Hydrapple_ex, (
            f"con activo rival golpeable y Dipplin que ataca tras "
            f"evolucionar, el fetch debe ser Hydrapple ex; fue {elegida}")
    else:
        assert elegida != m.Hydrapple_ex, (
            f"({op_activo}, e={energia_dipplin}): la excepcion no aplica y "
            f"el clamp vs Crustle debe impedir el fetch de Hydrapple ex; "
            f"fue {elegida}")


# ---------------------------------------------------------------------
# The builder's accounting rejects impossible states
# ---------------------------------------------------------------------

def test_builder_rechaza_mas_copias_que_el_mazo():
    esc = Escenario().mi_activo(pk(m.Dipplin, pre_evo=[m.Applin]))
    with pytest.raises(EstadoInconsistente):
        # deck.csv has 2 Hydrapple ex: the 3rd copy must fail.
        esc.mazo(m.Hydrapple_ex, m.Hydrapple_ex, m.Hydrapple_ex)


def test_builder_rechaza_sobrante_distinto_de_premios():
    esc = (Escenario()
           .mi_activo(pk(m.Dipplin, pre_evo=[m.Applin]))
           .op_activo(pk(KANGASKHAN, hp=160, max_hp=400))
           # a declared deck of 2 cards: ~50 are left unplaced (far more
           # than the 6 prizes) -> the construction must fail.
           .mazo(m.Hydrapple_ex, m.Tapu_Bulu)
           .fetch_ultra_ball())
    with pytest.raises(EstadoInconsistente):
        esc.construir()


# ---------------------------------------------------------------------
# The Meganium line takes priority vs Cornerstone Mask Ogerpon ex (user,
# registro_004 turn 4): its Cornerstone Stance cancels the damage of ALL
# our Pokemon WITH an ability (Teal Mask Ogerpon ex, Hydrapple ex,
# Dipplin...), so the only real attacker is Tapu Bulu. Meganium does not
# damage it either -- it also has an ability -- but its Wild Growth DOUBLES each
# Grass, so that with it in play Tapu attacks with 2 PHYSICAL Grass instead
# of 4. Building the line is therefore a priority in this matchup.
#
# A SYNTHETIC scenario (it does not exist in the current records: none gets to
# play an Ultra Ball against Cornerstone), exactly the case for the StateBuilder.
# ---------------------------------------------------------------------
CORNERSTONE = 117
CUBCHOO = 506


def _fetch_ub_vs(op_id):
    """An Ultra Ball fetch with a Chikorita on the bench and the line in the deck."""
    obs = (Escenario(turno=6, paso=1, tac=1)
           .mi_activo(pk(m.Teal_Mask_Ogerpon_ex, energias=[G], fisicas=1))
           .mi_banca(pk(m.Chikorita))
           .mi_mano()
           .op_activo(pk(op_id, hp=210, max_hp=210))
           .op_zonas(mano=4, mazo=40, premios=6)
           .mazo(m.Meganium, m.Bayleef, m.Tapu_Bulu, m.Teal_Mask_Ogerpon_ex,
                 m.Hydrapple_ex, m.Applin, m.Chikorita, m.Meowth_ex)
           .fetch_ultra_ball()
           .resto_al_descarte()
           .construir())
    eleccion = m.agent(obs)
    sel = obs["select"]
    return sel["deck"][sel["option"][eleccion[0]]["index"]]["id"]


def test_cornerstone_prioriza_linea_meganium():
    elegida = _fetch_ub_vs(CORNERSTONE)
    assert elegida in (m.Meganium, m.Bayleef), (
        f"vs Cornerstone, Wild Growth deja a Tapu Bulu atacando con 2 Plantas "
        f"fisicas en vez de 4: completar la linea Meganium es la busqueda "
        f"prioritaria; obtuvo {m.card_table[elegida].name}")


def test_sin_cornerstone_la_busqueda_no_cambia():
    # Boundary: without Cornerstone the matchup priority does not apply and the fetch
    # keeps its normal behaviour (Bayleef, an immediate evolution).
    elegida = _fetch_ub_vs(CUBCHOO)
    assert elegida == m.Bayleef, (
        f"sin Cornerstone el fetch no debe cambiar; obtuvo "
        f"{m.card_table[elegida].name}")


# ---------------------------------------------------------------------
# Tapu Bulu is the ONLY real attacker vs Cornerstone (user, registro_004
# turn 4): the anti-Cubchoo whitelist (`_CUB_ALLOWED_PLAY`) allowed Teal Mask
# Ogerpon ex and Hydrapple ex -- which because of their ability do ZERO damage to
# Cornerstone -- but excluded Tapu Bulu, the only one that does hit it. The agent
# played a 2nd Ogerpon ex and left Tapu dead in hand.
# ---------------------------------------------------------------------

def _menu_con_tapu_en_mano(op_id):
    """The main menu vs a Cubchoo rival with Cornerstone (or not) as the active."""
    return (Escenario(turno=6, paso=1, tac=1)
            .mi_activo(pk(m.Teal_Mask_Ogerpon_ex, energias=[G], fisicas=1))
            .mi_banca(pk(m.Bayleef, pre_evo=[m.Chikorita]))
            .mi_mano(m.Basic_Grass_Energy, m.Tapu_Bulu)
            .op_activo(pk(op_id, hp=210, max_hp=210))
            .op_banca(pk(CUBCHOO))
            .op_zonas(mano=4, mazo=40, premios=6)
            .menu_attach_energia()
            .construir())


def _energia_va_a(obs, eleccion):
    opt = obs["select"]["option"][eleccion[0]]
    if opt.get("type") != 8:
        return None
    me = obs["current"]["players"][obs["current"]["yourIndex"]]
    destino = (me["active"][0] if opt.get("inPlayArea") == 4
               else me["bench"][opt["inPlayIndex"]])
    return destino["id"]


def test_cornerstone_energia_va_a_tapu_bulu():
    # With Tapu Bulu ALREADY on the bench, the energy must charge it (the only attacker
    # that damages Cornerstone), not the Ogerpon ex with its ability cancelled.
    obs = (Escenario(turno=6, paso=1, tac=1)
           .mi_activo(pk(m.Teal_Mask_Ogerpon_ex, energias=[G], fisicas=1))
           .mi_banca(pk(m.Tapu_Bulu), pk(m.Bayleef, pre_evo=[m.Chikorita]))
           .mi_mano(m.Basic_Grass_Energy)
           .op_activo(pk(CORNERSTONE, hp=210, max_hp=210))
           .op_zonas(mano=4, mazo=40, premios=6)
           .menu_attach_energia()
           .construir())
    assert _energia_va_a(obs, m.agent(obs)) == m.Tapu_Bulu, (
        "vs Cornerstone la energia debe ir a Tapu Bulu: el Ogerpon ex tiene "
        "habilidad y su dano queda anulado")


def test_cornerstone_sin_el_la_energia_no_cambia():
    # Boundary: without Cornerstone the energy distribution keeps its criterion.
    obs = (Escenario(turno=6, paso=1, tac=1)
           .mi_activo(pk(m.Teal_Mask_Ogerpon_ex, energias=[G], fisicas=1))
           .mi_banca(pk(m.Tapu_Bulu), pk(m.Bayleef, pre_evo=[m.Chikorita]))
           .mi_mano(m.Basic_Grass_Energy)
           .op_activo(pk(CUBCHOO, hp=70, max_hp=70))
           .op_zonas(mano=4, mazo=40, premios=6)
           .menu_attach_energia()
           .construir())
    assert _energia_va_a(obs, m.agent(obs)) == m.Teal_Mask_Ogerpon_ex, (
        "sin Cornerstone la energia sigue yendo al atacante habitual")


# ---------------------------------------------------------------------
# The energy cap of Teal Mask Ogerpon ex vs the Hop's deck (user):
# a maximum of 3 PHYSICAL energies without Meganium in play / 2 with Meganium. The ONLY
# reason to go over it (a manual attachment, Ripening Charge or Teal Dance) is that the
# Ogerpon is ACTIVE and is missing that energy to KNOCK OUT the rival
# active. SYNTHETIC scenarios (the records vs Hop's do not reach 3 charges).
# ---------------------------------------------------------------------
TREVENANT = 879     # Hop's Trevenant (140 HP): it switches on op_is_hop_deck


def _jugada_elegida(obs, eleccion):
    """('ABILITY', None) for Teal Dance; ('ATTACH', destination id) for an attachment."""
    opt = obs["select"]["option"][eleccion[0]]
    if opt.get("type") == int(m.OptionType.ABILITY):
        return ("ABILITY", None)
    if opt.get("type") != int(m.OptionType.ATTACH):
        return ("OTRA", opt.get("type"))
    me = obs["current"]["players"][obs["current"]["yourIndex"]]
    destino = (me["active"][0] if opt.get("inPlayArea") == int(m.AreaType.ACTIVE)
               else me["bench"][opt["inPlayIndex"]])
    return ("ATTACH", destino["id"])


def _esc_hop(activo, banca, op_energias=(), menu="attach"):
    esc = (Escenario(turno=8, paso=1, tac=1)
           .mi_activo(activo)
           .mi_banca(*banca)
           .mi_mano(m.Basic_Grass_Energy)
           .op_activo(pk(TREVENANT, hp=140, max_hp=140, energias=list(op_energias)))
           .op_zonas(mano=4, mazo=40, premios=4))
    esc = esc.menu_teal_dance() if menu == "teal" else esc.menu_attach_energia()
    return esc.construir()


def test_hop_tope_3_energias_ogerpon_banca():
    # 3 physical on the BENCH Ogerpon = the cap reached: the energy goes to another
    # body (before, the cap was 4 and the Ogerpon was overcharged).
    obs = _esc_hop(pk(m.Dipplin, pre_evo=[m.Applin], energias=[G], fisicas=1),
                   [pk(m.Teal_Mask_Ogerpon_ex, energias=[G, G, G], fisicas=3)])
    tipo, destino = _jugada_elegida(obs, m.agent(obs))
    assert (tipo, destino) != ("ATTACH", m.Teal_Mask_Ogerpon_ex), (
        "vs Hop's un Ogerpon de banca con 3 energias fisicas esta en su tope: "
        "no se le adjunta una 4a")


def test_hop_dos_energias_ogerpon_banca_sigue_permitido():
    # Boundary: with 2 physical the cap does not apply and the charge is still valid.
    obs = _esc_hop(pk(m.Dipplin, pre_evo=[m.Applin], energias=[G], fisicas=1),
                   [pk(m.Teal_Mask_Ogerpon_ex, energias=[G, G], fisicas=2)])
    assert _jugada_elegida(obs, m.agent(obs)) == ("ATTACH", m.Teal_Mask_Ogerpon_ex), (
        "con 2 energias fisicas el Ogerpon aun no llega al tope de Hop's")


def test_hop_cuarta_energia_solo_si_habilita_el_ko():
    # EXCEPTION: an ACTIVE Ogerpon with 3 physical; Myriad does 30+30*(3+0)=120 and does not
    # knock out the 140 Trevenant, but with the 4th it reaches 150 => it is allowed.
    obs = _esc_hop(pk(m.Teal_Mask_Ogerpon_ex, energias=[G, G, G], fisicas=3),
                   [pk(m.Tapu_Bulu, energias=[G, G, G], fisicas=3)])
    assert _jugada_elegida(obs, m.agent(obs)) == ("ATTACH", m.Teal_Mask_Ogerpon_ex), (
        "la 4a energia se permite cuando es la que HABILITA el KO del activo "
        "rival desde el Ogerpon activo")


def test_hop_cuarta_energia_vetada_si_el_ogerpon_ya_noquea():
    # Without the exception: the active Ogerpon ALREADY knocks out (30+30*(3+2 rival
    # energies) = 180 >= 140), so the 4th energy is surplus and goes to another attacker.
    obs = _esc_hop(pk(m.Teal_Mask_Ogerpon_ex, energias=[G, G, G], fisicas=3),
                   [pk(m.Tapu_Bulu, energias=[G, G, G], fisicas=3)],
                   op_energias=[G, G])
    tipo, destino = _jugada_elegida(obs, m.agent(obs))
    assert (tipo, destino) != ("ATTACH", m.Teal_Mask_Ogerpon_ex), (
        "si el Ogerpon activo ya noquea, la energia extra no habilita nada: "
        "el tope de Hop's la reserva para otro cuerpo")


def test_hop_teal_dance_respeta_el_tope():
    # Teal Dance also attaches: with 3 physical on the bench Ogerpon it is
    # vetoed (before it was used and left it at 4).
    obs = _esc_hop(pk(m.Dipplin, pre_evo=[m.Applin], energias=[G], fisicas=1),
                   [pk(m.Teal_Mask_Ogerpon_ex, energias=[G, G, G], fisicas=3)],
                   menu="teal")
    assert _jugada_elegida(obs, m.agent(obs))[0] != "ABILITY", (
        "Teal Dance sobre un Ogerpon de banca en su tope (3 fisicas vs Hop's) "
        "sobrecargaria: debe quedar vetada")


def test_hop_teal_dance_permitida_si_habilita_el_ko():
    # The ACTIVE's exception also holds for Teal Dance (it attaches + DRAWS).
    obs = _esc_hop(pk(m.Teal_Mask_Ogerpon_ex, energias=[G, G, G], fisicas=3),
                   [pk(m.Tapu_Bulu, energias=[G, G, G], fisicas=3)],
                   menu="teal")
    assert _jugada_elegida(obs, m.agent(obs))[0] == "ABILITY", (
        "con el Ogerpon activo a una energia del KO, Teal Dance es la jugada "
        "(adjunta la Planta y ademas roba)")


def test_hop_tope_2_energias_con_meganium():
    # With Meganium in play (Wild Growth doubles) the cap drops to 2 physical.
    obs = (Escenario(turno=8, paso=1, tac=1)
           .mi_activo(pk(m.Meganium, pre_evo=[m.Chikorita, m.Bayleef]))
           .mi_banca(pk(m.Teal_Mask_Ogerpon_ex, energias=[G, G, G, G], fisicas=2),
                     pk(m.Tapu_Bulu))
           .mi_mano(m.Basic_Grass_Energy)
           .op_activo(pk(TREVENANT, hp=140, max_hp=140))
           .op_zonas(mano=4, mazo=40, premios=4)
           .menu_attach_energia()
           .construir())
    tipo, destino = _jugada_elegida(obs, m.agent(obs))
    assert (tipo, destino) != ("ATTACH", m.Teal_Mask_Ogerpon_ex), (
        "con Meganium en juego 2 Plantas fisicas ya son 4 efectivas: el "
        "Ogerpon de banca esta en su tope")


def test_tope_base_por_matchup():
    # A matchup boundary: the cap of 3 physical belongs ONLY to Hop's; vs Alakazam
    # (the other matchup with a cap) the base is still 4 without Meganium.
    assert m._ogerpon_base_phys_cap(False, True) == 3
    assert m._ogerpon_base_phys_cap(True, True) == 2
    assert m._ogerpon_base_phys_cap(False, False) == 4
    assert m._ogerpon_base_phys_cap(True, False) == 2


# ---------------------------------------------------------------------
# The winning Myriad combo: Teal Dance -> Boss's Orders -> gust -> attack
# (user, registro_012 step 227 vs Iono, LOST; a SYNTHETIC scenario because
# the records are transient local data). At 2 prizes, with a Teal Mask
# Ogerpon ex active (4 energies), 1 Grass + Boss's in hand and an Iono's
# Bellibolt ex (280 HP, 4 energies) on the rival bench, the line WINS:
# Teal Dance leaves the Ogerpon at 5 -> Boss's brings up the Bellibolt ->
# Myriad = 30 + 30*(5+4) = 300 >= 280 -> a 2-prize KO.
# The block was twofold: Teal Dance vetoed ("it already has >=3 energies and already knocks out
# the rival active") and the manual attachment to the active vetoed by the PRECEDENCE of
# Teal Dance, so the energy ended up on a bench body.
# ---------------------------------------------------------------------
BELLIBOLT_EX = 269      # Iono's Bellibolt ex, 280 HP, 2 prizes
KILOWATTREL = 271       # Iono's Kilowattrel, 120 HP
MYRIAD_ATK = 120


def _esc_combo_myriad(energias=4, plantas=1, energia_jugada=False,
                      premios_propios=2):
    # `menu_teal_dance()` requires a Grass in hand (the ability attaches it
    # FROM the hand); for the later steps of the chain (`plantas=0`) it is
    # built with it and then moved to the discard, which is exactly where it ends up
    # after being used.
    obs = (Escenario(turno=12, paso=227, tac=1,
                     premios_propios=premios_propios,
                     energia_jugada=energia_jugada)
           .mi_activo(pk(m.Teal_Mask_Ogerpon_ex, energias=[G] * energias,
                         fisicas=energias))
           .mi_banca(pk(m.Applin))
           .mi_mano(m.Basic_Grass_Energy, m.Boss_Orders)
           .op_activo(pk(KILOWATTREL, hp=120, max_hp=120))
           .op_banca(pk(BELLIBOLT_EX, hp=280, max_hp=280,
                        energias=[G, G, G, G]))
           .op_zonas(mano=5, mazo=30, premios=3)
           .menu_teal_dance()
           .construir())
    if plantas == 0:
        me = obs["current"]["players"][obs["current"]["yourIndex"]]
        sobra = [c for c in me["hand"] if c["id"] == m.Basic_Grass_Energy]
        me["hand"] = [c for c in me["hand"] if c["id"] != m.Basic_Grass_Energy]
        me["handCount"] = len(me["hand"])
        me["discard"] = list(me["discard"]) + sobra
    return obs


def _menu_combo(obs, con_ability=True, con_attach=True):
    """A realistic MAIN menu: Teal Dance + PLAY Boss's + attachments + attack."""
    me = obs["current"]["players"][obs["current"]["yourIndex"]]
    i_boss = next(i for i, c in enumerate(me["hand"]) if c["id"] == m.Boss_Orders)
    i_e = next((i for i, c in enumerate(me["hand"])
                if c["id"] == m.Basic_Grass_Energy), None)
    ops = []
    if con_ability:
        ops.append({"type": int(m.OptionType.ABILITY),
                    "area": int(m.AreaType.ACTIVE), "index": 0})
    ops.append({"type": int(m.OptionType.PLAY), "index": i_boss})
    if con_attach and i_e is not None:
        for area, idx in ((int(m.AreaType.ACTIVE), 0), (int(m.AreaType.BENCH), 0)):
            ops.append({"type": int(m.OptionType.ATTACH), "area": 2, "index": i_e,
                        "inPlayArea": area, "inPlayIndex": idx})
    ops += [{"type": int(m.OptionType.ATTACK), "attackId": MYRIAD_ATK},
            {"type": int(m.OptionType.RETREAT)}, {"type": int(m.OptionType.END)}]
    obs["select"]["option"] = ops
    return obs


def _tipo_elegido(obs, eleccion):
    return int(obs["select"]["option"][eleccion[0]]["type"])


def test_combo_myriad_usa_teal_dance_para_el_remate():
    obs = _menu_combo(_esc_combo_myriad())
    assert _tipo_elegido(obs, m.agent(obs)) == int(m.OptionType.ABILITY), (
        "con un remate ganador via Boss's, la energia del turno va al Ogerpon "
        "ACTIVO por Teal Dance (adjunta y roba), no a un cuerpo de banca")


def test_combo_myriad_teal_dance_con_el_adjunte_ya_gastado():
    # The ability is INDEPENDENT of the manual attachment: even if the turn's energy
    # has already been played, Teal Dance still adds the 5th energy and the
    # finisher must be detected all the same (before, `_mbw_dmg_to` only modelled the +1 of the
    # attachment and the finisher was lost).
    obs = _menu_combo(_esc_combo_myriad(energia_jugada=True), con_attach=False)
    assert _tipo_elegido(obs, m.agent(obs)) == int(m.OptionType.ABILITY), (
        "con el adjunte manual gastado, Teal Dance sigue siendo la carga que "
        "habilita el remate ganador")


def test_combo_myriad_juega_boss_tras_teal_dance():
    # The second step of the chain: the Ogerpon already at 5 energies, with no Grass in hand.
    obs = _menu_combo(_esc_combo_myriad(energias=5, plantas=0),
                      con_ability=False, con_attach=False)
    assert _tipo_elegido(obs, m.agent(obs)) == int(m.OptionType.PLAY), (
        "con el Ogerpon ya cargado, la jugada es Boss's Orders para subir al "
        "objetivo de 2 premios, no atacar al activo rival")


def test_combo_myriad_gustea_el_bellibolt():
    # The third step: choosing the gust's target.
    obs = _esc_combo_myriad(energias=5, plantas=0)
    yo = obs["current"]["yourIndex"]
    obs["select"] = {
        "context": int(m.SelectContext.TO_ACTIVE), "type": 1,
        "minCount": 1, "maxCount": 1, "contextCard": None, "deck": None,
        "effect": None, "remainDamageCounter": 0, "remainEnergyCost": 0,
        "option": [{"area": 5, "index": 0, "playerIndex": 1 - yo, "type": 3}],
    }
    eleccion = m.agent(obs)
    rival = obs["current"]["players"][1 - yo]
    objetivo = rival["bench"][obs["select"]["option"][eleccion[0]]["index"]]["id"]
    assert objetivo == BELLIBOLT_EX, (
        f"el gusteo debe subir al Bellibolt ex (2 premios, letal con Myriad); "
        f"obtuvo {m.card_table[objetivo].name}")


def test_combo_myriad_sin_remate_no_gasta_la_planta():
    # Boundary: with no prize target on the rival bench (only a Kilowattrel
    # worth 1 prize that we already knock out), the no-overcharging veto returns: the
    # energy does NOT go to the active Ogerpon via Teal Dance.
    obs = (Escenario(turno=12, paso=227, tac=1, premios_propios=2)
           .mi_activo(pk(m.Teal_Mask_Ogerpon_ex, energias=[G] * 4, fisicas=4))
           .mi_banca(pk(m.Applin))
           .mi_mano(m.Basic_Grass_Energy, m.Boss_Orders)
           .op_activo(pk(KILOWATTREL, hp=120, max_hp=120))
           .op_banca(pk(KILOWATTREL, hp=120, max_hp=120))
           .op_zonas(mano=5, mazo=30, premios=3)
           .menu_teal_dance()
           .construir())
    obs = _menu_combo(obs)
    assert _tipo_elegido(obs, m.agent(obs)) != int(m.OptionType.ABILITY), (
        "sin remate de premios via Boss's, el Ogerpon con 4 energias que ya "
        "noquea no gasta otra Planta en Teal Dance")


# ---------------------------------------------------------------------
# The Ogerpon retreat->KO pivot, an END-TO-END validation (user, log 86583929
# turn 4 vs Alakazam; the memory ogerpon-retreat-ko-pivot). The rule spans
# SEVERAL chained decisions and only the RETREAT had been verified in isolation.
# Here the whole chain is walked with simulated transitions: a stalled active
# Fezandipiti ex (1 energy, its attack asks for 3) + a bench Ogerpon ex
# at 2 energies which with Teal Dance's Grass reaches 3 and KNOCKS OUT the
# rival active Abra (Myriad 30+30*3=120 >= 50).
#   Case A (Grass in HAND):     TD bench -> RETREAT -> promote Ogerpon -> ATTACK
#   Case B (Grass in DISCARD):  NS -> recover -> TD bench -> RETREAT ->
#                               promote Ogerpon -> ATTACK
#   Case C (no reachable Grass): it does not waste the retreat (END).
# ---------------------------------------------------------------------
import copy

ABRA_ALAKAZAM = 741     # an Abra of the Alakazam line (50 HP)
KADABRA_ALK = 742


def _pivote_obs(caso):
    esc = (Escenario(turno=6, paso=40, tac=1)
           .mi_activo(pk(m.Fezandipiti_ex, energias=[G], fisicas=1))
           .mi_banca(pk(m.Teal_Mask_Ogerpon_ex, energias=[G, G], fisicas=2),
                     pk(m.Applin)))
    if caso == "A":
        esc = esc.mi_mano(m.Basic_Grass_Energy)
    else:
        esc = esc.mi_mano(m.Night_Stretcher, m.Basic_Grass_Energy)
    obs = (esc
           .op_activo(pk(ABRA_ALAKAZAM, hp=50, max_hp=50))
           .op_banca(pk(KADABRA_ALK, hp=80, max_hp=80))
           .op_zonas(mano=5, mazo=34, premios=6)
           .menu_teal_dance()  # the walker regenerates the menu at each step
           .construir())
    yo = obs["current"]["players"][0]
    if caso in ("B", "C"):
        # the Grass was built in hand (a builder requirement); in the
        # real scenario it is in the DISCARD (case B) or does not exist (case C)
        planta = next(c for c in yo["hand"] if c["id"] == m.Basic_Grass_Energy)
        yo["hand"] = [c for c in yo["hand"] if c is not planta]
        yo["discard"] = list(yo["discard"]) + [planta]
    if caso == "C":
        yo["hand"] = [c for c in yo["hand"] if c["id"] != m.Night_Stretcher]
        yo["discard"] = [c for c in yo["discard"]
                         if c["id"] != m.Basic_Grass_Energy]
    yo["handCount"] = len(yo["hand"])
    return obs


def _pivote_menu_main(obs):
    """A realistic MAIN menu for the current state (regenerated at each step)."""
    yo = obs["current"]["players"][0]
    ops = []
    if any(c["id"] == m.Basic_Grass_Energy for c in yo["hand"]):
        if yo["active"][0]["id"] == m.Teal_Mask_Ogerpon_ex:
            ops.append({"type": 10, "area": 4, "index": 0})
        for k, bp in enumerate(yo["bench"]):
            if bp["id"] == m.Teal_Mask_Ogerpon_ex:
                ops.append({"type": 10, "area": 5, "index": k})
        if not obs["current"]["energyAttached"]:
            i_e = next(i for i, c in enumerate(yo["hand"])
                       if c["id"] == m.Basic_Grass_Energy)
            ops.append({"type": 8, "area": 2, "index": i_e,
                        "inPlayArea": 4, "inPlayIndex": 0})
            for k in range(len(yo["bench"])):
                ops.append({"type": 8, "area": 2, "index": i_e,
                            "inPlayArea": 5, "inPlayIndex": k})
    for i, c in enumerate(yo["hand"]):
        if c["id"] == m.Night_Stretcher:
            ops.append({"type": 7, "index": i})
    act = yo["active"][0]
    if act["id"] == m.Teal_Mask_Ogerpon_ex and len(act["energies"]) >= 3:
        ops.append({"type": 13, "attackId": 120})
    if len(act["energies"]) >= 1 and not obs["current"]["retreated"]:
        ops.append({"type": 12})
    ops.append({"type": 14})
    obs["select"] = {"context": 0, "type": 0, "minCount": 1, "maxCount": 1,
                     "contextCard": None, "deck": None, "effect": None,
                     "remainDamageCounter": 0, "remainEnergyCost": 0,
                     "option": ops}
    return obs


def _pivote_caminar(obs, max_pasos=10):
    """Runs the chain; returns the list of labels of the decisions."""
    obs = _pivote_menu_main(copy.deepcopy(obs))
    pasos = []
    for _ in range(max_pasos):
        r = m.agent(obs)
        o = obs["select"]["option"][r[0]]
        t = int(o["type"])
        cur = obs["current"]
        yo = cur["players"][0]
        regen = True
        if t == 12:                                   # RETREAT + promotion
            act = yo["active"][0]
            yo["discard"] = list(yo["discard"]) + [act["energyCards"].pop()]
            act["energies"] = act["energies"][:-1]
            cur["retreated"] = True
            pasos.append("RETREAT")
            obs["select"] = {"context": int(m.SelectContext.SWITCH), "type": 1,
                             "minCount": 1, "maxCount": 1, "contextCard": None,
                             "deck": None, "effect": None,
                             "remainDamageCounter": 0, "remainEnergyCost": 0,
                             "option": [{"area": 5, "index": k,
                                         "playerIndex": 0, "type": 3}
                                        for k in range(len(yo["bench"]))]}
            regen = False
        elif t == 3 and obs["select"]["context"] == int(m.SelectContext.SWITCH):
            k = o["index"]
            nuevo, anterior = yo["bench"][k], yo["active"][0]
            yo["active"] = [nuevo]
            yo["bench"] = ([bp for i, bp in enumerate(yo["bench"]) if i != k]
                           + [anterior])
            pasos.append(f"PROMUEVE {m.card_table[nuevo['id']].name}")
        elif t == 7:                                  # PLAY Night Stretcher
            carta = yo["hand"][o["index"]]
            yo["hand"] = [c for i, c in enumerate(yo["hand"])
                          if i != o["index"]]
            yo["discard"] = list(yo["discard"]) + [carta]
            yo["handCount"] = len(yo["hand"])
            pasos.append("PLAY NS")
            cands = [i for i, c in enumerate(yo["discard"])
                     if c["id"] == m.Basic_Grass_Energy]
            obs["select"] = {"context": int(m.SelectContext.TO_HAND), "type": 1,
                             "minCount": 1, "maxCount": 1, "contextCard": None,
                             "deck": None,
                             "effect": {"id": m.Night_Stretcher,
                                        "playerIndex": 0, "serial": 999},
                             "remainDamageCounter": 0, "remainEnergyCost": 0,
                             "option": [{"area": 3, "index": i,
                                         "playerIndex": 0, "type": 3}
                                        for i in cands]}
            regen = False
        elif t == 3 and obs["select"]["context"] == int(m.SelectContext.TO_HAND):
            carta = yo["discard"][o["index"]]
            yo["discard"] = [c for j, c in enumerate(yo["discard"])
                             if j != o["index"]]
            yo["hand"] = list(yo["hand"]) + [carta]
            yo["handCount"] = len(yo["hand"])
            pasos.append(f"RECUPERA {m.card_table[carta['id']].name}")
        elif t == 10:                                 # Teal Dance
            i_e = next(i for i, c in enumerate(yo["hand"])
                       if c["id"] == m.Basic_Grass_Energy)
            e_card = yo["hand"][i_e]
            yo["hand"] = [c for i, c in enumerate(yo["hand"]) if i != i_e]
            yo["handCount"] = len(yo["hand"])
            tgt = (yo["active"][0] if o["area"] == 4
                   else yo["bench"][o["index"]])
            tgt["energies"] = list(tgt["energies"]) + [int(G)]
            tgt["energyCards"] = list(tgt["energyCards"]) + [e_card]
            pasos.append("TEAL DANCE")
        elif t == 8:                                  # a manual attachment
            e_card = yo["hand"][o["index"]]
            yo["hand"] = [c for i, c in enumerate(yo["hand"])
                          if i != o["index"]]
            yo["handCount"] = len(yo["hand"])
            tgt = (yo["active"][0] if o["inPlayArea"] == 4
                   else yo["bench"][o["inPlayIndex"]])
            tgt["energies"] = list(tgt["energies"]) + [int(G)]
            tgt["energyCards"] = list(tgt["energyCards"]) + [e_card]
            cur["energyAttached"] = True
            pasos.append("ATTACH")
        elif t == 13:
            pasos.append("ATTACK")
            return pasos, obs
        else:
            pasos.append("END")
            return pasos, obs
        if regen:
            obs = _pivote_menu_main(obs)
    raise AssertionError(f"cadena sin cierre: {pasos}")


def _pivote_asserts_ko(pasos, obs):
    assert pasos[-1] == "ATTACK", pasos
    act = obs["current"]["players"][0]["active"][0]
    opa = obs["current"]["players"][1]["active"][0]
    assert act["id"] == m.Teal_Mask_Ogerpon_ex and len(act["energies"]) >= 3
    dmg = 30 + 30 * (len(act["energies"]) + len(opa["energies"]))
    assert dmg >= opa["hp"], (dmg, opa["hp"])


def test_pivote_ogerpon_retreat_ko_planta_en_mano():
    pasos, obs = _pivote_caminar(_pivote_obs("A"))
    assert pasos == ["TEAL DANCE", "RETREAT",
                     "PROMUEVE Teal Mask Ogerpon ex", "ATTACK"], pasos
    _pivote_asserts_ko(pasos, obs)


def test_pivote_ogerpon_retreat_ko_planta_via_night_stretcher():
    pasos, obs = _pivote_caminar(_pivote_obs("B"))
    assert pasos == ["PLAY NS", "RECUPERA Basic {G} Energy", "TEAL DANCE",
                     "RETREAT", "PROMUEVE Teal Mask Ogerpon ex",
                     "ATTACK"], pasos
    _pivote_asserts_ko(pasos, obs)


def test_pivote_ogerpon_sin_planta_no_malgasta_el_retiro():
    pasos, _ = _pivote_caminar(_pivote_obs("C"))
    assert pasos == ["END"], (
        f"sin Planta alcanzable el pivote no dispara: retirar solo pagaria "
        f"una energia para subir un Ogerpon que no ataca; obtuvo {pasos}")


# ---------------------------------------------------------------------
# Detecting the Cornerstone archetype by the NON-ex (386) and by the DISCARD
# (phase 8: the autopsy vs the synthetic cornerstone_cubchoo deck showed 112
# sterile turns across 35 losses; with only Cubchoo/Beartic in sight the
# `op_is_cornerstone_deck` flag did not fire and the anti-Cubchoo whitelist
# vetoed PLAY Tapu Bulu -- the matchup's win condition -- 38 times).
# ---------------------------------------------------------------------
CORNERSTONE_NOEX = 386


def _menu_con_tapu(op_activo, op_banca=(), op_descarte=()):
    esc = (Escenario(turno=6, paso=1, tac=1)
           .mi_activo(pk(m.Teal_Mask_Ogerpon_ex, energias=[G], fisicas=1))
           .mi_banca(pk(m.Chikorita))
           .mi_mano(m.Tapu_Bulu, m.Basic_Grass_Energy)
           .op_activo(pk(op_activo, hp=70, max_hp=70)))
    if op_banca:
        esc = esc.op_banca(*[pk(b) for b in op_banca])
    if op_descarte:
        esc = esc.op_descarte(*op_descarte)
    # menu_attach_energia() gives the builder's minimal select; it is replaced
    # below by the PLAY menu that exercises the whitelist.
    obs = (esc.op_zonas(mano=4, mazo=38, premios=6)
           .menu_attach_energia().construir())
    yo = obs["current"]["players"][0]
    i_tapu = next(i for i, c in enumerate(yo["hand"])
                  if c["id"] == m.Tapu_Bulu)
    obs["select"] = {"context": int(m.SelectContext.MAIN), "type": 0,
                     "minCount": 1, "maxCount": 1, "contextCard": None,
                     "deck": None, "effect": None, "remainDamageCounter": 0,
                     "remainEnergyCost": 0,
                     "option": [{"type": int(m.OptionType.PLAY),
                                 "index": i_tapu},
                                {"type": int(m.OptionType.END)}]}
    return obs


def test_cornerstone_noex_en_banca_permite_tapu():
    # The non-ex 386 does not make anything immune (it has no ability) but it gives the archetype away: the
    # anti-Cubchoo whitelist must be extended with Tapu Bulu.
    obs = _menu_con_tapu(CUBCHOO, op_banca=(CORNERSTONE_NOEX,))
    r = m.agent(obs)
    assert obs["select"]["option"][r[0]]["type"] == int(m.OptionType.PLAY), (
        "con un Cornerstone no-ex en la banca rival, Tapu Bulu (la win "
        "condition del matchup) debe poder bajarse")


def test_cornerstone_en_descarte_permite_tapu():
    # Seeing it in the DISCARD also identifies the deck (a PLAN flag; the
    # positional op_has_ability_immune_active is still tied to the board).
    obs = _menu_con_tapu(CUBCHOO, op_descarte=(CORNERSTONE_NOEX,))
    r = m.agent(obs)
    assert obs["select"]["option"][r[0]]["type"] == int(m.OptionType.PLAY), (
        "con un Cornerstone en el descarte rival, el plan del matchup "
        "cambia y Tapu Bulu debe poder bajarse")


def test_cubchoo_puro_sigue_vetando_tapu():
    # Boundary: with no trace of Cornerstone, the user's anti-Cubchoo plan
    # is left INTACT (Tapu Bulu is not played vs the pure Cubchoo deck).
    obs = _menu_con_tapu(CUBCHOO, op_banca=(CUBCHOO,))
    r = m.agent(obs)
    assert obs["select"]["option"][r[0]]["type"] == int(m.OptionType.END), (
        "vs Cubchoo puro la whitelist del usuario excluye a Tapu Bulu")


# ---------------------------------------------------------------------
# Strategy vs Raging Bolt ex: PRIZE MISMATCH (user, registro_002
# step 27 vs Raging Bolt/Ogerpon, LOST). Their whole deck is 2-prize ex and
# Bellowing Thunder knocks out any of our ex in one blow: if
# our active ex canNOT knock out, a 1-prize body is played (Tapu
# Bulu), the ex is retreated and the 1-prize one is put in front — the rival KO pays 1
# prize and not 2. The real chain of step 27, walked with transitions.
# ---------------------------------------------------------------------

def _raging_obs(tapu_en_banca=False, ogerpon_cargado=False, bolt_hp=240):
    act = pk(m.Teal_Mask_Ogerpon_ex,
             energias=[G] * (4 if ogerpon_cargado else 1),
             fisicas=(4 if ogerpon_cargado else 1))
    banca = [pk(m.Teal_Mask_Ogerpon_ex, energias=[G, G], fisicas=2),
             pk(m.Meowth_ex)]
    mano = [m.Forest_of_Vitality, m.Dawn, m.Xerosic_Machinations,
            m.Meganium, m.Basic_Grass_Energy, m.Forest_of_Vitality]
    if tapu_en_banca:
        banca.append(pk(m.Tapu_Bulu, aparecio=True))
    else:
        mano.insert(4, m.Tapu_Bulu)
    return (Escenario(turno=2, paso=27, tac=14, primer_jugador=0,
                      energia_jugada=True, partidario_jugado=True)
            .mi_activo(act)
            .mi_banca(*banca)
            .mi_mano(*mano)
            .mi_descarte(m.Night_Stretcher, m.Forest_of_Vitality,
                         m.Ultra_Ball, m.Lillie_Determination)
            .op_activo(pk(m.Raging_Bolt_ex, hp=bolt_hp, max_hp=240))
            .op_banca(pk(m.Teal_Mask_Ogerpon_ex, energias=[G], fisicas=1),
                      pk(m.Teal_Mask_Ogerpon_ex, energias=[G], fisicas=1),
                      pk(m.Teal_Mask_Ogerpon_ex))
            .op_zonas(mano=2, mazo=44, premios=6)
            .menu_teal_dance()   # the walker regenerates the menu at each step
            .construir())


def _raging_menu(obs):
    yo = obs["current"]["players"][0]
    act = yo["active"][0]
    ops = []
    for i, c in enumerate(yo["hand"]):
        if c["id"] in (m.Forest_of_Vitality, m.Tapu_Bulu):
            if (c["id"] == m.Forest_of_Vitality
                    and (obs["current"]["stadiumPlayed"]
                         or obs["current"]["stadium"])):
                continue
            ops.append({"type": int(m.OptionType.PLAY), "index": i})
    if (act["id"] == m.Teal_Mask_Ogerpon_ex
            and len(act["energies"]) >= 3):
        ops.append({"type": int(m.OptionType.ATTACK), "attackId": 120})
    if len(act["energies"]) >= 1 and not obs["current"]["retreated"]:
        ops.append({"type": int(m.OptionType.RETREAT)})
    ops.append({"type": int(m.OptionType.END)})
    obs["select"] = {"context": int(m.SelectContext.MAIN), "type": 0,
                     "minCount": 1, "maxCount": 1, "contextCard": None,
                     "deck": None, "effect": None, "remainDamageCounter": 0,
                     "remainEnergyCost": 0, "option": ops}
    return obs


def _raging_caminar(obs, max_pasos=10):
    pasos = []
    obs = _raging_menu(copy.deepcopy(obs))
    for _ in range(max_pasos):
        r = m.agent(obs)
        o = obs["select"]["option"][r[0]]
        t = int(o["type"])
        yo = obs["current"]["players"][0]
        if t == int(m.OptionType.PLAY):
            carta = yo["hand"][o["index"]]
            yo["hand"] = [c for i, c in enumerate(yo["hand"])
                          if i != o["index"]]
            yo["handCount"] = len(yo["hand"])
            if carta["id"] == m.Forest_of_Vitality:
                obs["current"]["stadium"] = [carta]
                obs["current"]["stadiumPlayed"] = True
                pasos.append("FOREST")
            else:
                d = m.card_table[carta["id"]]
                yo["bench"] = list(yo["bench"]) + [
                    {"id": carta["id"], "serial": carta["serial"],
                     "playerIndex": 0, "hp": d.hp, "maxHp": d.hp,
                     "appearThisTurn": True, "energies": [],
                     "energyCards": [], "tools": [], "preEvolution": []}]
                pasos.append(f"BAJA {d.name}")
        elif t == int(m.OptionType.RETREAT):
            act = yo["active"][0]
            yo["discard"] = list(yo["discard"]) + [act["energyCards"].pop()]
            act["energies"] = act["energies"][:-1]
            obs["current"]["retreated"] = True
            pasos.append("RETREAT")
            obs["select"] = {"context": int(m.SelectContext.SWITCH),
                             "type": 1, "minCount": 1, "maxCount": 1,
                             "contextCard": None, "deck": None,
                             "effect": None, "remainDamageCounter": 0,
                             "remainEnergyCost": 0,
                             "option": [{"area": 5, "index": k,
                                         "playerIndex": 0, "type": 3}
                                        for k in range(len(yo["bench"]))]}
            r2 = m.agent(obs)
            k = obs["select"]["option"][r2[0]]["index"]
            nuevo = yo["bench"][k]
            yo["bench"] = [b for i, b in enumerate(yo["bench"])
                           if i != k] + [act]
            yo["active"] = [nuevo]
            pasos.append(f"PROMUEVE {m.card_table[nuevo['id']].name}")
        else:
            pasos.append("ATTACK" if t == int(m.OptionType.ATTACK) else "END")
            break
        obs = _raging_menu(obs)
    return pasos, obs["current"]["players"][0]["active"][0]


def test_raging_bolt_descuadre_cadena_completa():
    pasos, activo_final = _raging_caminar(_raging_obs())
    assert "BAJA Tapu Bulu" in pasos and "RETREAT" in pasos, pasos
    assert "PROMUEVE Tapu Bulu" in pasos, pasos
    assert activo_final["id"] == m.Tapu_Bulu, (
        f"vs Raging Bolt (todo ex de 2 premios), el turno debe terminar con "
        f"un cuerpo de 1 premio delante; termino {activo_final['id']}: {pasos}")


def test_raging_bolt_con_1premio_en_banca_no_baja_otro_y_retira():
    # With the Tapu ALREADY on the bench there is no need to play another body: the chain goes
    # straight to retreating and promoting it.
    pasos, activo_final = _raging_caminar(_raging_obs(tapu_en_banca=True))
    assert "RETREAT" in pasos and "PROMUEVE Tapu Bulu" in pasos, pasos
    assert not any(p.startswith("BAJA") for p in pasos), pasos
    assert activo_final["id"] == m.Tapu_Bulu, pasos


def test_raging_bolt_con_ko_disponible_no_sacrifica():
    # Boundary: the charged active Ogerpon KNOCKS OUT the damaged Bolt (Myriad
    # 30+30*4=150 >= 120): we attack, we do not give away the mismatch's tempo.
    pasos, activo_final = _raging_caminar(
        _raging_obs(ogerpon_cargado=True, bolt_hp=120))
    assert "RETREAT" not in pasos, pasos
    assert pasos[-1] == "ATTACK", pasos
    assert activo_final["id"] == m.Teal_Mask_Ogerpon_ex, pasos


# ---------------------------------------------------------------------
# Strategy vs Mega Abomasnow ex: PRIZE MISMATCH (user, registro_002
# step 14 and registro_004 step 17, vs Snover -> Mega Abomasnow ex). Their line
# one-shots any of our ex; with two Ogerpon ex in play and unable
# to knock out the active (an Ogerpon with 1 energy, Myriad costs 3), the correct
# line is to play a 1-prize body (Tapu Bulu) and put it in front.
# EXCEPTION (user): the rule does NOT apply on our first turn going
# FIRST -- the rival cannot knock us out on their next turn yet.
# ---------------------------------------------------------------------

def _abomasnow_obs(primer_jugador=1, turno=2, tapu_en_banca=False):
    # An active Ogerpon ex with a single energy: it canNOT use Myriad Leaf Shower
    # (it costs 3) => it does not knock out the Snover => the mismatch fires.
    act = pk(m.Teal_Mask_Ogerpon_ex, energias=[G], fisicas=1)
    banca = [pk(m.Teal_Mask_Ogerpon_ex, energias=[G, G], fisicas=2),
             pk(m.Meowth_ex)]
    mano = [m.Forest_of_Vitality, m.Dawn, m.Xerosic_Machinations,
            m.Meganium, m.Basic_Grass_Energy, m.Forest_of_Vitality]
    if tapu_en_banca:
        banca.append(pk(m.Tapu_Bulu, aparecio=True))
    else:
        mano.insert(4, m.Tapu_Bulu)
    return (Escenario(turno=turno, paso=14, tac=7, primer_jugador=primer_jugador,
                      energia_jugada=True, partidario_jugado=True)
            .mi_activo(act)
            .mi_banca(*banca)
            .mi_mano(*mano)
            .op_activo(pk(m.Snover))
            .op_banca(pk(m.Snover))
            .op_zonas(mano=5, mazo=41, premios=6)
            .menu_teal_dance()   # the walker regenerates the menu at each step
            .construir())


def test_abomasnow_descuadre_cadena_completa():
    # Going SECOND (our first turn is turn 2), the rule applies:
    # play Tapu Bulu, retreat the Ogerpon ex and put it in front.
    pasos, activo_final = _raging_caminar(_abomasnow_obs())
    assert "BAJA Tapu Bulu" in pasos and "RETREAT" in pasos, pasos
    assert "PROMUEVE Tapu Bulu" in pasos, pasos
    assert activo_final["id"] == m.Tapu_Bulu, (
        f"vs Mega Abomasnow ex, sin poder noquear, el turno debe terminar con "
        f"un cuerpo de 1 premio delante; termino {activo_final['id']}: {pasos}")


def test_abomasnow_primer_turno_primeros_no_sacrifica():
    # EXCEPTION (user): on OUR first turn going FIRST the rule does NOT
    # apply -- the rival cannot knock us out on their next turn yet, early
    # development is not sacrificed. The ex is not retreated.
    pasos, activo_final = _raging_caminar(
        _abomasnow_obs(primer_jugador=0, turno=1))
    assert "RETREAT" not in pasos, pasos
    assert activo_final["id"] == m.Teal_Mask_Ogerpon_ex, (
        f"primer turno partiendo primeros: el descuadre no aplica; "
        f"termino {activo_final['id']}: {pasos}")


def test_abomasnow_primeros_pero_turno_posterior_si_sacrifica():
    # The exception's boundary: the exception belongs ONLY to turn 1. Going
    # first but on a later turn (turn 3) the rule applies again.
    pasos, activo_final = _raging_caminar(
        _abomasnow_obs(primer_jugador=0, turno=3))
    assert "RETREAT" in pasos and activo_final["id"] == m.Tapu_Bulu, pasos


# ---------------------------------------------------------------------
# An IMMUNE rival active -> the Boss's engine to gust the bench (user).
# Scenario: an active Hydrapple ex (it can do 330) vs an active Cornerstone Mask Ogerpon ex
# (it cancels our Pokemon WITH an ability -> attacking it = 0 damage) with a
# Mega Lucario ex on the rival bench, and a Meowth ex in hand. The correct play
# is NOT to attack the Cornerstone (0), but to play Meowth ex so that Last-Ditch
# Catch searches for a Boss's Orders (in the deck), gust the Mega Lucario and attack it.
# ---------------------------------------------------------------------
MEGA_LUCARIO = 678


def _menu_inmune_activo(op_activo_id, op_banca_id):
    esc = (Escenario(turno=8, paso=100, tac=0,
                     partidario_jugado=False, estadio_jugado=True,
                     premios_propios=4)
           .mi_activo(pk(m.Hydrapple_ex, energias=[G, G, G, G], fisicas=4))
           .mi_banca(pk(m.Teal_Mask_Ogerpon_ex, energias=[G, G, G, G], fisicas=4),
                     pk(m.Teal_Mask_Ogerpon_ex, energias=[G, G, G], fisicas=3))
           .mi_mano(m.Meowth_ex)
           .op_activo(pk(op_activo_id, energias=[C], fisicas=1))
           .op_banca(pk(op_banca_id, energias=[], fisicas=0))
           .op_zonas(mano=5, mazo=28, premios=4))
    esc._select = {
        "context": int(m.SelectContext.MAIN), "contextCard": None, "deck": None,
        "effect": None, "maxCount": 1, "minCount": 1,
        "option": [
            {"index": 0, "type": 7},          # PLAY Meowth ex
            {"attackId": 195, "type": 13},    # ATTACK Hydrapple Syrup Storm
            {"type": 14},                     # END
        ],
        "remainDamageCounter": 0, "remainEnergyCost": 0, "type": 0,
    }
    return esc.construir()


def test_activo_inmune_juega_meowth_para_gustear_banca():
    obs = _menu_inmune_activo(CORNERSTONE, MEGA_LUCARIO)
    m._init_cartas_tracking()
    m.plan = m.AttackPlan()
    dec = m.agent(obs)
    tipo = obs["select"]["option"][dec[0]]["type"]
    assert tipo == int(m.OptionType.PLAY), (
        f"con el activo rival INMUNE (Cornerstone) y un Mega Lucario gusteable "
        f"en banca, debe JUGAR Meowth ex (motor Boss's), no atacar al muro por "
        f"0; eligio tipo {tipo}")


def test_activo_atacable_no_desvia_a_meowth():
    # Boundary: if the rival active is NOT immune (an active Mega Lucario ex, without
    # the Cornerstone ability), `_meowth_immune_boss_engine` does NOT apply -- the
    # Hydrapple ex DOES hit it (330), so the agent ATTACKS instead of detouring
    # into playing Meowth ex through the immunity engine's route.
    obs = _menu_inmune_activo(MEGA_LUCARIO, CORNERSTONE)
    m._init_cartas_tracking()
    m.plan = m.AttackPlan()
    dec = m.agent(obs)
    tipo = obs["select"]["option"][dec[0]]["type"]
    assert tipo == int(m.OptionType.ATTACK), (
        f"con el activo rival ATACABLE (Mega Lucario), Hydrapple ex debe ATACAR "
        f"(330), no desviarse al motor Meowth-inmune; eligio tipo {tipo}")


# ---------------------------------------------------------------------
# Iron Thorns ex ("Initialization") in the rival ACTIVE spot switches off the abilities
# of the Pokemon with a Rule Box on BOTH sides (plan Jul 2026, P1.4). The agent
# must not plan around Last-Ditch Catch: with Iron Thorns in front,
# searching for Meowth ex "for the Supporter fetch" is a dead card -- the same
# treatment as Team Rocket's Watchtower (`meowth_ability_lock`).
# ---------------------------------------------------------------------

def _fetch_ub_motor_meowth_vs(op_id):
    """A UB with an empty hand and the refresh engine available in the deck."""
    obs = (Escenario(turno=6, paso=1, tac=1)
           .mi_activo(pk(m.Teal_Mask_Ogerpon_ex, energias=[G], fisicas=1))
           .mi_banca(pk(m.Chikorita))
           .mi_mano()
           .op_activo(pk(op_id, hp=230, max_hp=230))
           .op_zonas(mano=4, mazo=40, premios=6)
           .mazo(m.Meowth_ex, m.Lillie_Determination, m.Tapu_Bulu,
                 m.Hydrapple_ex, m.Applin, m.Chikorita)
           .fetch_ultra_ball()
           .resto_al_descarte()
           .construir())
    eleccion = m.agent(obs)
    sel = obs["select"]
    return sel["deck"][sel["option"][eleccion[0]]["index"]]["id"]


def test_iron_thorns_activo_veta_fetch_de_meowth():
    elegida = _fetch_ub_motor_meowth_vs(m.Iron_Thorns_ex)
    assert elegida != m.Meowth_ex, (
        "con Iron Thorns ex de activo rival (Initialization anula Last-Ditch "
        "Catch), Ultra Ball no debe buscar Meowth ex para el motor de "
        f"Supporter; obtuvo {m.card_table[elegida].name}")


def test_sin_iron_thorns_el_motor_meowth_sigue_vivo():
    # Boundary: with a neutral rival active (Snorunt) the same scenario DOES
    # search for Meowth ex (the Last-Ditch -> Lillie's refresh engine).
    elegida = _fetch_ub_motor_meowth_vs(103)  # Snorunt
    assert elegida == m.Meowth_ex, (
        f"sin lock de habilidades el fetch del motor no debe cambiar; obtuvo "
        f"{m.card_table[elegida].name}")


# =====================================================================
# The FIRST-turn UB engine going SECOND (user, Jul 2026): the ONLY
# reason to play an Ultra Ball on our first action turn going
# second (outside an empty bench / a Budew rival active) is to SEARCH FOR MEOWTH EX
# when we do NOT have a Lillie's Determination and need to play one
# (Last-Ditch Catch brings it from the deck). Gate `_ub_ft_case2`. These tests
# pin the full contract after the gates of the anti-sterile-turn net
# (a7df1ce / 57db985), which use another route (score 200) and must not affect it.
# =====================================================================

def _escenario_t2_saliendo_segundo(mano):
    return (Escenario(turno=2, tac=1, primer_jugador=1)
            .mi_activo(pk(m.Tapu_Bulu))
            .mi_banca(pk(m.Chikorita))
            .mi_mano(*mano)
            .op_activo(pk(103, hp=60, max_hp=60))
            .op_zonas(mano=6, mazo=40, premios=6)
            .mazo(m.Meowth_ex, m.Lillie_Determination, m.Tapu_Bulu,
                  m.Hydrapple_ex, m.Applin, m.Teal_Mask_Ogerpon_ex)
            .fetch_ultra_ball()
            .resto_al_descarte()
            .construir())


def _menu_main(obs, opciones):
    obs["select"] = {"context": 0, "contextCard": None, "deck": None,
                     "effect": None, "maxCount": 1, "minCount": 1, "type": 0,
                     "remainDamageCounter": 0, "remainEnergyCost": 0,
                     "option": opciones}
    return obs


def test_ub_t1_segundos_sin_lillie_busca_el_motor_meowth():
    # With neither Lillie's NOR Meowth in hand, with both in the DECK: the first-turn
    # UB going second IS played (the Last-Ditch -> Lillie's engine).
    obs = _menu_main(
        _escenario_t2_saliendo_segundo([m.Ultra_Ball, m.Basic_Grass_Energy,
                                        m.Chikorita]),
        [{"index": 0, "type": 7}, {"index": 2, "type": 7}, {"type": 14}])
    eleccion = m.agent(obs)
    opt = obs["select"]["option"][eleccion[0]]
    assert opt.get("type") == 7 and opt.get("index") == 0, (
        f"la UB del motor Meowth->Lillie's debe jugarse en t2 saliendo "
        f"segundos sin Lillie's en mano; obtuvo {opt}")


def test_ub_t1_segundos_fetch_elige_meowth():
    obs = _escenario_t2_saliendo_segundo([m.Basic_Grass_Energy, m.Chikorita])
    eleccion = m.agent(obs)
    sel = obs["select"]
    elegida = sel["deck"][sel["option"][eleccion[0]]["index"]]["id"]
    assert elegida == m.Meowth_ex, (
        f"el fetch de la UB de primer turno debe traer Meowth ex (motor de "
        f"Lillie's); obtuvo {m.card_table[elegida].name}")


def test_ub_t1_segundos_con_lillie_en_mano_se_veta():
    # Control: with the Lillie's ALREADY in hand the engine is not needed and the first-turn
    # UB is vetoed again (the Lillie's is played).
    obs = _menu_main(
        _escenario_t2_saliendo_segundo([m.Ultra_Ball, m.Lillie_Determination,
                                        m.Basic_Grass_Energy]),
        [{"index": 0, "type": 7}, {"index": 1, "type": 7}, {"type": 14}])
    eleccion = m.agent(obs)
    opt = obs["select"]["option"][eleccion[0]]
    assert opt.get("type") == 7 and opt.get("index") == 1, (
        f"con Lillie's en mano se juega la Lillie's y la UB queda vetada; "
        f"obtuvo {opt}")


# ---------------------------------------------------------------------------
# The Teal Dance cap on Ogerpon EXTENDED to Cornerstone (autopsy v2.1 p025
# t20, Jul 2026 cycle). Cornerstone Stance cancels the damage of our Pokemon
# WITH an ability: the Ogerpon does not attack in that matchup and overcharging it via Teal
# Dance starves Tapu Bulu (THE attacker). The same extension pattern
# as d801d57 (the anti-Cubchoo whitelist extended with the immune wall in play).

def _esc_corner_td(ogerpon_fisicas):
    return (Escenario(turno=8, paso=1, tac=1)
            .mi_activo(pk(m.Tapu_Bulu, energias=[G], fisicas=1))
            .mi_banca(pk(m.Teal_Mask_Ogerpon_ex,
                         energias=[G] * ogerpon_fisicas,
                         fisicas=ogerpon_fisicas))
            .mi_mano(m.Basic_Grass_Energy)
            .op_activo(pk(117, hp=210, max_hp=210))   # Cornerstone Mask O. ex
            .op_zonas(mano=4, mazo=40, premios=4)
            .menu_teal_dance()
            .construir())


def test_cornerstone_td_tope_2_fisicas_redirige_a_tapu():
    # A bench Ogerpon ALREADY with 2 physical: Teal Dance vetoed; the Grass from
    # hand goes to Tapu Bulu (the cornerstone->Tapu +22000 energy_score rule
    # finally gets the energy).
    obs = _esc_corner_td(ogerpon_fisicas=2)
    tipo, destino = _jugada_elegida(obs, m.agent(obs))
    assert (tipo, destino) == ("ATTACH", m.Tapu_Bulu), (
        f"vs Cornerstone un Ogerpon con 2 fisicas esta en su tope: la energia "
        f"va a Tapu Bulu; obtuvo {(tipo, destino)}")


def test_cornerstone_td_una_fisica_sigue_permitida():
    # The cap's boundary: with 1 physical the Ogerpon does not reach the cap yet. The
    # Teal Dance is not VETOED (it may lose against other charges on score,
    # but the cap does not kill it): we check that the veto does not fire by looking
    # at the fact that the choice is NOT END and that if a charge wins, it is legitimate.
    obs = _esc_corner_td(ogerpon_fisicas=1)
    tipo, destino = _jugada_elegida(obs, m.agent(obs))
    assert tipo in ("ABILITY", "ATTACH"), (
        f"con 1 fisica el turno sigue produciendo (TD o adjunte); "
        f"obtuvo {(tipo, destino)}")


def test_generico_td_dos_fisicas_sin_muro_no_capa():
    # The inverse control: with no Cornerstone/Crustle/wall in front (a neutral rival,
    # Kilowattrel 271) the cap does not apply and the Teal Dance of the Ogerpon with 2
    # physical is still alive.
    obs = (Escenario(turno=8, paso=1, tac=1)
           .mi_activo(pk(m.Tapu_Bulu, energias=[G], fisicas=1))
           .mi_banca(pk(m.Teal_Mask_Ogerpon_ex, energias=[G, G], fisicas=2))
           .mi_mano(m.Basic_Grass_Energy)
           .op_activo(pk(271, hp=120, max_hp=120))    # Kilowattrel
           .op_zonas(mano=4, mazo=40, premios=4)
           .menu_teal_dance()
           .construir())
    tipo, _ = _jugada_elegida(obs, m.agent(obs))
    assert tipo == "ABILITY", (
        f"sin muro anti-habilidad el tope no aplica: Teal Dance sigue siendo "
        f"la jugada (adjunta + ROBA); obtuvo {tipo}")
