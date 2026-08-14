"""What every slice of the main.py regression log needs.

`tests/test_main.py` grew into 9 500 lines: one file holding the regression
history of `main.py`, a fixture and a test per mistake the agent has made. It
reads badly at that size and it reviews worse, so it is split into slices --
`test_main_units.py` for the helper unit tests, and `test_main_regressions_N.py`
for the scenarios.

The split is CHRONOLOGICAL, not thematic, because the file is chronological:
tests were appended as games were lost. Grouping them by matchup would mean
reordering them, and the order is itself information -- neighbouring tests
usually come from the same session and explain each other.

What lives here is what more than one slice needs: the agent module, the state
reset that runs before every test, the two builders, and the handful of
fixtures and helpers that are shared across slices.
"""

import sys

from pathlib import Path

import types

from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import main as m

from patching import patch_name, instalar

from cg.api import AreaType, EnergyType, LogType, OptionType, SelectContext

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
    m._ld_supp_comprometido = 0
    m._dodge_immune_serial = None
    m._dodge_immune_turn = -1
    m._op_prize_denial_pecharunt = False
    m._op_prize_denial_gengar = False
    m.AGENT_STATE.setup_active_id = None
    yield
    m._init_cards_tracking()

def make_pokemon(card_id, *, hp=100, max_hp=100, energies=None, pre_evolution=None, energy_cards=None, tools=None):
    return SimpleNamespace(
        id=card_id,
        hp=hp,
        maxHp=max_hp,
        energies=list(energies or []),
        preEvolution=list(pre_evolution or []),
        energyCards=list(energy_cards or []),
        tools=list(tools or []),
    )

def make_card(card_id, name="Card"):
    return SimpleNamespace(id=card_id, name=name)

import copy

import json

def _resolve_play_options(obs_dict):
    """Returns {position_in_option: card_id} for the PLAY options (type 7)."""
    obs = m.to_observation_class(obs_dict)
    my_index = obs_dict["current"]["yourIndex"]
    mapping = {}
    for i, opt in enumerate(obs_dict["select"]["option"]):
        if opt.get("type") == OptionType.PLAY:
            card = m.get_card(obs, AreaType.HAND, opt["index"], my_index)
            mapping[i] = None if card is None else card.id
    return mapping

def _resolve_search_options(obs_dict):
    """{position_in_option: card_id} for deck search options."""
    deck = obs_dict["select"].get("deck") or []
    mapping = {}
    for i, opt in enumerate(obs_dict["select"]["option"]):
        if opt.get("type") == int(OptionType.CARD) and opt.get("area") == int(AreaType.DECK):
            di = opt.get("index")
            if di is not None and di < len(deck):
                mapping[i] = deck[di]["id"]
    return mapping

def _make_boss_ctx(**overrides):
    base = dict(
        state=SimpleNamespace(supporterPlayed=False, turn=6, energyAttached=False),
        my_state=SimpleNamespace(discard=[], active=[None], bench=[], hand=[]),
        op_state=SimpleNamespace(active=[None], bench=[]),
        hand_counts={m.Boss_Orders: 1},
        field_counts={},
        supp_values={m.Boss_Orders: 700},
        cards_in_deck={},
        field_at_turn_start={},
        bench_count=0,
        my_hand_len=5,
        my_prize=6,
        op_prize=6,
        op_hand_count=6,
        meganium_in_play=False,
        forest_in_play=False,
        itchy_pollen_active=False,
        has_hydrapple=False,
        watchtower_in_play=False,
        meowth_ability_lock=False,
        neutralization_zone_active=False,
        mega_line_active=False,
        active_needs_energy=False,
        evolve_possible_in_play=False,
        energy_starved_low_draw=False,
        pp_playable_in_hand=False,
        can_attack=False,
        best_supp_in_hand_val=0,
        best_supp_in_deck_val=0,
        op_is_alakazam_deck=False,
        op_is_hop_deck=False,
        op_is_comfey_deck=False,
        op_active_is_dunsparce=False,
        op_has_ability_immune_active=False,
        op_has_ex_immune_active=False,
        op_has_ex_immune_bench=False,
        op_is_control_deck=False,
        op_is_slowking_deck=False,
        op_is_gardevoir_deck=False,
        op_is_zoroark_deck=False,
        op_is_aggro_deck=False,
        op_is_beedrill_deck=False,
        op_is_crustle_deck=False,
        op_is_cornerstone_deck=False,
        op_is_fire_deck=False,
        op_is_mirror=False,
        op_kang_ko_target=False,
        stadium_id=0,
        ko_last_turn=False,
        our_first_turn=False,
        active_cant_attack=False,
        bdg_retreat_ko=False,
        supporter_boost=0,
        we_go_first=False,
        budew_op_index=-1,
        budew_on_op_field=False,
        lucario_sac_pivot=False,
        win_via_boss_gust=False,
        gust_2prize_via_boss=False,
        boss_win_via_bench=False,
        boss_dodge_redirect=False,
        boss_defensive_gust=False,
        boss_deny_alakazam_line=False,
        boss_low_value_gust=False,
        boss_prize_rank=0,
        boss_ko_threat_preevo=False,
        has_ready_bench_attacker=True,
        active_ko_likely=False,
    )
    base.update(overrides)
    # `hand_counts`/`field_counts` in production are defaultdict(int); the scorers
    # use bracket access (e.g. hand_counts[Basic_Grass_Energy],
    # field_counts[Chikorita]). We coerce them so that the test context
    # behaves the same.
    from collections import defaultdict
    base["hand_counts"] = defaultdict(int, base["hand_counts"])
    base["field_counts"] = defaultdict(int, base["field_counts"])
    return m.DecisionContext(**base)

import copy as _copy

import json as _json

_ZONE_PROMOTE_FIXTURE = ROOT / "tests" / "fixtures" / "zone_promote_nonex_not_ex_active.json"

_XEROSIC_BIGHAND_FIXTURE = (
    ROOT / "tests" / "fixtures" / "alakazam_play_xerosic_bighand.json")

_GARCHOMP_BOSS_GABITE_FIXTURE = (
    ROOT / "tests" / "fixtures"
    / "garchomp_step82_boss_gust_energized_gabite.json")

_GARCHOMP_MEOWTH_DENY_EVO_FIXTURE = (
    ROOT / "tests" / "fixtures"
    / "garchomp_step82_meowth_boss_deck_deny_evo.json")

def _garchomp_meowth_deny_replay(mutate=None):
    import copy as _c
    with open(_GARCHOMP_MEOWTH_DENY_EVO_FIXTURE, encoding="utf-8") as f:
        data = json.load(f)
    seq = data["sequence"]
    for item in seq[:-1]:
        m.agent(item["observation"])
    obs = seq[-1]["observation"]
    if mutate is not None:
        obs = _c.deepcopy(obs)
        mutate(obs)
    return m.agent(obs), obs, data

def _played_meowth(obs, result):
    opt = obs["select"]["option"][result[0]]
    hand = [c["id"] for c in obs["current"]["players"][1]["hand"]]
    return (opt.get("type") == int(OptionType.PLAY)
            and opt.get("index", -1) < len(hand)
            and hand[opt["index"]] == m.Meowth_ex)

_LUCARIO_RIPEN_FIXTURE = (
    ROOT / "tests" / "fixtures"
    / "lucario_step113_ripening_active_over_bench_td.json")

def _lucario_ripen_data():
    with open(_LUCARIO_RIPEN_FIXTURE, encoding="utf-8") as f:
        return json.load(f)

_ALAKAZAM_S85_FIXTURE = (
    ROOT / "tests" / "fixtures" / "alakazam_step85_xerosic_sobre_boss.json")

def _alakazam_s85_replay(observation_key=None):
    with open(_ALAKAZAM_S85_FIXTURE, encoding="utf-8") as f:
        data = json.load(f)
    seq = data["sequence"]
    for item in seq[:-1]:
        m.agent(item["observation"])
    obs = data[observation_key] if observation_key else seq[-1]["observation"]
    return m.agent(obs), obs, data

def _played_card(obs, result):
    opt = obs["select"]["option"][result[0]]
    if opt.get("type") != int(OptionType.PLAY):
        return None
    hand = obs["current"]["players"][obs["current"]["yourIndex"]]["hand"]
    return hand[opt["index"]]["id"]

def spend_the_supporter_slot(obs, card_id):
    """The SAME board one action later, with `card_id` already played as the
    turn's Supporter: the card leaves the hand, its option leaves the menu and
    `supporterPlayed` goes up.

    The net of `finalizar` reorders rather than replaces -- a Supporter whose
    slot is about to expire is played BEFORE the attack that closes the turn,
    and the attack fires on the next menu. A test whose claim is about the
    ATTACK therefore has to ask on the menu where the reorder is already done,
    or it is pinning the order of two plays instead of the claim it was written
    for. See `OP_HAND_PRICED_PLAY_IDS`.
    """
    nxt = copy.deepcopy(obs)
    cur = nxt["current"]
    hand = cur["players"][cur["yourIndex"]]["hand"]
    gone = next(i for i, c in enumerate(hand) if c["id"] == card_id)
    del hand[gone]
    cur["players"][cur["yourIndex"]]["handCount"] = len(hand)
    cur["supporterPlayed"] = True
    menu = []
    for o in nxt["select"]["option"]:
        if o.get("type") != int(OptionType.PLAY):
            menu.append(o)
            continue
        if o["index"] == gone:
            continue
        o = dict(o)
        if o["index"] > gone:
            o["index"] -= 1
        menu.append(o)
    nxt["select"]["option"] = menu
    return nxt

_FOREST_DISCARD_FIXTURE = (
    ROOT / "tests" / "fixtures" / "cubchoo_step61_protect_forest_forced_discard.json")

_ULTRA_BALL = 1121

def _load_lucario_step99_obs():
    import json as _json
    return _json.load(open(
        ROOT / "tests" / "fixtures" /
        "lucario_step99_promote_survivor_tank_not_ogerpon.json",
        encoding="utf-8"))["observation"]

def _promote_choice_id(obs):
    me = obs["current"]["players"][obs["current"]["yourIndex"]]
    m._init_cards_tracking()
    m.plan = m.AttackPlan()
    dec = m.agent(obs)
    opt = obs["select"]["option"][dec[0]]
    return me["bench"][opt["index"]]["id"]

def _reset_state_record_008():
    m._init_cards_tracking()
    m._cards_first_scan_done = False
    m._cards_last_turn = -1
    m._prev_op_prize = 6
    m._ko_detected_this_turn = False
    m.plan = m.AttackPlan()

__all__ = [
    'sys',
    'Path',
    'types',
    'SimpleNamespace',
    'pytest',
    'ROOT',
    'm',
    'instalar',
    'patch_name',
    'AreaType',
    'EnergyType',
    'LogType',
    'OptionType',
    'SelectContext',
    'reset_main_state',
    'spend_the_supporter_slot',
    'make_pokemon',
    'make_card',
    'copy',
    'json',
    '_resolve_play_options',
    '_resolve_search_options',
    '_make_boss_ctx',
    '_copy',
    '_json',
    '_ZONE_PROMOTE_FIXTURE',
    '_XEROSIC_BIGHAND_FIXTURE',
    '_GARCHOMP_BOSS_GABITE_FIXTURE',
    '_GARCHOMP_MEOWTH_DENY_EVO_FIXTURE',
    '_garchomp_meowth_deny_replay',
    '_played_meowth',
    '_LUCARIO_RIPEN_FIXTURE',
    '_lucario_ripen_data',
    '_ALAKAZAM_S85_FIXTURE',
    '_alakazam_s85_replay',
    '_played_card',
    '_FOREST_DISCARD_FIXTURE',
    '_ULTRA_BALL',
    '_load_lucario_step99_obs',
    '_promote_choice_id',
    '_reset_state_record_008',
]
