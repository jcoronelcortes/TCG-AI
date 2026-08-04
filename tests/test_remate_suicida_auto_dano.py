"""The finisher that kills itself does not WIN: it draws. You have to retreat and finish with another.

Scenario (user, episode 88696693 registro_016 step 184 vs Marnie's Grimmsnarl,
DRAW):

    US                                RIVAL
    active  Tapu Bulu   20/140  6e    active  Impidimp   70/70   0e
    bench   Meganium    80/160  0e    bench   5 bodies (full)
            Ogerpon ex 100/210  6e
            Hydrapple  290/330  0e
    prizes left: 1                    prizes left: 1

The agent attacked with Wood Hammer (220 >= 70): it knocked out the Impidimp... and Wood Hammer
"also does 30 damage to itself", so Tapu Bulu's 20 HP did not
survive either. The two KOs are SIMULTANEOUS: each player took their LAST prize and
the game ended 0-0, a DRAW (`result=2` in the simulator).

The winning play was on the bench: retreat Tapu Bulu (cost 3) and promote the
Teal Mask Ogerpon ex, already with 6 energies, for Myriad Leaf Shower = 30 + 30x6 =
210 >= 70. Verified by driving the real simulator from step 184 with
`cg.api.search_begin/search_step`: the agent's line gives `result=2` (a draw) and
the retreat one gives `result=0` (OUR VICTORY).

The agent was missing THREE pieces, which are the ones these tests pin down:

 1. the attack's SELF-DAMAGE. It is not a field of `Attack`, it lives in its TEXT; now
    `_attack_self_damage` parses it (out of the ~49 attacks in the database with self-damage,
    telling apart mandatory / optional "You may" / coin flip / by counters).
 2. that the KO of OUR body ALSO PAYS PRIZES: `_active_attack_wins_now`
    declared victory looking only at the prizes we took.
 3. that when retreating you have to promote the FINISHER, not the tankiest body: the
    promotion brought up the 290 HP Hydrapple ex (no energy, it does not finish) ahead
    of the charged Ogerpon ex that closed out the game.
"""

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import main as m
from parcheo import parcheado
from state_builder import G, Escenario, pk

TAPU = m.Tapu_Bulu             # 920: Wood Hammer 220, -30 to itself
OGERPON = m.Teal_Mask_Ogerpon_ex
HYDRAPPLE = m.Hydrapple_ex
MEGANIUM = m.Meganium
LANAS = m.Lanas_Aid
BAYLEEF = m.Bayleef
GRASS = m.Basic_Grass_Energy

WOOD_HAMMER = 1326
MYRIAD_LEAF_SHOWER = 120

IMPIDIMP = 646                 # 70 HP, 1 prize (Grimmsnarl line)
ARCHALUDON_EX = 190           # 300 HP, Grass resistance (-30): it survives 220
SPIKEMUTH_GYM = 1259           # the rival's stadium in the record


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
    m._dodge_immune_serial = None
    m._dodge_immune_turn = -1
    yield
    m._init_cards_tracking()


# ---------------------------------------------------------------------------
# 1. The missing datum: the self-damage comes out of the attack's TEXT
# ---------------------------------------------------------------------------

def test_wood_hammer_se_hace_30_a_si_mismo():
    assert m._attack_self_damage(WOOD_HAMMER) == 30


def test_myriad_leaf_shower_no_tiene_auto_dano():
    assert m._attack_self_damage(MYRIAD_LEAF_SHOWER) == 0


def test_el_auto_dano_opcional_no_se_asume():
    """"You may do 30 more damage. If you do, this Pokemon also does 30 damage
    to itself" (Superpower 144): the decision is OURS, so the certain damage
    is 0. Same with the form without -s ("...also DO 60 damage to itself", 1171)."""
    assert m._attack_self_damage(144) == 0
    assert m._attack_self_damage(1171) == 0


def test_el_auto_dano_por_moneda_solo_cuenta_en_el_peor_caso():
    """Reckless Abandon (662): "Flip 2 coins. If both of them are tails, this
    Pokemon also does 90 damage to itself"."""
    assert m._attack_self_damage(662) == 0
    assert m._attack_self_damage(662, incierto=True) == 90


def test_el_auto_dano_por_contadores_usa_el_dano_recibido():
    """Vanguard Punch (51): 10 for EACH damage counter on the attacker."""
    herido = _pkmn(51, hp=80, max_hp=130)
    assert m._attack_self_damage(51, herido) == 50   # 5 counters


def test_una_moneda_posterior_no_convierte_el_auto_dano_en_azar():
    """Thump-Thump Boom (364): "This Pokemon does 100 damage to itself. Flip a
    coin..." -- the coin belongs to ANOTHER sentence and does not touch the self-damage."""
    assert m._attack_self_damage(364) == 100


def test_tapu_bulu_a_20_pv_se_noquea_con_su_propio_ataque():
    assert m._self_ko_by_own_attack(_pkmn(TAPU, hp=20, energias=6))
    assert not m._self_ko_by_own_attack(_pkmn(TAPU, hp=140, energias=6))


def test_sin_energia_para_pagar_el_ataque_no_hay_auto_dano():
    """The self-damage only counts if the attack can be USED: Wood Hammer costs
    4 units, and with 2 energies there is no attack (nor suicide) to fear."""
    tapu = _pkmn(TAPU, hp=20, energias=2)
    assert m._self_damage_of_pokemon(tapu) == 0
    assert not m._self_ko_by_own_attack(tapu)


# ---------------------------------------------------------------------------
# 2. Step 184: retreat instead of signing off on the draw
# ---------------------------------------------------------------------------

def _paso_184(op_premios=1, mis_premios=1, tapu_hp=20, ogerpon_energias=6):
    """The exact board of step 184. Meganium on the bench => each physical Grass
    counts DOUBLE, so 3 energy cards give 6 effective units."""
    return (Escenario(turno=16, paso=184, tac=1,
                      premios_propios=mis_premios)
            .mi_activo(pk(TAPU, hp=tapu_hp, energias=[G] * 6, fisicas=3))
            .mi_banca(pk(MEGANIUM, hp=80, pre_evo=[m.Chikorita, BAYLEEF]),
                      pk(OGERPON, hp=100, energias=[G] * ogerpon_energias,
                         fisicas=ogerpon_energias // 2),
                      pk(HYDRAPPLE, hp=290, pre_evo=[m.Applin, m.Dipplin]))
            .mi_mano(BAYLEEF, GRASS, LANAS)
            .estadio(SPIKEMUTH_GYM, del_rival=True)
            .op_activo(pk(IMPIDIMP))
            .op_banca(pk(IMPIDIMP), pk(IMPIDIMP), pk(IMPIDIMP),
                      pk(IMPIDIMP), pk(IMPIDIMP))
            .op_zonas(mano=4, mazo=25, prizes=op_premios))


def _tipo_elegido(obs, eleccion):
    return obs["select"]["option"][eleccion[0]]["type"]


def test_con_un_premio_por_lado_se_retira_en_vez_de_rematar_suicida():
    """THE FAILURE IN THE RECORD. Before: ATTACK (Wood Hammer) -> a 0-0 draw.
    Now: RETREAT, to promote the Ogerpon ex and win cleanly."""
    obs = _paso_184().menu_mano(con_retirada=True, con_ataque=True).construir()
    assert _tipo_elegido(obs, m.agent(obs)) == int(m.OptionType.RETREAT)


def test_el_remate_suicida_queda_vetado_mientras_exista_el_relevo():
    obs = _paso_184().menu_mano(con_retirada=True, con_ataque=True).construir()
    scores = _scores(obs)
    i_atk = _indice(obs, m.OptionType.ATTACK)
    i_ret = _indice(obs, m.OptionType.RETREAT)
    assert scores[i_atk] <= 0
    assert scores[i_ret] > 0


def test_sin_relevo_en_banca_el_empate_es_el_mejor_resultado_y_no_se_veta():
    """With nobody on the bench to finish, the draw is the best available: the
    attack is NOT vetoed (passing also ends in a draw, but gives away the turn).
    The veto is measured rather than the choice because, with energy in hand, attaching it
    scores higher than attacking through rules PRIOR to this change."""
    obs = (Escenario(turno=16, paso=184, tac=1, premios_propios=1)
           .mi_activo(pk(TAPU, hp=20, energias=[G] * 6, fisicas=3))
           .mi_banca(pk(MEGANIUM, hp=80, pre_evo=[m.Chikorita, BAYLEEF]))
           .mi_mano(GRASS)
           .op_activo(pk(IMPIDIMP))
           .op_banca(pk(IMPIDIMP))
           .op_zonas(mano=4, mazo=25, prizes=1)
           .menu_mano(con_retirada=True, con_ataque=True).construir())
    assert _scores(obs)[_indice(obs, m.OptionType.ATTACK)] > 0


def test_con_el_rival_lejos_del_final_el_remate_suicida_sigue_ganando():
    """The brake looks at the RIVAL'S prizes, not at self-damage in the abstract: with 3
    rival prizes our corpse (1 prize) does not close out their count, so
    Wood Hammer is still the top-priority winning finisher."""
    obs = _paso_184(op_premios=3).menu_mano(
        con_retirada=True, con_ataque=True).construir()
    assert _tipo_elegido(obs, m.agent(obs)) == int(m.OptionType.ATTACK)


def test_tapu_bulu_sano_no_se_suicida_y_remata_de_frente():
    """The same board with Tapu Bulu at 140/140: the 30 self-damage does not kill it,
    so there is no draw to avoid and ATTACKING is the first thing again."""
    obs = _paso_184(tapu_hp=140).menu_mano(
        con_retirada=True, con_ataque=True).construir()
    assert _tipo_elegido(obs, m.agent(obs)) == int(m.OptionType.ATTACK)


def test_el_remate_suicida_que_PIERDE_se_veta_aunque_no_haya_relevo():
    """A worse case than the draw: our attack does NOT knock out (a 380 HP Duraludon
    survives the 220), so the self-damage only HANDS the rival their last
    prize. There, attacking is losing: it is vetoed with no need for a relief body."""
    obs = (Escenario(turno=16, paso=184, tac=1, premios_propios=3)
           .mi_activo(pk(TAPU, hp=20, energias=[G] * 6, fisicas=3))
           .mi_banca(pk(MEGANIUM, hp=80, pre_evo=[m.Chikorita, BAYLEEF]))
           .mi_mano(GRASS)
           .op_activo(pk(ARCHALUDON_EX, hp=300, max_hp=300))
           .op_banca(pk(IMPIDIMP))
           .op_zonas(mano=4, mazo=25, prizes=1)
           .menu_mano(con_retirada=True, con_ataque=True).construir())
    scores = _scores(obs)
    assert scores[_indice(obs, m.OptionType.ATTACK)] <= 0


# ---------------------------------------------------------------------------
# 3. When retreating, the FINISHER comes up (not the tankiest body)
# ---------------------------------------------------------------------------

def test_la_promocion_tras_retirar_sube_al_que_gana_la_partida():
    """The other half of the chain: without this we retreated well and then brought up the
    290 HP Hydrapple ex (no energy, it does not finish) instead of the charged
    Ogerpon ex, and the turn closed without taking the prize."""
    obs = _paso_184().promocion_tras_retirada().construir()
    eleccion = m.agent(obs)
    idx = obs["select"]["option"][eleccion[0]]["index"]
    banca = obs["current"]["players"][0]["bench"]
    assert banca[idx]["id"] == OGERPON


def test_la_promocion_forzada_tras_un_KO_no_cambia_de_criterio():
    """The "bring up the finisher" bonus belongs only to the VOLUNTARY retreat
    (the SWITCH context, always on our turn and before attacking). The forced
    promotion after a KO (TO_ACTIVE) may fall on the rival's turn, where nobody
    attacks and the usual criterion is still the right one."""
    obs = _paso_184().promocion_desde_banca().construir()
    eleccion = m.agent(obs)
    idx = obs["select"]["option"][eleccion[0]]["index"]
    banca = obs["current"]["players"][0]["bench"]
    assert banca[idx]["id"] == HYDRAPPLE


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------

def _pkmn(card_id, hp, max_hp=None, energias=0):
    """A loose Pokemon for the self-damage helpers (without a full observation)."""
    return m.Pokemon(id=card_id, serial=0, hp=hp,
                     maxHp=max_hp if max_hp is not None else hp,
                     appearThisTurn=False, energies=[G] * energias,
                     energyCards=[], tools=[], preEvolution=[])


def _indice(obs, tipo):
    for i, o in enumerate(obs["select"]["option"]):
        if o["type"] == int(tipo):
            return i
    raise AssertionError(f"el menu no ofrece {tipo!r}")


def _scores(obs):
    """The scores the agent assigns to each menu option."""
    capturado = {}
    original = m._debug_log_decision

    def espia(context, select, scores, o, my_index, top_n=3):
        capturado.setdefault("scores", list(scores))
        return original(context, select, scores, o, my_index, top_n)

    # The spy is installed in ALL the modules that bind the name: the caller
    # now lives in ptcg/turno/finalize.py, not in main.
    with parcheado("_debug_log_decision", espia):
        m.agent(obs)
    assert "scores" in capturado, "el agente no puntuo el menu"
    return capturado["scores"]
