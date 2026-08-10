"""The evolution that arrives already charged, and the body we put in front of it.

Scenario (`records/registro_004_pasos_037_hasta_054.json`, the last menu of our
turn 3, episode 91522306 vs Archaludon ex -- LOST):

    US                                     RIVAL (Duraludon -> Archaludon ex)
    active  Teal Mask Ogerpon ex 180 (3 G)  active  Duraludon 130 (1 M)
    bench   Dipplin 80                      bench   Duraludon 130
            Bayleef 110                     discard 2x Basic {M} Energy
            Teal Mask Ogerpon ex 210 (1 G)
    hand    Chikorita, Hydrapple ex x2, Poke Pad x2, Grass, Unfair Stamp

Myriad Leaf Shower does not knock the Duraludon out -- the whole line is Metal
and RESISTS Grass, -30 -- so the menu offered four things and the agent picked
the one that changes nothing: ATTACK. Their turn: the Duraludon evolved into
Archaludon ex, Assemble Alloy pulled the two Metals out of their discard, and
Metal Defender took 220 damage and TWO prizes off our 210 HP Ogerpon ex.

WHY NOTHING FIRED. `_doomed_ex_sac_pivot` is built for exactly this board and
every gate of it was satisfied except the damage reading, the same failure
`test_retreat_before_the_evolution_kills_the_ex.py` records one layer down.
There the projector could not see the evolution at all; here it could, and it
still answered 0: `_op_evolution_attack_damage_to` hands the evolution the
energies the pre-evolution carries plus the one attachment of their turn -- 1 +
1 = 2 -- and Metal Defender costs three. The card that closes the gap is the
ability, not an attachment.

THE FIX, in three parts:

  * OP_EVO_ENERGY_ON_PLAY (ptcg/cards/ids.py) is the energy an evolution's
    ability attaches the moment it is played, keyed by the card that prints it.
    It is CAPPED BY THE DISCARD, because that is where Assemble Alloy takes it
    from: with an empty discard the projection stays blind, which is what keeps
    it from condemning our active on turn 1 against a board that cannot yet do
    anything;
  * the sacrifice hands over a BASIC, and if there is not one on the bench it
    puts one there. `_doomed_sac_wall_in_hand` names the body (Chikorita, then
    Applin -- the same order the promotion menu ranks with) and a PLAY envelope
    lifts it over the development veto that would otherwise leave it in hand: a
    second Chikorita with a Bayleef already in play is SCORE_VETO as
    development, and this body is not development;
  * it goes down LAST. The envelope is worth 900 and sits in its own tier
    (`_TIER_SAC_WALL`, below the energy tier), so the turn still develops, still
    dances and still attaches, and only then benches the shield and retreats.
    Left at development height it took the whole turn over.

WHAT IS NOT CHANGED: the retreat itself. `_doomed_ex_sac_pivot` only ever needed
ONE prize to go in front instead of two, so a bench holding nothing but a
Dipplin still retreats into the Dipplin. What this arranges is a BETTER body to
hand over -- and where no Basic can be arranged, the pivot behaves exactly as it
did before.
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
from cg.api import AreaType, CardType, EnergyType, OptionType, SelectContext, SelectType
from ptcg.calc.damage import _op_evolution_attack_damage_to
from tests.state_builder import Scenario, pk, G

_FIXTURE = (ROOT / "tests" / "fixtures"
            / "archaludon_t3_basic_shield_before_the_retreat_step37.json")

OGERPON = m.Teal_Mask_Ogerpon_ex
HYDRAPPLE = m.Hydrapple_ex
CHIKORITA = m.Chikorita
BAYLEEF = m.Bayleef
APPLIN = m.Applin
DIPPLIN = m.Dipplin
TAPU = m.Tapu_Bulu
DURALUDON = m.Duraludon
ARCHALUDON = m.Archaludon_ex
METAL = int(EnergyType.METAL)
METAL_ENERGY = 8            # Basic {M} Energy, the card Assemble Alloy attaches


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
    m.op_is_starmie_deck = False
    m._field_at_turn_start = {}
    m._poke_pad_target_id = 0
    m._ub_meowth_pending = False
    m._ub_fez_pending = False
    m._ld_supp_comprometido = 0
    m._dodge_immune_serial = None
    m._dodge_immune_turn = -1
    yield
    m._init_cards_tracking()


def _obs_fixture():
    """The record's board, with the ability budget of that turn already spent.

    `_grass_attaches_this_turn` is an ACCUMULATOR the agent fills observation by
    observation, and the fixture is a single frame from the middle of a turn: on
    a cold start it reads 0, the plan believes Teal Dance is still available, and
    `prizes_today` claims the knockout that one extra energy would buy. Replaying
    our whole turn 3 from `records/` leaves it at 3 (one manual attachment and
    two dances), which is the board the agent really faced -- and the menu of the
    record proves it, because it offers no ability at all. Same device, and for
    the same reason, as `_grass_attaches_this_turn = 4` in
    tests/test_fez_cruel_arrow_finishes_the_bench.py.
    """
    obs = copy.deepcopy(json.load(open(_FIXTURE, encoding="utf-8"))["observation"])
    m.AGENT_STATE.pre_turn = obs["current"]["turn"]   # we are MID-turn, not opening it
    m.AGENT_STATE._grass_attaches_this_turn = 3
    return obs


def _chosen(obs):
    o = obs["select"]["option"][m.agent(copy.deepcopy(obs))[0]]
    return o.get("type"), o


def _play_it(obs, opt, idx):
    """Apply a PLAY the agent chose, so the next decision sees the new bench."""
    cur = obs["current"]
    mine = cur["players"][cur["yourIndex"]]
    card = mine["hand"][opt["index"]]
    data = m.card_table[card["id"]]
    mine["hand"] = [c for i, c in enumerate(mine["hand"]) if i != opt["index"]]
    mine["handCount"] = len(mine["hand"])
    mine["bench"] = list(mine["bench"]) + [{
        "id": card["id"], "serial": card["serial"], "playerIndex": cur["yourIndex"],
        "hp": data.hp, "maxHp": data.hp, "appearThisTurn": True,
        "energies": [], "energyCards": [], "tools": [], "preEvolution": []}]
    obs["select"]["option"] = [o for i, o in enumerate(obs["select"]["option"])
                               if i != idx]
    for o in obs["select"]["option"]:
        if o.get("type") == int(OptionType.PLAY) and o.get("index", 0) > opt["index"]:
            o["index"] -= 1
    return card["id"]


def _walk(obs, max_steps=5):
    """(types chosen, ids played), applying each PLAY before asking again."""
    obs = copy.deepcopy(obs)
    types, played = [], []
    for _ in range(max_steps):
        idx = m.agent(copy.deepcopy(obs))[0]
        opt = obs["select"]["option"][idx]
        types.append(int(opt["type"]))
        if int(opt["type"]) != int(OptionType.PLAY):
            break
        played.append(_play_it(obs, opt, idx))
    return types, played, obs


def _promotion_menu(obs):
    """The SWITCH prompt the simulator emits right after paying the retreat."""
    promo = copy.deepcopy(obs)
    cur = promo["current"]
    mine = cur["players"][cur["yourIndex"]]
    cur["retreated"] = True
    act = mine["active"][0]
    if act["energyCards"]:                      # the fee is already in the discard
        mine["discard"] = list(mine["discard"]) + [act["energyCards"][0]]
        act["energyCards"] = act["energyCards"][1:]
        act["energies"] = act["energies"][1:]
    promo["select"] = {
        "type": int(SelectType.CARD), "context": int(SelectContext.SWITCH),
        "minCount": 1, "maxCount": 1, "remainDamageCounter": 0,
        "remainEnergyCost": 0, "deck": None, "contextCard": None, "effect": None,
        "option": [{"type": int(OptionType.CARD), "area": int(AreaType.BENCH),
                    "index": k, "playerIndex": cur["yourIndex"]}
                   for k in range(len(mine["bench"]))]}
    idx = m.agent(copy.deepcopy(promo))[0]
    return mine["bench"][promo["select"]["option"][idx]["index"]]["id"]


# ---------------------------------------------------------------------------
# 1. The projection: the evolution brings its own energy, out of the discard
# ---------------------------------------------------------------------------

def _duraludon(energies=(METAL,)):
    return m._ProjTarget(DURALUDON, (), tuple(energies))


def _metal_energy_cards(n):
    return [m.Card(id=METAL_ENERGY, playerIndex=0, serial=900 + i)
            for i in range(n)]


def test_the_duraludon_alone_does_not_reach_metal_defender():
    """One Metal plus their attachment is two, and the attack costs three: the
    reading the agent had, and it is right about the energy on the board."""
    assert _op_evolution_attack_damage_to(
        _duraludon(), m._ProjTarget(OGERPON)) == 0


def test_two_metals_in_their_discard_turn_it_into_a_finisher():
    """Assemble Alloy attaches up to two Basic {M} out of the discard the moment
    Archaludon ex is played to evolve: 1 + 2 + their attachment covers the cost
    and Metal Defender prints 220, over the 210 HP of a Teal Mask Ogerpon ex."""
    assert _op_evolution_attack_damage_to(
        _duraludon(), m._ProjTarget(OGERPON),
        op_discard=_metal_energy_cards(2)) >= 210


def test_an_empty_discard_credits_nothing():
    """The ability takes the energy FROM the discard, so on their first turns it
    brings none -- and a projection that credited it anyway would condemn our
    active from turn 1 against a board that cannot do anything yet."""
    assert _op_evolution_attack_damage_to(
        _duraludon(), m._ProjTarget(OGERPON), op_discard=[]) == 0


def test_one_metal_in_the_discard_is_still_not_enough():
    """The credit is capped by what is really there: 1 carried + 1 recovered +
    1 attached is three, which pays Metal Defender -- and with a Grass energy in
    that discard instead it would not, which is the next test."""
    assert _op_evolution_attack_damage_to(
        _duraludon(), m._ProjTarget(OGERPON),
        op_discard=_metal_energy_cards(1)) >= 210


def test_the_wrong_energy_type_in_the_discard_credits_nothing():
    """Assemble Alloy names Basic {M}: a discard full of Grass is not fuel."""
    grass = [m.Card(id=m.Basic_Grass_Energy, playerIndex=0, serial=900)
             for _ in range(4)]
    assert _op_evolution_attack_damage_to(
        _duraludon(), m._ProjTarget(OGERPON), op_discard=grass) == 0


def test_the_reading_is_not_asked_of_a_final_stage():
    """Archaludon ex has nothing to become, so the max() every caller takes
    costs nothing where there is no line left to read."""
    archaludon = m._ProjTarget(ARCHALUDON, (), (METAL, METAL, METAL))
    assert _op_evolution_attack_damage_to(
        archaludon, m._ProjTarget(OGERPON),
        op_discard=_metal_energy_cards(2)) == 0


# ---------------------------------------------------------------------------
# 2. The record: the Chikorita goes down, the ex retreats, the Chikorita goes up
# ---------------------------------------------------------------------------

def test_the_fixture_is_the_turn_that_was_lost():
    o = _obs_fixture()
    cur = o["current"]
    mine = cur["players"][cur["yourIndex"]]
    theirs = cur["players"][1 - cur["yourIndex"]]

    assert mine["active"][0]["id"] == OGERPON
    assert mine["active"][0]["hp"] == 180
    assert len(mine["active"][0]["energies"]) == 3          # it CAN attack
    assert theirs["active"][0]["id"] == DURALUDON
    assert sum(1 for c in theirs["discard"] if c["id"] == METAL_ENERGY) == 2
    assert sorted(b["id"] for b in mine["bench"]) == sorted(
        [DIPPLIN, BAYLEEF, OGERPON])
    assert not any(b["id"] == CHIKORITA for b in mine["bench"])
    assert CHIKORITA in [c["id"] for c in mine["hand"]]
    types = [op["type"] for op in o["select"]["option"]]
    assert int(OptionType.ATTACK) in types and int(OptionType.RETREAT) in types


def test_it_benches_the_chikorita_and_retreats_instead_of_attacking():
    """The regression of the record, end to end: it used to ATTACK for 90 into
    a 130 HP body and leave a two-prize ex in front of the evolution."""
    types, played, _ = _walk(_obs_fixture())
    assert played[:1] == [CHIKORITA], f"no bajo el escudo: {played}"
    assert int(OptionType.RETREAT) in types, f"no se retiro: {types}"
    assert int(OptionType.ATTACK) not in types, (
        f"ataco con el ex condenado sin noquear: {types}")


def test_the_body_it_hands_over_is_the_chikorita_and_not_half_a_line():
    """The point of benching it: with the record's bench the sacrifice would
    otherwise be a Dipplin or a Bayleef, each of them half of one of the two
    lines the deck attacks with."""
    _, _, after = _walk(_obs_fixture())
    assert _promotion_menu(after) == CHIKORITA


def _play_score(obs, card_id):
    """The score the chain gives the PLAY of `card_id` in this menu."""
    cur = obs["current"]
    mine = cur["players"][cur["yourIndex"]]
    seen = {}
    original = m.score_option

    def spy(tc, o, score):
        result = original(tc, o, score)
        if o.type == OptionType.PLAY and mine["hand"][o.index]["id"] == card_id:
            seen["score"] = result
        return result

    m.score_option = spy
    try:
        m.agent(copy.deepcopy(obs))
    finally:
        m.score_option = original
    return seen.get("score")


def test_the_shield_is_lifted_by_the_envelope_and_not_by_development():
    """The mechanism, not just the choice. A second Chikorita with a Bayleef
    already in play is SCORE_VETO as development (the Meganium-line cap), so
    what puts it on the board is the envelope -- and the envelope is worth 900,
    not the 21600 of its two siblings. That number is what keeps the shield in
    `_TIER_SAC_WALL` instead of `_TIER_DEVELOP`; with the development height the
    golden corpus caught it reordering three earlier decisions of this same
    turn, going down before the second Ogerpon ex, before Teal Dance and before
    the attachment."""
    assert _play_score(_obs_fixture(), CHIKORITA) == m.DOOMED_SAC_WALL_PLAY_SCORE


# ---------------------------------------------------------------------------
# 3. The boundaries
# ---------------------------------------------------------------------------

def _board(my_bench, hand, op_discard_metals=2):
    """The record's shape, parameterised: our doomed ex in front of a charged
    Duraludon whose discard holds the fuel of Assemble Alloy."""
    return (Scenario(turn=3, step=37, tac=16, first_player=0,
                     energy_played=True, supporter_played=True)
            .my_active(pk(OGERPON, hp=180, energies=[G, G, G]))
            .my_bench(*[b if isinstance(b, dict) else pk(b) for b in my_bench])
            .my_hand(*hand)
            .op_active(pk(DURALUDON, energies=[METAL]))
            .op_discard(*([METAL_ENERGY] * op_discard_metals))
            .op_zones(hand=7, deck=30, prizes=6)
            .menu_hand(with_retreat=True, with_attack=True)
            .build())


def test_with_no_basic_to_arrange_the_pivot_behaves_exactly_as_before():
    """The user's fallback, and the line this change deliberately does not
    cross: with no Basic anywhere the retreat still happens -- one prize in
    front instead of two was always the whole point of `_doomed_ex_sac_pivot`
    -- and the body handed over is the one-prize one the bench does have."""
    types, played, _ = _walk(_board([DIPPLIN, BAYLEEF], [HYDRAPPLE]))
    assert int(OptionType.RETREAT) in types, types
    assert int(OptionType.ATTACK) not in types, types


def test_an_empty_opposing_discard_leaves_the_turn_as_it_was():
    """The control for the whole chain: the same board, the same hand, and the
    only thing that moves is whether Assemble Alloy has anything to attach.
    Without fuel the evolution does not reach Metal Defender, nothing is doomed,
    and the agent attacks as it always did."""
    types, played, _ = _walk(_board([DIPPLIN, BAYLEEF], [HYDRAPPLE],
                                    op_discard_metals=0))
    assert int(OptionType.ATTACK) in types, types
    assert int(OptionType.RETREAT) not in types, types
    assert CHIKORITA not in played


def test_a_ready_attacker_on_the_bench_is_not_a_sacrifice_board():
    """`_bench_attacker_ready`: with a body that can attack there is a better
    plan than handing a corpse over, so no sacrifice is arranged and the turn
    does not end in a retreat."""
    types, _, _ = _walk(_board([DIPPLIN, pk(OGERPON, energies=[G, G, G])],
                               [HYDRAPPLE]))
    assert int(OptionType.RETREAT) not in types, types


# ---------------------------------------------------------------------------
# 4. The middle rung of the ladder: the search that buys the body
# ---------------------------------------------------------------------------

def test_the_poke_pad_goes_and_gets_the_shield_when_there_is_none():
    """"...or one we can search for with a Poke Pad or a Bug Catching Set"
    (user). The PLAY side: with the sacrifice asking for a body and none on the
    board, the Poke Pad names one, in the sacrifice order."""
    from ptcg.decision.poke_pad import _pp_doomed_sac_target
    from ptcg.state.zones import ZONE_DECK

    class _Ctx:
        cards_in_deck = {APPLIN: {ZONE_DECK: 2}, CHIKORITA: {ZONE_DECK: 2}}
        field_counts = {}
        hand_counts = {}
        bench_count = 1
        doomed_sac_needs_body = True

    assert _pp_doomed_sac_target(_Ctx) == CHIKORITA
    # With a Chikorita already in play the search moves down the same order...
    _Ctx.field_counts = {CHIKORITA: 1}
    assert _pp_doomed_sac_target(_Ctx) == APPLIN
    # ...and it stays silent when the sacrifice is not asking for anything.
    _Ctx.doomed_sac_needs_body = False
    assert _pp_doomed_sac_target(_Ctx) is None


def test_the_fetch_menu_follows_the_same_sacrifice_order():
    """The fetch is a different decision, with a different context object, so
    the order is stated twice and the two statements have to agree -- including
    the absence of Tapu Bulu, which the OPENING order heads and this one does
    not name at all: this menu is picking a body to lose."""
    from ptcg.decision.poke_pad import _CtxPPFetch, _RULES_PP_FETCH
    from ptcg.engine.rules import _resolve_with_trace

    class _State:
        turn = 3

    def _score(card_id, needs_body=True):
        return _resolve_with_trace(
            "pp->fetch", _RULES_PP_FETCH, [],
            _CtxPPFetch(card_id, {}, {}, 1, _State,
                        doomed_sac_needs_body=needs_body),
            default=10)

    assert _score(CHIKORITA) > _score(APPLIN) > _score(TAPU)
    assert _score(CHIKORITA) > _score(CHIKORITA, needs_body=False)
