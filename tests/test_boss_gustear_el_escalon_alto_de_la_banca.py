"""The HIGHEST step of an opposing line, if it is on the BENCH, gets GUSTED.

Scenario (user, `registros/registro_008_pasos_133_hasta_141.json` step 136,
episode 89224411, turn 8, vs Marnie's Grimmsnarl ex, **LOST**):

    US (seat 1, 4 prizes)                  OPPONENT (2 prizes)
    active  Hydrapple ex 300/330, 2e       active  **Marnie's Impidimp** 70 HP,
    bench   Meganium 2e, Meowth ex,                a Basic, **1 energy**
            Fezandipiti ex, Ogerpon ex 4e, bench   Froslass, Froslass,
            Ogerpon ex                             Munkidori 1e,
    hand    Xerosic, **Dawn**, Dipplin,            **Marnie's Morgrem 100 HP,
            Hydrapple ex, **Boss's Orders**,       Stage 1, 2 energies**,
            Bayleef, Poke Pad, Tapu Bulu           Munkidori 1e

Syrup Storm (30 + 30 for each Grass on ALL our Pokemon, 8 units)
knocks out either of the two bodies, and both are worth **1 prize**. The
agent played **Dawn** and attacked the Impidimp. That is the mistake: the Morgrem is one
step HIGHER UP the SAME line and is only reachable by GUSTING it.

  * killing the Impidimp takes 1 prize and lets the **Morgrem** evolve into
    **Marnie's Grimmsnarl ex** (Stage 2, 320 HP, 2 prizes, *Punk Up* searches 5
    energies from the deck when evolving) -- which is exactly what happened in
    the record: the opponent promoted the Morgrem and closed the game;
  * gusting the Morgrem takes **the same prize** and forces the opponent to rebuild
    BOTH steps (evolving the Impidimp and searching for the Stage 2 again).

RULE (symmetric to [[boss-gust-mayor-evolucion-fase2]]): inside a line
Basic -> Stage 1 -> Stage 2 the highest reachable stage is ALWAYS knocked out. If
the one higher up is the opposing ACTIVE, we attack and keep the Boss's
(test_boss_noquear_la_etapa_mas_alta_de_la_linea); if it is on the BENCH, the
Boss's is spent bringing it up.

Why it did not fire
-------------------
The deny-evo loop of the Boss's valuation discarded the Morgrem through
`_bo_active_prize_dominates` (the active yields >= prizes than the pre-evolution: 1 >= 1)
and none of its three exceptions covered this board:

  * `_bo_pe_is_ex_line_vs_wall` and `_bo_pe_is_energized_preevo_vs_bare_wall`
    require an opposing active with **0 energies**; the Impidimp had 1;
  * `_bo_pe_is_energized_preevo_off_line` requires an active that is **outside** the line;
    the Impidimp is the pre-evolution of the line itself.

All three looked at the active's ENERGY, never at its STAGE. The fix
(`_bo_pe_outranks_active`) is the exact mirror of the stage veto that already existed
in the opposite direction, and it is deck-agnostic by double entry: the stage comes
from the card data (`_supera_en_evolucion`) and the "it is worth the Boss's" from the
chain ending in an ex (`_linea_culmina_en_ex`), not from per-deck lists.

Measurement: 1 single flip in the 63 decisions of ours in episode 89224411 (the
one of this step). The golden corpus unchanged. Self-play vs the bot (700 games per
branch): Marnie 95.0% vs 93.9%, Cynthia 99.4% vs 98.7%, Dragapult 97.3% = 97.3%.

Later unification (`_preevo_de_linea_ex`)
-----------------------------------------
The standalone block `_deny_evo_via_boss` -- the one that feeds the Meowth ex
-> Last-Ditch Catch -> Boss's engine when the card is in the DECK -- classified the
pre-evolution with the curated list `EX_PREEVO_IDS`, which only grew *after* losing
a game (the Cynthia line was added that way). Now it uses the same card-data
helper, with the `DUNSPARCE_IDS` guard (their line culminates in Dudunsparce ex but
the gust has them FORBIDDEN as targets: motivating a gust towards a vetoed
target is the Dwebble failure of log 86339758). It is an exact superset of the
list -- pinned by `test_el_helper_es_SUPERCONJUNTO_de_la_lista_curada` -- and it adds
three cards across the whole meta: Frillish (jellicent_lock, with its Jellicent ex IN ITS
OWN DECK), Applin/Dipplin (festival_lead) and Snorunt (marnie).

That second part is NEUTRAL in winrate and the gate cannot measure it: with 2500
games per branch, jellicent_lock 94.2% vs 94.9%, festival_lead 99.0% = 99.0% and
the CONTROL GROUP -- mega_lucario, where both branches execute exactly the
same code because no card of that deck changes class -- 92.2% vs 93.2%,
that is, 1.0 point of pure noise. Its justification is not the scoreboard but not having
to hand-list every new opposing line again.
"""

import copy
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "tests") not in sys.path:
    sys.path.insert(0, str(ROOT / "tests"))

import main as m
from cg.api import AreaType, OptionType, SelectContext, SelectType

_FIXTURE = (ROOT / "tests" / "fixtures"
            / "marnie_step136_gustear_el_morgrem_no_el_impidimp.json")

IMPIDIMP = m.Marnies_Impidimp
MORGREM = m.Marnies_Morgrem
GRIMMSNARL = m.Grimmsnarl_ex
HYDRAPPLE = m.Hydrapple_ex
BOSS = m.Boss_Orders
DAWN = m.Dawn
FROSLASS = m.Froslass
MUNKIDORI = m.Munkidori


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
    m._ub_fez_pending = False
    m._ld_supp_comprometido = 0
    m._dodge_immune_serial = None
    m._dodge_immune_turn = -1
    yield
    m._init_cards_tracking()


def _obs():
    return copy.deepcopy(json.load(open(_FIXTURE, encoding="utf-8"))["observation"])


def _pkm(card_id, energias=0):
    return SimpleNamespace(id=card_id, energies=[1] * energias, energyCards=[],
                           tools=[])


def _idx(obs, **campos):
    """The index of the menu option that meets all the given fields."""
    return next(i for i, o in enumerate(obs["select"]["option"])
                if all(o.get(k) == v for k, v in campos.items()))


def _mano_idx(obs, card_id):
    """The position of `card_id` in OUR hand (the one the type=7 options use)."""
    yo = obs["current"]["yourIndex"]
    return next(i for i, c in enumerate(obs["current"]["players"][yo]["hand"])
                if c["id"] == card_id)


def _menu_de_gusteo(obs):
    """Turns the MAIN menu into the TARGET select of the already played Boss's."""
    cur = obs["current"]
    yo = cur["yourIndex"]
    mio, riv = cur["players"][yo], cur["players"][1 - yo]
    mio["hand"] = [c for c in mio["hand"] if c["id"] != BOSS]
    mio["handCount"] = len(mio["hand"])
    cur["supporterPlayed"] = True
    obs["select"] = {
        "type": int(SelectType.CARD), "context": int(SelectContext.SWITCH),
        "minCount": 1, "maxCount": 1,
        "remainDamageCounter": 0, "remainEnergyCost": 0,
        "option": [{"type": int(OptionType.CARD), "area": int(AreaType.BENCH),
                    "index": k, "playerIndex": 1 - yo}
                   for k in range(len(riv["bench"]))],
        "deck": None, "contextCard": None,
        "effect": {"id": BOSS, "playerIndex": yo, "serial": 500},
    }
    return obs


# ---------------------------------------------------------------------------
# 1. The scenario: without it, the test measures nothing
# ---------------------------------------------------------------------------

def test_el_fixture_es_el_paso_136_con_la_fase_1_en_la_banca():
    o = _obs()
    yo = o["current"]["yourIndex"]
    mio = o["current"]["players"][yo]
    riv = o["current"]["players"][1 - yo]

    assert o["current"]["turn"] == 8 and not o["current"]["supporterPlayed"]

    # Us: a Hydrapple ex as the active and the menu offering Dawn, Boss's and attacking.
    assert mio["active"][0]["id"] == HYDRAPPLE
    assert {BOSS, DAWN} <= {c["id"] for c in mio["hand"]}
    assert _idx(o, type=7, index=_mano_idx(o, BOSS)) >= 0
    assert _idx(o, type=7, index=_mano_idx(o, DAWN)) >= 0
    assert _idx(o, type=13) >= 0

    # The opponent: an Impidimp (a Basic) as the active WITH energy -- which is why the
    # "bare wall" exceptions were not enough -- and the charged Morgrem (Stage 1)
    # on the bench. Both bodies are worth 1 prize.
    assert riv["active"][0]["id"] == IMPIDIMP
    assert len(riv["active"][0]["energies"]) == 1
    banca = [b["id"] for b in riv["bench"]]
    assert banca == [FROSLASS, FROSLASS, MUNKIDORI, MORGREM, MUNKIDORI]
    assert len(riv["bench"][3]["energies"]) == 2
    assert m.prize_count_op(_pkm(IMPIDIMP)) == m.prize_count_op(_pkm(MORGREM)) == 1

    # ...and the line ends in a 2-prize ex: that is why cutting it is worth the Boss's.
    assert m.prize_count_op(_pkm(GRIMMSNARL)) == 2


def test_el_hydrapple_noquea_a_los_dos_cuerpos():
    """The rule only makes sense if both KOs are REAL: if the Morgrem did not
    die, gusting it would be giving the opponent a free retreat."""
    o = _obs()
    riv = o["current"]["players"][1 - o["current"]["yourIndex"]]
    assert riv["active"][0]["hp"] == 70 and riv["bench"][3]["hp"] == 100
    # Syrup Storm: 30 + 30 for each Grass on ALL our Pokemon.
    mio = o["current"]["players"][o["current"]["yourIndex"]]
    plantas = len(mio["active"][0]["energies"]) + sum(
        len(b["energies"]) for b in mio["bench"])
    assert 30 + 30 * plantas >= 100


# ---------------------------------------------------------------------------
# 2. The decision and the target
# ---------------------------------------------------------------------------

def test_se_juega_el_boss_no_el_dawn():
    o = _obs()
    assert m.agent(o) == [_idx(o, type=7, index=_mano_idx(o, BOSS))], (
        "con la Fase 1 de la linea en la BANCA y noqueable, se juega Boss's: "
        "mismo premio que atacar al Basico de enfrente, pero corta la linea un "
        "escalon mas arriba y retrasa dos turnos a Marnie's Grimmsnarl ex")


def test_el_objetivo_del_gusteo_es_el_morgrem():
    o = _menu_de_gusteo(_obs())
    riv = o["current"]["players"][1 - o["current"]["yourIndex"]]
    elegido = m.agent(o)
    assert riv["bench"][elegido[0]]["id"] == MORGREM, (
        "el gusteo va a la Fase 1 energizada, no a las Froslass ni a los "
        "Munkidori de soporte")


def test_con_la_fase_1_ya_de_activo_no_se_gasta_el_boss():
    """Control (the stage veto, on the same board): if the high step is ALREADY
    the active, attacking it is free and the Boss's is kept."""
    o = _obs()
    riv = o["current"]["players"][1 - o["current"]["yourIndex"]]
    activo, banca = riv["active"][0], riv["bench"][3]
    activo["id"], banca["id"] = MORGREM, IMPIDIMP
    activo["hp"] = activo["maxHp"] = 100
    banca["hp"] = banca["maxHp"] = 70
    activo["preEvolution"] = [{"id": IMPIDIMP, "playerIndex": 0, "serial": 900}]
    banca["preEvolution"] = []

    assert m.agent(o) == [_idx(o, type=13)], (
        "con la Fase 1 delante se ATACA: mismo premio, corta la linea igual de "
        "arriba y no gasta el Boss's ni el Supporter del turno")


def test_la_regla_no_es_de_la_linea_marnie(monkeypatch):
    """Deck-agnostic: the same board with the Dreepy -> Drakloak ->
    Dragapult ex line resolves the same way, without touching any per-deck list."""
    o = _obs()
    riv = o["current"]["players"][1 - o["current"]["yourIndex"]]
    activo, banca = riv["active"][0], riv["bench"][3]
    activo["id"], banca["id"] = m.Dreepy, m.Drakloak
    activo["hp"] = activo["maxHp"] = 60
    banca["hp"] = banca["maxHp"] = 90
    activo["preEvolution"] = []
    banca["preEvolution"] = [{"id": m.Dreepy, "playerIndex": 0, "serial": 900}]

    assert m.agent(o) == [_idx(o, type=7, index=_mano_idx(o, BOSS))]


# ---------------------------------------------------------------------------
# 3. `_linea_culmina_en_ex`, in isolation (deck-agnostic)
# ---------------------------------------------------------------------------

def test_la_linea_ex_se_deriva_del_dato_de_carta():
    # Lines that DO end in a 2-prize attacker: cutting them is worth the Boss's.
    for cid in (IMPIDIMP, MORGREM, m.Cynthias_Gible, m.Cynthias_Gabite,
                m.Dreepy, m.Drakloak, m.Ralts, m.Kirlia, m.Duraludon,
                m.Riolu, m.Buneary, m.Applin, m.Dipplin):
        assert m._line_ends_in_ex(cid), cid


def test_la_linea_alakazam_queda_fuera():
    """Abra -> Kadabra -> Alakazam ends in a 1-prize body: gusting its
    pre-evolution yields the same as attacking from the front. That is
    [[boss-no-gustear-preevo-linea-no-ex]], and here it comes for free from the card data."""
    assert not m._line_ends_in_ex(m.Abra)
    assert not m._line_ends_in_ex(m.Kadabra)
    assert not m._line_ends_in_ex(m.Dwebble_Grass)
    assert not m._line_ends_in_ex(m.Hops_Phantump)


def test_el_helper_es_SUPERCONJUNTO_de_la_lista_curada():
    """`_preevo_de_linea_ex` replaces `EX_PREEVO_IDS` in the standalone block
    `_deny_evo_via_boss` (a Boss's searched from the DECK with Meowth ex ->
    Last-Ditch). The replacement is only valid if it does NOT lose any line
    somebody hand-listed after losing a game."""
    perdidas = [cid for cid in (m.EX_PREEVO_IDS - m.NONEX_FINAL_PREEVO_IDS)
                if not m._preevo_of_ex_line(cid)]
    assert perdidas == [], [m.card_table[c].name for c in perdidas]


def test_el_helper_cubre_lineas_que_la_lista_curada_no_tenia():
    """Frillish -> Jellicent ex is in `deck/rivales/jellicent_lock.csv` and was NOT
    in `EX_PREEVO_IDS`: the curated list only grew after a loss."""
    FRILLISH = 597
    assert m.card_table[FRILLISH].name == "Frillish"
    assert FRILLISH not in m.EX_PREEVO_IDS
    assert m._preevo_of_ex_line(FRILLISH)


def test_dunsparce_no_motiva_un_gusteo_que_tiene_prohibido():
    """Dunsparce -> Dudunsparce ex culminates in an ex, but the selection handler
    ALWAYS vetoes Dunsparce as a target. A reason that points at a forbidden
    target spends (or searches for) the Boss's only to bring something else up: it is the
    Dwebble failure of log 86339758."""
    for cid in m.DUNSPARCE_IDS:
        assert m._line_ends_in_ex(cid), "la linea SI acaba en ex..."
        assert not m._preevo_of_ex_line(cid), "...pero no debe motivar el gusteo"


def test_la_cima_de_una_linea_no_culmina_en_nada():
    # A Stage 2 (or a Basic with no evolution) has nothing above it any more.
    assert not m._line_ends_in_ex(GRIMMSNARL)
    assert not m._line_ends_in_ex(HYDRAPPLE)
    assert not m._line_ends_in_ex(m.Teal_Mask_Ogerpon_ex)
    # What is not a Pokemon (or does not exist) has no line.
    assert not m._line_ends_in_ex(BOSS)
    assert not m._line_ends_in_ex(-12345)
