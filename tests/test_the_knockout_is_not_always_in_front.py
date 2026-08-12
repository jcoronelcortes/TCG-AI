"""The body that closes the game was on our bench, and it did not need the
front spot to be free of a wall -- it needed the front spot.

Scenario (user, `records/registro_014_pasos_129_hasta_131.json` step 129, turn
14 vs a Cornerstone/Ceruledge ex deck -- episode 91832930, WON with the win
thrown away three turns running). ONE prize left on our side:

    US (1 prize)                              THEM (5 prizes)
    active  Hydrapple ex  70/330, 2 en.       active  Cornerstone Mask
    bench   Meganium      160/160, 2 en.              Ogerpon ex 210/210
            Teal Mask Ogerpon ex 210, 4 en.   bench   70 HP body
            Meowth ex     170/170, 0 en.              110 HP body
            Teal Mask Ogerpon ex 210, 4 en.           110 HP body
            **Fezandipiti ex 210/210, 8 en.**         **70 HP body**
    hand    one basic Grass

Cruel Arrow does a fixed 100 to ANY of their Pokemon: either 70 HP body on their
bench is our last prize. The Fezandipiti ex was on the BENCH and its retreat
cost three symbols against the Hydrapple's two energies, so the Grass in hand
paid exactly that: Grass to the ACTIVE -> retreat -> promote the sniper -> Cruel
Arrow -> game. Played out on the real engine (`cg.api.search_begin` from this
very observation) the line ends `result = 1` on the spot.

The agent attached that Grass to the Fezandipiti ex -- which already carried
eight energies and needed three -- and then attacked the wall with Syrup Storm
for zero.

WHY NOTHING SAW IT. Three readings, all of them measuring the same wrong thing:

  * `_grass_unlocks_active_retreat`, the detector that routes an energy to the
    active to pay a retreat, asks `_bench_attacker_can_ko(..., their_active)`.
    Cruel Arrow's 100 against a Cornerstone Mask Ogerpon ex -- whose stance
    cancels every attacker of ours carrying an Ability -- reads 0, so no route
    existed and the Grass fell to the generic development band (7700, which the
    already-loaded Fezandipiti won by four ten-thousandths of a point);
  * its `active_can_attack` cut-off then closed the chip half too. Our Hydrapple
    ex COULD attack. Into the wall. For nothing. The boolean says "there is an
    ATTACK option in the menu", and that is not the same sentence as "the turn
    has something to do";
  * `_prizes_via_promote` in the turn plan reaches their bench only behind a
    Boss's Orders (`_targets`), so the plan read DEVELOP at match point.

The snipe was NOT missing from the agent -- `SNIPE_ANY_TARGET_IDS`,
`_snipe_best_target` and the DAMAGE-menu ranking have been there since
registro_004 step 54. They were only ever asked about the body ALREADY standing
in the active spot. Read from the other side of a retreat, the same question had
no answer.

FIX, deck-agnostic, three readings widened and none replaced:

  1. `_bench_snipe_best` / `_bench_snipe_can_ko` (ptcg/calc/damage.py): the best
     snipe a BENCHED body would fire once promoted, measured against their whole
     field with the Grass left after paying the retreat;
  2. `_targets(op_state, boss_in_hand, attacker)` (ptcg/turn/game_plan.py): the
     reach of an attack is a property of the ATTACKER. A sniper reaches their
     bench with nothing in hand;
  3. `_promo_kos_op` (main.py): the promotion menu asks the active question
     first and, only if it says no, the snipe question -- so a candidate that
     takes a prize is worth `PROMO_KO_BONUS` whether the prize is in front of us
     or behind it.

`_bench_attacker_can_ko` is deliberately NOT widened: its callers (the gust)
name a target and mean that target.

Measured: 0 flips in the 3 580 decisions of the frozen corpus; 11 in the local
records, all of them this same game. Replayed on the real engine, three sterile
turns (steps 129, 141 and 148) become three immediate wins and no other turn
loses a prize or a point of damage.
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

import main as m
from cg.api import OptionType, SelectContext
from ptcg.turn.game_plan import _targets

HYDRA = m.Hydrapple_ex            # 70 of 330, 2 energies, retreat cost 3
FEZ = m.Fezandipiti_ex            # 210/210, 8 energies: Cruel Arrow, 100 anywhere
OGERPON = m.Teal_Mask_Ogerpon_ex
MEOWTH = m.Meowth_ex
MEGANIUM = m.Meganium
WALL = m.Cornerstone_Mask_Ogerpon_ex   # 117: cancels our bodies with an Ability

_FIX_MAIN = (ROOT / "tests" / "fixtures"
             / "cornerstone_step129_the_sniper_waits_on_the_bench.json")
_FIX_SWITCH = (ROOT / "tests" / "fixtures"
               / "cornerstone_step129_the_promotion_after_the_retreat.json")


@pytest.fixture(autouse=True)
def reset_main_state():
    m.AGENT_STATE.reset()
    m._init_cards_tracking()
    m._cards_first_scan_done = False
    m._cards_prizes_identified = False
    m._cards_last_turn = -1
    m.plan = m.AttackPlan()
    m.pre_turn = 0
    m._prev_op_prize = 6
    yield
    m.AGENT_STATE.reset()
    m._init_cards_tracking()


def _obs(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)["observation"]


def _sides(obs):
    """(my_state, op_state) as the agent's own parser builds them."""
    state = m.to_observation_class(obs).current
    mine = state.yourIndex
    return state.players[mine], state.players[1 - mine]


def _bench(obs, card_id):
    cur = obs["current"]
    mine = cur["players"][cur["yourIndex"]]
    return next(b for b in mine["bench"] if b and b["id"] == card_id)


def _chosen(obs):
    """The option dict the agent picks on this menu."""
    o = copy.deepcopy(obs)
    action = m.agent(o)
    return [obs["select"]["option"][i] for i in action]


def _snipe_ko(my_state, op_state, grass_after=0):
    return m._bench_snipe_can_ko(my_state, op_state, True, 5, grass_after, False)


# ---------------------------------------------------------------------------
# 1. The record's board. Without it the rest of the file measures nothing.
# ---------------------------------------------------------------------------

def test_the_board_is_the_records_one():
    obs = _obs(_FIX_MAIN)
    cur = obs["current"]
    mine = cur["players"][cur["yourIndex"]]
    theirs = cur["players"][1 - cur["yourIndex"]]

    assert len(mine["prize"]) == 1, "match point: any knockout ends the game"
    assert mine["active"][0]["id"] == HYDRA
    assert len(mine["active"][0]["energies"]) == 2, (
        "two effective energies against a retreat cost of three symbols")
    assert m.RETREAT_COST[HYDRA] == 3

    sniper = _bench(obs, FEZ)
    assert len(sniper["energies"]) == 8 >= m.AGENT_STATE.ATTACK_ENERGY_REQ[FEZ], (
        "the sniper is loaded to bursting: this energy buys it NOTHING")

    assert theirs["active"][0]["id"] == WALL
    assert sorted(b["hp"] for b in theirs["bench"] if b) == [70, 70, 110, 110], (
        "two 70 HP bodies on their bench: Cruel Arrow's fixed 100 is lethal")


def test_the_retreat_is_not_legal_yet_and_the_grass_is_what_pays_it():
    """The whole family of retreat pivots switches off without this: with the
    retreat already legal a different set of rules owns the board."""
    obs = _obs(_FIX_MAIN)
    assert not any(o["type"] == OptionType.RETREAT
                   for o in obs["select"]["option"]), "no RETREAT in the menu"
    my_state, _ = _sides(obs)
    active = my_state.active[0]
    assert (len(active.energies) + m._grass_attach_unit()
            >= m.RETREAT_COST[active.id]), "one Grass completes the cost"


def test_the_active_can_attack_and_the_attack_is_worth_zero():
    """The trap that swallowed the case. `can_attack` is true -- the ATTACK
    option is right there in the menu -- and the wall makes it worth nothing."""
    obs = _obs(_FIX_MAIN)
    assert any(o["type"] == OptionType.ATTACK for o in obs["select"]["option"])

    my_state, op_state = _sides(obs)
    active, wall = my_state.active[0], op_state.active[0]
    base = m._attacker_base_damage(active.id, wall, 4, grass_scale=10,
                                   teal_self_energy=4, bench_count=5)
    assert base > 0, "Syrup Storm does reach its cost with the Grass attached"
    assert m._our_effective_damage(active, wall, base, True, False) == 0, (
        "and the Cornerstone stance cancels every body of ours with an Ability")


# ---------------------------------------------------------------------------
# 2. The reading that was missing
# ---------------------------------------------------------------------------

def test_the_benched_sniper_knocks_something_out():
    obs = _obs(_FIX_MAIN)
    my_state, op_state = _sides(obs)
    attacker, target, damage, is_ko = m._bench_snipe_best(
        my_state, op_state, True, 5, 0, False)
    assert attacker is not None and attacker.id == FEZ
    assert damage == 100 and is_ko
    assert (target.hp or 0) == 70 and target is not op_state.active[0], (
        "the prize is on their BENCH, not in front of us")


def test_the_question_asked_of_the_active_still_says_no():
    """Positive evidence that the new reading is not a rewrite of the old one:
    against the wall in front NOTHING of ours knocks out, and that answer is
    unchanged. The gust's question keeps its meaning."""
    obs = _obs(_FIX_MAIN)
    my_state, op_state = _sides(obs)
    assert not m._bench_attacker_can_ko(
        my_state, op_state.active[0], True, 10, 5, 0, False)


def test_the_detector_routes_the_grass_to_the_active():
    obs = _obs(_FIX_MAIN)
    my_state, op_state = _sides(obs)
    ko, chip = m._grass_unlocks_active_retreat(
        my_state, op_state, True, m.count_total_grass_energy(my_state), 5,
        False, active_can_attack=True)
    assert ko, "the lethal half fires even though the active CAN attack"


def test_an_attack_that_picks_its_target_reaches_their_bench():
    """The root of it, one level up: the reach of an attack is a property of the
    ATTACKER and not only of the Supporter in hand."""
    obs = _obs(_FIX_MAIN)
    my_state, op_state = _sides(obs)
    sniper = next(b for b in my_state.bench if b is not None and b.id == FEZ)
    plain = next(b for b in my_state.bench if b is not None and b.id == OGERPON)

    assert len(_targets(op_state, False)) == 1, "no Boss's: their active only"
    assert len(_targets(op_state, False, plain)) == 1, "and for a plain body"
    assert len(_targets(op_state, False, sniper)) == 5, (
        "the sniper reaches the whole field with nothing in hand")


# ---------------------------------------------------------------------------
# 3. The decisions
# ---------------------------------------------------------------------------

def test_the_energy_pays_the_retreat_instead_of_watering_the_sniper():
    obs = _obs(_FIX_MAIN)
    chosen = _chosen(obs)
    assert len(chosen) == 1 and chosen[0]["type"] == OptionType.ATTACH
    assert chosen[0]["inPlayArea"] == 4, (
        "the Grass goes to the ACTIVE (area 4) to pay its retreat, not onto the "
        "bench body that already has eight energies")


def test_the_promotion_brings_up_the_sniper():
    obs = _obs(_FIX_SWITCH)
    assert obs["select"]["context"] == SelectContext.SWITCH
    chosen = _chosen(obs)
    cur = obs["current"]
    mine = cur["players"][cur["yourIndex"]]
    promoted = mine["bench"][chosen[0]["index"]]
    assert promoted["id"] == FEZ, (
        "the front spot goes to the body that takes the last prize, not to a "
        "Teal Mask Ogerpon ex the wall has switched off")


def test_the_promotion_prices_the_sniper_as_a_knocker():
    """`PROMO_KO_BONUS` is what moves it, and it is the same +20000 any other
    body that takes a prize gets."""
    obs = _obs(_FIX_SWITCH)
    my_state, op_state = _sides(obs)
    seen = {}
    original = m.score_option

    def spy(tc, o, score):
        seen.setdefault("kos", tc._promo_kos_op)
        seen.setdefault("bench", tc.my_state.bench)
        return original(tc, o, score)

    m.score_option = spy
    try:
        m.agent(copy.deepcopy(obs))
    finally:
        m.score_option = original

    kos = {b.id: seen["kos"](b) for b in seen["bench"] if b is not None}
    assert kos[FEZ], "the sniper takes a prize"
    assert not kos[OGERPON] and not kos[MEGANIUM] and not kos[MEOWTH], (
        "and nobody else does: the wall cancels all three")


# ---------------------------------------------------------------------------
# 4. Where it stops
# ---------------------------------------------------------------------------

def test_without_a_sniper_on_the_bench_nothing_changes():
    obs = _obs(_FIX_MAIN)
    _bench(obs, FEZ)["id"] = MEOWTH        # same eight energies, no free target
    my_state, op_state = _sides(obs)
    assert not _snipe_ko(my_state, op_state)
    ko, _ = m._grass_unlocks_active_retreat(
        my_state, op_state, True, m.count_total_grass_energy(my_state), 5,
        False, active_can_attack=True)
    assert not ko, "no sniper, no route: the old answer stands"


def test_a_sniper_below_its_attack_cost_is_not_a_route():
    obs = _obs(_FIX_MAIN)
    sniper = _bench(obs, FEZ)
    sniper["energies"] = [1] * (m.AGENT_STATE.ATTACK_ENERGY_REQ[FEZ] - 1)
    sniper["energyCards"] = sniper["energyCards"][:1]
    my_state, op_state = _sides(obs)
    assert not _snipe_ko(my_state, op_state)


def test_a_snipe_that_knocks_nothing_out_is_not_a_route():
    """The chip is not the lethal half's business: with their whole field above
    100 HP the sniper still shoots, and this reading still says no."""
    obs = _obs(_FIX_MAIN)
    cur = obs["current"]
    for body in cur["players"][1 - cur["yourIndex"]]["bench"]:
        if body:
            body["hp"] = 150
    my_state, op_state = _sides(obs)
    attacker, _, damage, is_ko = m._bench_snipe_best(
        my_state, op_state, True, 5, 0, False)
    assert attacker is not None and damage == 100 and not is_ko
    assert not _snipe_ko(my_state, op_state)


def test_the_record_still_wins_when_the_file_is_there():
    """The end-to-end line on the REAL engine. `records/` is transient local
    data (rule R6 of utils/lint_architecture.py), hence the guard."""
    record = ROOT / "records" / "registro_014_pasos_129_hasta_131.json"
    if not record.exists():
        pytest.skip("registro_014 no esta en records/ (datos locales)")

    import dataclasses
    from cg import api
    import golden_corpus as gc

    def as_dict(o):
        if dataclasses.is_dataclass(o):
            return {k: as_dict(v) for k, v in dataclasses.asdict(o).items()}
        if isinstance(o, list):
            return [as_dict(v) for v in o]
        if isinstance(o, dict):
            return {k: as_dict(v) for k, v in o.items()}
        return o

    with open(record, encoding="utf-8") as f:
        data = json.load(f)
    first = next(o for pair in data["steps"] for it in pair
                 for o in [it["observation"]]
                 if o.get("select") and o["current"].get("yourIndex") == 1
                 and o["current"]["turnActionCount"] == 1)
    parsed = api.to_observation_class(first)
    me = parsed.current.players[1]
    them = parsed.current.players[0]
    gc.reset_agent(m)

    # `tests/test_cg_api.py` fakes `AgentStart` to return the integer 77, and
    # `search_begin` caches that in the MODULE GLOBAL `api.agent_ptr` --
    # monkeypatch restores `api.lib`, not the global. A real `SearchBegin`
    # later in the same session then dereferences 77 and the interpreter dies
    # with a segfault instead of a red test. Dropping the cache makes the next
    # call build a genuine agent.
    api.__dict__.pop("agent_ptr", None)
    search = api.search_begin(
        parsed, [m.Basic_Grass_Energy] * me.deckCount,
        [m.Basic_Grass_Energy] * len(me.prize), [6] * them.deckCount,
        [6] * len(them.prize), [6] * them.handCount, [])

    obs, result = first, None
    for _ in range(30):
        search = api.search_step(search.searchId, m.agent(obs))
        current = search.observation.current
        if current is not None and (current.result or -1) >= 0:
            result = current.result
            break
        if search.observation.select is None:
            break
        obs = as_dict(search.observation)
        obs["search_begin_input"] = None
        if obs["current"]["yourIndex"] != 1:
            break

    assert result == 1, (
        "the turn has to END THE GAME: attach to the active, retreat, promote "
        "the Fezandipiti ex and snipe a 70 HP body for the last prize")
