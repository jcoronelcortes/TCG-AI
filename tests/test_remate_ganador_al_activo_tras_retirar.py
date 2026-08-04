"""MATCH POINT against the rival ACTIVE: the finisher is on the BENCH.

Scenario (user, episode 89104831, registro_010 step 144 vs Marnie's
Grimmsnarl ex, LOST):

    US (seat 1)                             RIVAL (Marnie's Grimmsnarl)
    active  Fezandipiti ex 20/210 (2 eff.)  active  Marnie's Grimmsnarl ex
    bench   Meowth ex 130, Meowth ex 160,           310/320, 3 {D} energies
            Teal Mask Ogerpon ex 200 (4e),  bench   2x Munkidori 100,
            Meganium 150, Ogerpon ex 200            Froslass 90, Impidimp 70
    hand    Xerosic, Chikorita, Dipplin,
            Hydrapple ex, Meganium, Boss's
    prizes  2 - 1   (we are TWO short)

The menu offered exactly four things: Xerosic, Boss's Orders, RETREAT and
END. There was mate on the board:

    RETREAT Fezandipiti (cost 1, and it carries energy) -> promote the Teal Mask
    Ogerpon ex with 4 energies -> Myriad Leaf Shower.

Myriad Leaf Shower does 30 + 30 for each Energy attached to BOTH actives
(see [[ogerpon-myriad-cuenta-ambos-activos]]): 30 + 30 x (4 ours + 3 of the
Grimmsnarl) = 240, and the Grimmsnarl ex has a Grass WEAKNESS -> 240 x 2 =
**480 >= 310**. It is a Pokemon ex: **2 prizes**, exactly the 2 that were missing.
The game won on the spot.

The agent played Boss's Orders, gusted a Froslass (1 prize), knocked it out and
closed the turn at 1 prize. The rival finished us off on theirs.

THE BUG: THE RIVAL ACTIVE WAS INVISIBLE
---------------------------------------
Every reading of "can I knock out the rival ACTIVE?" was done with the
Pokemon that is in the active spot TODAY -- `_boss_dmg_to` -> `_bo_can_ko_active`,
and `_bpr_active_can_ko` inside `_boss_prize_rank`. With the Fezandipiti
stuck (2 effective, its attack asks for 3) that gives 0 damage, hence
`_bo_active_prize = 0`: the 2-prize Grimmsnarl ex counted as ZERO
prizes and any 1-prize bench body beat it. Boss's scored
5200 (`gusteo_por_prize_rank`) against the retreat's 3500.

The asymmetry is the failure, not the number: for BENCH targets that same
block DOES look through the retreat (`_bench_attacker_can_ko`, both in
`_boss_prize_rank` and in `_bo_win_via_bench`); for the ACTIVE, never.

THE FIX: `_win_ko_active_via_promote`
-------------------------------------
It closes the symmetry in the one case that admits no argument -- when that KO
WINS the game (`prize_count_op(rival active) >= my_prize`), the retreat is
payable and the finisher is on the BENCH (if the CURRENT active already knocks out,
the route is to attack, not to retreat). Winning is a VETO, the same criterion as
PROMO_MATCH_POINT_VETO: the Boss's is vetoed, `_boss_prize_rank` is cancelled and the
retreat rises to 9600 with `_TIER_WIN_ATTACK` so that no energy charge
overtakes it by ORDER.
"""

import copy
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import main as m

BOSS = m.Boss_Orders
OGERPON = m.Teal_Mask_Ogerpon_ex
GRIMMSNARL = 648
FROSLASS = 104

_FIX = (ROOT / "tests" / "fixtures"
        / "marnie_remate_ganador_al_activo_tras_retirar_step144.json")


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
    # Matchup/table globals: without resetting them, the suite's order decides which
    # Supporter wins among the NON-vetoed ones and the boundary becomes fragile.
    m.meganium_in_play = False
    m.forest_in_play = False
    m.we_go_first = False
    m.op_is_crustle_deck = False
    m.op_is_cornerstone_deck = False
    m.op_has_mega_kangaskhan = False
    yield
    m._init_cards_tracking()


def _fixture():
    with open(_FIX, encoding="utf-8") as f:
        return json.load(f)


def _tipos(obs):
    return [o["type"] for o in obs["select"]["option"]]


def _idx_of_type(obs, tipo):
    return _tipos(obs).index(int(tipo))


def _idx_play_boss(obs):
    yo = obs["current"]["yourIndex"]
    hand = obs["current"]["players"][yo]["hand"]
    for i, o in enumerate(obs["select"]["option"]):
        if o["type"] == int(m.OptionType.PLAY) and hand[o["index"]]["id"] == BOSS:
            return i
    return -1


# ---------------------------------------------------------------------------
# The board: that the mate really existed, measured with the engine's evaluators
# ---------------------------------------------------------------------------

def test_el_mate_existia_ogerpon_de_banca_noquea_al_grimmsnarl():
    obs = m.to_observation_class(_fixture()["observation"])
    st = obs.current
    yo, rival = st.players[1], st.players[0]

    assert len(yo.prize) == 2, "nos faltaban DOS premios"
    opa = rival.active[0]
    assert opa.id == GRIMMSNARL and opa.hp == 310
    assert m.prize_count_op(opa) == 2, "el Grimmsnarl ex vale 2 premios"

    # The retreat was payable: cost 1 and the Fezandipiti carried energy.
    act = yo.active[0]
    assert len(act.energies) >= m.RETREAT_COST.get(act.id, 1)

    m.meganium_in_play = any(p is not None and p.id == m.Meganium
                             for p in (yo.active + yo.bench))
    total_grass = sum(len(p.energies) for p in (yo.active + yo.bench)
                      if p is not None)

    ogerpon = next(p for p in yo.bench
                   if p is not None and p.id == OGERPON and len(p.energies) == 4)
    base = m._attacker_base_damage(ogerpon.id, opa, len(ogerpon.energies),
                                   grass_scale=total_grass,
                                   teal_self_energy=len(ogerpon.energies),
                                   bench_count=len(yo.bench))
    # 30 + 30 x (4 ours + 3 theirs) = 240 ... and x2 for the Grass weakness.
    assert base == 240, base
    efectivo = m._our_effective_damage(ogerpon, opa, base, m.meganium_in_play)
    assert efectivo == 480, efectivo
    assert efectivo >= opa.hp, "el KO al activo rival GANA la partida"

    # No gust from the rival bench takes the 2 prizes that are missing.
    assert all(m.prize_count_op(b) == 1
               for b in rival.bench if b is not None)


# ---------------------------------------------------------------------------
# The decision: RETREAT, not Boss's Orders
# ---------------------------------------------------------------------------

def test_retira_en_vez_de_gustear():
    fx = _fixture()
    previa, decision = fx["observacion_previa"], fx["observation"]

    # The real menu offered both: playing the Boss's and RETREATING.
    i_boss = _idx_play_boss(decision)
    i_retreat = _idx_of_type(decision, m.OptionType.RETREAT)
    assert i_boss >= 0 and i_retreat >= 0, _tipos(decision)

    m.agent(previa)
    choice = m.agent(decision)

    assert choice == [i_retreat], (
        f"esperaba RETIRAR (idx {i_retreat}), eligio {choice}")
    assert choice != [i_boss], "el Boss's tira el turno ganador"


def test_la_linea_completa_cierra_la_partida():
    """After retreating: promote the charged Ogerpon and attack the Grimmsnarl."""
    fx = _fixture()

    promo = fx["contrafactual_promocion"]
    choice = m.agent(promo)
    bench = promo["current"]["players"][1]["bench"]
    subido = bench[promo["select"]["option"][choice[0]]["index"]]
    assert subido["id"] == OGERPON and len(subido["energies"]) == 4, subido

    attack_id = fx["contrafactual_ataque"]
    assert attack_id["current"]["players"][0]["active"][0]["id"] == GRIMMSNARL
    choice = m.agent(attack_id)
    opcion = attack_id["select"]["option"][choice[0]]
    assert opcion["type"] == int(m.OptionType.ATTACK), opcion


# ---------------------------------------------------------------------------
# The BOUNDARY: the rule only rules when the KO WINS the game
# ---------------------------------------------------------------------------

def test_la_regla_no_depende_del_atacante_concreto():
    """The same board with a charged Tapu Bulu (non-ex, another attack) instead of the
    Ogerpon: Wood Hammer 220 x2 for the weakness = 440 >= 310. It is still mate,
    so the retreat still rules. The flag leans on
    `_bench_attacker_can_ko`, which is generic."""
    fx = _fixture()
    decision = copy.deepcopy(fx["observation"])
    for p in decision["current"]["players"][1]["bench"]:
        if p["id"] == OGERPON and len(p["energies"]) == 4:
            p["id"] = m.Tapu_Bulu
            p["hp"] = p["maxHp"] = 140
            break
    else:
        pytest.fail("no se encontro el Ogerpon cargado en la banca")

    m.agent(fx["observacion_previa"])
    choice = m.agent(decision)
    assert choice == [_idx_of_type(decision, m.OptionType.RETREAT)], choice


def test_sin_rematador_en_banca_no_dispara():
    """BOUNDARY: if no bench body knocks out the rival active, retreating closes
    nothing and the Boss's is the play again."""
    fx = _fixture()
    decision = copy.deepcopy(fx["observation"])
    for p in decision["current"]["players"][1]["bench"]:
        if p["id"] == OGERPON and len(p["energies"]) == 4:
            p["energies"] = [1]
            p["energyCards"] = p["energyCards"][:1]
            break

    m.agent(fx["observacion_previa"])
    choice = m.agent(decision)
    # The rule's contract is "close out the game by retreating". With no finisher it closes
    # nothing, so it must not hijack the turn; which of the NON-vetoed
    # Supporters wins afterwards is decided by other scorers.
    assert choice != [_idx_of_type(decision, m.OptionType.RETREAT)], choice


def test_sin_match_point_el_gusteo_sigue_vivo():
    """With THREE prizes left, the KO on the active (2 prizes) no longer closes
    the game: the veto does not fire and Boss's Orders is playable again."""
    fx = _fixture()
    decision = copy.deepcopy(fx["observation"])
    decision["current"]["players"][1]["prize"] = [None, None, None]

    m.agent(fx["observacion_previa"])
    choice = m.agent(decision)

    assert choice != [_idx_of_type(decision, m.OptionType.RETREAT)], (
        f"sin match point la retirada no debe mandar, eligio {choice}")
    assert choice == [_idx_play_boss(decision)], (
        f"sin match point el gusteo debe seguir disponible, eligio {choice}")
