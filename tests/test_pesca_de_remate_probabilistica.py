"""FINISHER FISHING: the attack that today depends only on the DRAW.

Scenario (user, episode 89328622, registro_004 step 49 vs Marnie's
Grimmsnarl, LOST):

    US (seat 0)                              OPPONENT (Marnie's Grimmsnarl)
    active  Teal Mask Ogerpon ex 30/210      active  Marnie's Grimmsnarl ex
            with 1 energy (Myriad asks 3)            320/320, 2 {D} energies
    bench   Meowth ex 170, Fezandipiti ex    bench   Morgrem 100 (2e),
            180 (1e), Applin 40, Ogerpon             Snorunt 70, Impidimp 70 (2e)
            ex 210 (0e), Bayleef 110 (0e)
    hand    Lillie's x2, Boss's, Hydrapple
            ex, Ultra Ball  (ZERO energy)
    prizes  6 - 6      our deck 38 cards, 10 live Grass

No body could attack and there was not a single Grass in hand: the turn,
as it stood, did no damage. But the finisher DID exist, two cards
away:

    Lillie's Determination draws EIGHT (6 prizes untouched) -> 2 Grass ->
    the manual attachment + Teal Dance -> Myriad Leaf Shower with 3 energies of ours
    and 2 of the opponent's = 30 + 30 x 5 = 180, x2 for the Grass WEAKNESS of Marnie's
    Grimmsnarl ex = 360 >= 320 HP. TWO prizes.

With 10 live Grass in 42 cards (38 of deck + the 4 Lillie's shuffles back),
drawing 8 pulls the 2 that are missing **63%** of the time.

The agent played Boss's Orders to drag out a 70 HP Snorunt. The gust,
besides spending the Supporter slot, DEGRADES the finisher: Myriad Leaf Shower
scales with the energy on BOTH actives, so swapping a Grimmsnarl ex with
2 energies and a Grass weakness for a bare Snorunt turns a hit of 360
into one of 120. And with the Supporter already spent both Lillie's became
dead cards: the Ultra Ball discarded them to pay its cost.

THE BUG: "digging" was not measured, it was assumed
---------------------------------------------------
Lillie's ordering vetoes (`ultra_ball_completa_linea`,
`cede_a_boss_ejecutable`) treat the refill as a generic development play that
can always wait. When the draw is the ONLY line that attacks this turn,
that is false -- and how much it is worth depends on a number the agent never
computed: the probability that the draw brings the energy.

THE FIX: `_pesca_de_remate` + `_prob_al_menos`
----------------------------------------------
`_pesca_de_remate` is the DAMAGE-AWARE sibling of `_plan_de_planta`:
it shares its attachment arithmetic (how many Grass are missing, which routes can
point at that body today) and adds who is attacked, how much damage comes out and
how many prizes it takes. `_prob_al_menos` (hypergeometric over the deck
belief) measures whether the draw brings them. With a prize KO at >= `PESCA_PROB_MIN`,
Lillie's rises to `LILLIE_SCORE_PESCA_REMATE` (5900, above the whole
Boss's ladder that does not win the game) and Boss's yields the turn.
"""

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import main as m
from parcheo import parchear
from state_builder import Escenario, G, pk

OGERPON = m.Teal_Mask_Ogerpon_ex
LILLIE = m.Lillie_Determination
BOSS = m.Boss_Orders
GRASS = m.Basic_Grass_Energy

# The opponent's cards (they are not in our deck.csv).
GRIMMSNARL = 648
MORGREM = 647
IMPIDIMP = 646
SNORUNT = 860
DARK = 7

_FIX = ROOT / "tests" / "fixtures" / "marnie_pesca_de_remate_step49.json"


@pytest.fixture(autouse=True)
def reset_main_state():
    m._init_cards_tracking()
    m._cards_first_scan_done = False
    m._cards_prizes_identified = False
    m._cards_last_turn = -1
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
    m._init_cards_tracking()


def _fixture():
    with open(_FIX, encoding="utf-8") as f:
        return json.load(f)["observation"]


def _idx_play_de(obs, card_id):
    """The index of the PLAY option that plays `card_id` from hand."""
    yo = obs["current"]["yourIndex"]
    mano = obs["current"]["players"][yo]["hand"]
    for i, o in enumerate(obs["select"]["option"]):
        if o["type"] == int(m.OptionType.PLAY) and mano[o["index"]]["id"] == card_id:
            return i
    return -1


def _espiar_pesca(monkeypatch):
    """Captures the `_PescaRemate` the agent computes in the decision."""
    capturado = {}
    original = m._finisher_fishing

    def espia(*args, **kwargs):
        plan = original(*args, **kwargs)
        capturado["plan"] = plan
        return plan

    monkeypatch.setattr(m, "_finisher_fishing", espia)
    return capturado


# ---------------------------------------------------------------------------
# The board: that the finisher really existed, measured with the engine
# ---------------------------------------------------------------------------

def test_el_remate_existia_myriad_con_tres_energias_noquea_al_grimmsnarl():
    obs = m.to_observation_class(_fixture())
    st = obs.current
    yo, rival = st.players[0], st.players[1]

    active = yo.active[0]
    assert active.id == OGERPON and active.hp == 30
    assert len(active.energies) == 1, "1 de las 3 energias de Myriad"
    assert m.ATTACK_ENERGY_REQ[OGERPON] == 3
    assert not any(c["id"] == GRASS for c in _fixture()["current"]
                   ["players"][0]["hand"]), "ni una Planta en la mano"

    opa = rival.active[0]
    assert opa.id == GRIMMSNARL and opa.hp == 320
    assert m.prize_count_op(opa) == 2, "el Grimmsnarl ex vale DOS premios"

    # Myriad Leaf Shower with the 3 of ours + the 2 of the opponent's, and the Grass weakness.
    base = m._attacker_base_damage(OGERPON, opa, 3, grass_scale=3,
                                   teal_self_energy=3, bench_count=5)
    assert base == 180
    damage = m._our_effective_damage(active, opa, base, False, False)
    assert damage == 360 >= (opa.hp or 0), "debilidad Planta: 180 x 2"


def test_el_gusteo_degrada_el_objetivo_del_remate():
    """Myriad scales with the energy of BOTH actives: bringing up the bare Snorunt
    swaps a hit of 360 for one of 120."""
    obs = m.to_observation_class(_fixture())
    rival = obs.current.players[1]
    active = obs.current.players[0].active[0]
    snorunt = next(b for b in rival.bench if b is not None and b.id == SNORUNT)

    base_snorunt = m._attacker_base_damage(OGERPON, snorunt, 3, grass_scale=3,
                                           teal_self_energy=3, bench_count=5)
    dano_snorunt = m._our_effective_damage(active, snorunt, base_snorunt,
                                           False, False)
    assert dano_snorunt == 120, "sin energia rival que sumar y sin debilidad"
    assert m.prize_count_op(snorunt) == 1 < 2


# ---------------------------------------------------------------------------
# The hypergeometric
# ---------------------------------------------------------------------------

def test_prob_al_menos_reproduce_el_63_por_ciento_del_registro():
    # The record's reality: 10 live Grass in the 42-card deck (38 + the 4 that
    # Lillie's shuffles back), drawing 8.
    assert m._prob_al_menos(10, 42, 8, 2) == pytest.approx(0.6257, abs=1e-4)
    assert m._prob_al_menos(10, 42, 8, 1) == pytest.approx(0.9109, abs=1e-4)
    assert m._prob_al_menos(10, 42, 8, 3) == pytest.approx(0.2802, abs=1e-4)
    # What the agent can KNOW (the belief: the deck + the face-down prizes are
    # unseen cards): 11 in 48. Conservative, never optimistic.
    assert m._prob_al_menos(11, 48, 8, 2) == pytest.approx(0.5976, abs=1e-4)


def test_prob_al_menos_fronteras():
    assert m._prob_al_menos(0, 40, 8, 1) == 0.0        # no outs
    assert m._prob_al_menos(10, 40, 8, 0) == 1.0       # nothing is needed
    assert m._prob_al_menos(1, 40, 8, 2) == 0.0        # fewer copies than k
    assert m._prob_al_menos(10, 40, 1, 2) == 0.0       # a smaller draw than k
    assert m._prob_al_menos(40, 40, 8, 8) == 1.0       # the whole deck is outs


def test_el_robo_de_lillie_es_ocho_solo_con_los_seis_premios():
    assert m._lillie_draw_count(6) == 8
    assert m._lillie_draw_count(5) == 6
    assert m._lillie_draw_count(1) == 6


# ---------------------------------------------------------------------------
# The real decision of step 49
# ---------------------------------------------------------------------------

def test_paso49_pesca_dos_cartas_por_dos_premios(monkeypatch):
    capturado = _espiar_pesca(monkeypatch)
    m.agent(_fixture())
    plan = capturado["plan"]

    assert plan is not None
    assert plan.attacker_id == OGERPON and not plan.from_bench
    assert plan.cards_needed == 2, "faltan DOS Plantas (adjunte manual + Teal Dance)"
    assert plan.lethal and plan.prizes == 2
    assert plan.damage == 360
    # The belief counts what is UNSEEN (deck 38 + 6 prizes): 11 Grass in 48
    # cards after shuffling the 4 from hand. A conservative estimate of the real
    # 0.63 (10 live Grass in the 42-card deck).
    assert plan.draws == 8 and plan.outs == 11 and plan.universe == 48
    assert plan.prob == pytest.approx(0.5976, abs=1e-4)


def test_paso49_juega_lillie_para_pescar_no_boss():
    obs = _fixture()
    eleccion = m.agent(obs)
    assert eleccion == [_idx_play_de(obs, LILLIE)], (
        "con el turno sin ataque posible y un KO de 2 premios a 2 cartas de "
        "distancia, el hueco de Supporter es de Lillie's")


def test_paso49_contrafactual_sin_pesca_vuelve_a_gustear(monkeypatch):
    """Control: if the fishing is not measured (an unreachable threshold), the
    Boss's of the record reappears. It is the change the rule introduces, not another."""
    parchear(monkeypatch, "FISHING_PROB_MIN", 1.1)
    obs = _fixture()
    assert m.agent(obs) == [_idx_play_de(obs, BOSS)]


# ---------------------------------------------------------------------------
# Synthetic boundaries (StateBuilder): probability, energy in hand
# ---------------------------------------------------------------------------

def _escenario_paso49(grass_in_deck=10, grass_en_mano=0, con_adjunte=False):
    """A synthetic replica of step 49 with the deck parameterised.

    grass_en_mazo: LIVE Grass in the deck (the rest goes to the discard).
    grass_en_mano: Grass already in hand (0 = like the real one).
    """
    mano = [LILLIE, BOSS, LILLIE, m.Hydrapple_ex, m.Ultra_Ball]
    mano += [GRASS] * grass_en_mano

    esc = (Escenario(turn=4, paso=49, tac=1, primer_jugador=1)
           .mi_activo(pk(OGERPON, hp=30, energias=[G], fisicas=1))
           .mi_banca(pk(m.Meowth_ex),
                     pk(m.Fezandipiti_ex, hp=180, energias=[G], fisicas=1),
                     pk(m.Applin),
                     pk(OGERPON),
                     pk(m.Bayleef, pre_evo=[m.Chikorita]))
           .mi_mano(*mano)
           .op_activo(pk(GRIMMSNARL, hp=320, max_hp=320,
                         energias=[DARK, DARK], pre_evo=[IMPIDIMP]))
           .op_banca(pk(MORGREM, hp=100, max_hp=100, energias=[DARK, DARK],
                        pre_evo=[IMPIDIMP]),
                     pk(SNORUNT, hp=70, max_hp=70),
                     pk(IMPIDIMP, hp=70, max_hp=70, energias=[DARK, DARK]))
           .op_zonas(mano=5, mazo=32, prizes=6))

    # Deck: the requested live Grass + filler from the pool (including the Dipplin
    # that makes the Ultra Ball "complete a line", as in the record).
    # `_pool` (private) = what is left of deck.csv after placing the field and the hand.
    # The Grass that does not go to the deck is declared in the DISCARD (visible), so
    # that the deck belief sees exactly `grass_en_mazo` outs.
    n_grass = min(grass_in_deck, esc._pool[GRASS])
    esc.mi_descarte(*([GRASS] * (esc._pool[GRASS] - n_grass)))
    relleno = [cid for cid in sorted(esc._pool.elements()) if cid != GRASS]
    # The deck reaches 38 cards (like the real one) as long as there is filler to spare;
    # with a lot of Grass in the discard it comes out shorter (always leaving 6
    # cards for the prizes).
    ids_mazo = ([GRASS] * n_grass
                + relleno[:max(0, min(38 - n_grass, len(relleno) - 6))])
    esc.mazo(*ids_mazo).resto_al_descarte()
    obs = esc.menu_mano(con_adjunte=con_adjunte).construir()
    # `menu_mano` emits one PLAY per EACH card in hand; the simulator does not. The
    # two that were not in the menu on the real step are removed: the Hydrapple ex
    # (an evolution without its Dipplin in play -- exactly what makes the Ultra Ball
    # "complete a line" and veto Lillie's) and the Grass, which are played through
    # ATTACH, not through PLAY.
    mano_obs = obs["current"]["players"][obs["current"]["yourIndex"]]["hand"]
    obs["select"]["option"] = [
        o for o in obs["select"]["option"]
        if not (o["type"] == int(m.OptionType.PLAY)
                and mano_obs[o["index"]]["id"] in (m.Hydrapple_ex, GRASS))]
    return obs


def test_sintetico_reproduce_la_decision_real(monkeypatch):
    capturado = _espiar_pesca(monkeypatch)
    obs = _escenario_paso49()
    assert m.agent(obs) == [_idx_play_de(obs, LILLIE)]
    assert capturado["plan"].prizes == 2


def test_con_el_mazo_seco_de_plantas_la_pesca_no_pisa_los_vetos(monkeypatch):
    """Boundary: with a single live Grass the draw canNOT bring the two that
    are missing (prob 0) and the refill loses its privilege."""
    capturado = _espiar_pesca(monkeypatch)
    obs = _escenario_paso49(grass_in_deck=1)
    assert capturado is not None
    eleccion = m.agent(obs)
    assert capturado["plan"] is None, "sin outs suficientes no hay pesca"
    assert eleccion != [_idx_play_de(obs, LILLIE)]


def test_frontera_de_probabilidad(monkeypatch):
    """The fishing fires above the threshold and stays quiet below it, with the SAME board:
    the only thing that changes is how many Grass are left alive."""
    vistos = {}
    for grass in (3, 10):
        m._init_cards_tracking()
        m._cards_first_scan_done = False
        m._cards_prizes_identified = False
        m._cards_last_turn = -1
        capturado = _espiar_pesca(monkeypatch)
        obs = _escenario_paso49(grass_in_deck=grass)
        juega_lillie = (m.agent(obs) == [_idx_play_de(obs, LILLIE)])
        vistos[grass] = (capturado["plan"].prob, juega_lillie)

    assert vistos[3][0] < m.FISHING_PROB_MIN < vistos[10][0]
    assert vistos[3][1] is False, "3 Plantas de 42 robando 8: no paga barajar"
    assert vistos[10][1] is True


def test_la_pesca_exitosa_se_convierte_en_ataque():
    """Closing the loop: with the 3 energies already placed (the fishing came off) and the
    hand empty, the 30 HP Ogerpon ex ATTACKS -- it neither retreats nor closes the turn."""
    esc = (Escenario(turn=4, paso=49, tac=6, primer_jugador=1,
                     energia_jugada=True, partidario_jugado=True)
           .mi_activo(pk(OGERPON, hp=30, energias=[G, G, G], fisicas=3))
           .mi_banca(pk(m.Meowth_ex),
                     pk(m.Fezandipiti_ex, hp=180, energias=[G], fisicas=1),
                     pk(m.Applin),
                     pk(OGERPON),
                     pk(m.Bayleef, pre_evo=[m.Chikorita]))
           .op_activo(pk(GRIMMSNARL, hp=320, max_hp=320,
                         energias=[DARK, DARK], pre_evo=[IMPIDIMP]))
           .op_banca(pk(MORGREM, hp=100, max_hp=100, energias=[DARK, DARK],
                        pre_evo=[IMPIDIMP]),
                     pk(SNORUNT, hp=70, max_hp=70))
           .op_zonas(mano=5, mazo=32, prizes=6))
    esc.mazo(*sorted(esc._pool.elements())[:34]).resto_al_descarte()
    obs = esc.menu_mano(con_retirada=True, con_ataque=True).construir()
    eleccion = m.agent(obs)
    assert (obs["select"]["option"][eleccion[0]]["type"]
            == int(m.OptionType.ATTACK))


def test_con_la_energia_ya_en_mano_no_se_baraja_la_mano(monkeypatch):
    """A critical control: if the HAND already brings the 2 missing Grass, playing
    Lillie's would return them to the deck. There is NO fishing there: it charges."""
    capturado = _espiar_pesca(monkeypatch)
    obs = _escenario_paso49(grass_en_mano=2, con_adjunte=True)
    eleccion = m.agent(obs)

    assert capturado["plan"] is None, (
        "con la energia en la mano no se pesca: se adjunta")
    tipo = obs["select"]["option"][eleccion[0]]["type"]
    assert tipo == int(m.OptionType.ATTACH), (
        "la jugada es cargar al Ogerpon, no barajar la mano")
