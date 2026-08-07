"""Festival Grounds + Dipplin: the opponent ATTACKS TWICE, so the promoted body
has to reach our turn alive.

Scenario (log 88971843, step 117, turn 9, LOST vs *Festival Lead*):

    US (3 prizes)                        OPPONENT (**1 prize**)
    active  -- (they have just knocked   active  Dipplin 80 HP, 1 Grass,
            out our Teal Mask Ogerpon ex)        **Brave Bangle**
    bench   Meganium  160 HP, 0 en       bench   5 Pokémon
            Dipplin    80 HP, 2 en       stadium **Festival Grounds** (theirs)
            Chikorita  70 HP, 0 en
            Tapu Bulu 140 HP, 2 en

*Do the Wave* = 20 x THEIR bench = **20x5 = 100**; +30 from *Brave Bangle* against
our ex = 130, which is what finished off the Ogerpon ex at 70 HP (log: `-130`).
And *Festival Lead* -- "if the first attack knocks out, attack **again** after choosing
the new Active" -- gives them a second *Do the Wave* of 100 **before we
play**. With the opponent at 1 prize, any body that dies there loses
the game.

The agent brought up the **80 HP Dipplin** (it dies to the 100) with a
**140 HP Tapu Bulu** behind it that survives and that, with a single attachment (x2 from *Wild
Growth*), reaches 4 energies and finishes with *Wood Hammer* 220.

Three chained blind spots, all three corrected here:

1. *Do the Wave* has **printed damage 0** in `attack_table` (it is "20x"), so
   `_op_active_attack_damage_to` projected **0** against the four candidates and
   the whole survival machinery (`_promo_survives`, the caution in
   `_pb_key`, `_ev_survivor_asis`, `_ko_prefer_basic_general`) switched off in
   silence. It is the same hole that was already plugged for *Powerful Hand*; now the
   scale travels in the per-turn flag `_op_bench_count`.
2. **Brave Bangle** (+30 to the active ex, a bearer without a Rule Box) was invisible:
   only Maximum Belt was modelled.
3. The promotion branch is written on the premise *"promotion happens on the
   OPPONENT'S turn, where nobody attacks any more"*. Under Festival Lead that is **false**:
   `op_double_attack_pending` switches it off -- the doomed body stops being a candidate for
   "best attacker" and loses the two exemptions (`PROMO_KO_BONUS` and the guaranteed
   finisher of `_promote_setup_ko_attacker`).

On top of that, `_promo_kos_op` projected the PROMOTED body's *Do the Wave* with the bench
not discounting its own body (20x4 = 80 instead of 20x3 = 60): it believed the Dipplin
knocked out the opposing 80 HP Dipplin and handed it `PROMO_KO_BONUS`. The other two
places that project a promoted body already subtracted 1.
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

_FIXTURE = (ROOT / "tests" / "fixtures"
            / "festival_lead_promover_tapu_no_dipplin_step117.json")

MEGANIUM = m.Meganium
DIPPLIN = m.Dipplin
CHIKORITA = m.Chikorita
TAPU = m.Tapu_Bulu
OGERPON = m.Teal_Mask_Ogerpon_ex


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
    m._op_bench_count = 0
    m._festival_grounds_in_play = False
    yield
    m._init_cards_tracking()


def _obs(**mut):
    o = copy.deepcopy(json.load(open(_FIXTURE, encoding="utf-8"))["observation"])
    yo = o["current"]["yourIndex"]
    if mut.get("without_stadium"):
        # The same board WITHOUT Festival Grounds: with no stadium there is no Festival
        # Lead and the second attack does not exist.
        o["current"]["stadium"] = []
    if mut.get("rival_sin_bangle"):
        o["current"]["players"][1 - yo]["active"][0]["tools"] = []
    return o


def _bench(obs):
    yo = obs["current"]["yourIndex"]
    return obs["current"]["players"][yo]["bench"]


def _elegido(obs, choice):
    """The bench card matching the chosen option."""
    opt = obs["select"]["option"][choice[0]]
    return _bench(obs)[opt["index"]]


# ---------------------------------------------------------------------------
# 1. The scenario: without it, the test measures nothing
# ---------------------------------------------------------------------------

def test_the_fixture_is_the_promotion_under_festival_grounds():
    o = _obs()
    yo = o["current"]["yourIndex"]
    mio = o["current"]["players"][yo]
    opponent = o["current"]["players"][1 - yo]

    assert not mio["active"]                       # they knocked out our active
    assert o["select"]["context"] == 4             # promotion menu

    # Festival Grounds on the table -- and it is the OPPONENT'S: the stadium is SHARED.
    assert [c["id"] for c in o["current"]["stadium"]] == [m.Festival_Grounds]
    assert o["current"]["stadium"][0]["playerIndex"] == 1 - yo

    # Their active is the Dipplin with Festival Lead and Brave Bangle.
    assert opponent["active"][0]["id"] == DIPPLIN
    assert DIPPLIN in m.FESTIVAL_LEAD_IDS
    assert [t["id"] for t in opponent["active"][0]["tools"]] == [m.Brave_Bangle]
    assert not m._tiene_rule_box(DIPPLIN)          # the Bangle DOES apply to it

    # Opponent at MATCH POINT: one more KO and we lose.
    assert len(opponent["prize"]) == 1

    # The bench: two that survive 100 (Meganium, Tapu) and two that do not.
    assert [(b["id"], b["hp"]) for b in mio["bench"]] == [
        (MEGANIUM, 160), (DIPPLIN, 80), (CHIKORITA, 70), (TAPU, 140)]
    assert len(opponent["bench"]) == 5                # Do the Wave = 20 x 5 = 100


def test_do_the_wave_has_zero_printed_damage():
    """The root cause: without modelling it, the projection was 0 against everyone."""
    assert (m.attack_table[m.DO_THE_WAVE_ATTACK_ID].damage or 0) == 0
    assert m.card_table[DIPPLIN].attacks == [m.DO_THE_WAVE_ATTACK_ID]


# ---------------------------------------------------------------------------
# 2. The damage projection
# ---------------------------------------------------------------------------

def test_it_projects_do_the_wave_and_the_brave_bangle():
    obs = _obs()
    m.agent(obs)                                   # it refreshes the per-turn flags
    assert m._op_bench_count == 5
    assert m._festival_grounds_in_play is True

    yo = obs["current"]["yourIndex"]
    op_act = m.to_observation_class(obs).current.players[1 - yo].active[0]

    # 20 x 5 = 100 against any NON-ex body...
    for pk in m.to_observation_class(obs).current.players[yo].bench:
        if pk.id not in m.OUR_EX_IDS:
            assert m._op_active_attack_damage_to(op_act, pk) == 100

    # ...and 130 against an ex of ours (Brave Bangle +30), which is the REAL blow
    # that finished off the Teal Mask Ogerpon ex (log: value -130).
    assert m._op_active_attack_damage_to(op_act, m._ProjTarget(OGERPON)) == 130

    # Without the Bangle it is 100 again, also against the ex.
    obs2 = _obs(rival_sin_bangle=True)
    m.agent(obs2)
    op_act2 = m.to_observation_class(obs2).current.players[1 - yo].active[0]
    assert m._op_active_attack_damage_to(op_act2, m._ProjTarget(OGERPON)) == 100


def test_brave_bangle_does_not_add_if_the_bearer_has_a_rule_box():
    """The tool only counts if the bearer has NO Rule Box."""
    assert m._tiene_rule_box(OGERPON) is True      # Pokemon ex
    assert m._tiene_rule_box(TAPU) is False
    assert m._tiene_rule_box(MEGANIUM) is False


# ---------------------------------------------------------------------------
# 3. The decision
# ---------------------------------------------------------------------------

def test_it_promotes_the_tapu_that_survives_not_the_doomed_dipplin():
    obs = _obs()
    chosen = _elegido(obs, m.agent(obs))
    assert chosen["id"] == TAPU, (
        "bajo Festival Lead el promovido come un Do the Wave ANTES de que "
        "juguemos: el Dipplin de 80 PV muere y con el rival a 1 premio eso es "
        "la partida")
    assert chosen["hp"] > 100                     # it survives the second blow


def test_the_promoted_tapu_finishes_next_turn():
    """It is not just the tankiest: with one attachment it reaches Wood Hammer."""
    obs = _obs()
    yo = obs["current"]["yourIndex"]
    tapu = next(b for b in _bench(obs) if b["id"] == TAPU)
    opponent_act_id = obs["current"]["players"][1 - yo]["active"][0]

    # Meganium in play -> Wild Growth: one physical Grass is worth 2 effective.
    assert any(b["id"] == MEGANIUM for b in _bench(obs))
    assert len(tapu["energies"]) + 2 >= m.ATTACK_ENERGY_REQ[TAPU]
    assert 220 >= opponent_act_id["hp"]                  # Wood Hammer finishes it


# ---------------------------------------------------------------------------
# 4. The counter-stadium: Forest of Vitality switches Festival Lead off at the root
# ---------------------------------------------------------------------------

def test_festival_grounds_makes_the_counter_stadium_urgent():
    """`_counter_stadium_urgent` governs BOTH faces: not letting the Forest go in
    a forced discard and not vetoing its play."""
    # A hostile stadium and no Forest of ours on the table -> urgent.
    assert m._counter_stadium_urgent(False, False, False, True) is True
    # With our Forest already on the table there is nothing to put up.
    assert m._counter_stadium_urgent(False, False, True, True) is False
    # Without the opposing Applin/Dipplin line the flag arrives switched off: the stadium is
    # DOUBLE-EDGED and removing it would also switch off our Dipplin.
    assert m._counter_stadium_urgent(False, False, False, False) is False
    # It does not break the two siblings that were already there.
    assert m._counter_stadium_urgent(True, False, False, False) is True
    assert m._counter_stadium_urgent(False, True, False, False) is True


def test_switching_off_festival_lead_comes_before_the_evolution_chain():
    """The priority of playing the Forest: the chain is cashed in next turn,
    the double attack kills us on this one. Below the Meowth engine, which on top of that
    is irreversible."""
    names = [r.name for r in m._RULES_FOREST_PLAY]
    assert names.index("revive_the_meowth_engine_vs_watchtower") \
        < names.index("switch_off_festival_lead") \
        < names.index("enables_the_evolution_chain") \
        < names.index("replace_the_opponent_stadium")


def test_the_hostile_flag_needs_the_opponent_line():
    """The fixture has an opposing Dipplin in the active spot -> hostile. With no
    Applin/Dipplin of theirs in sight, the stadium stops counting as hostile."""
    o = _obs()
    yo = o["current"]["yourIndex"]
    riv = o["current"]["players"][1 - yo]
    assert riv["active"][0]["id"] == DIPPLIN

    # With no opposing line in sight: a neutral active, a bench with no Applin/Dipplin and
    # a discard clean of the line.
    o2 = _obs()
    riv2 = o2["current"]["players"][1 - yo]
    riv2["active"][0]["id"] = CHIKORITA
    riv2["bench"] = [b for b in riv2["bench"]
                     if b["id"] not in (DIPPLIN, m.Applin)]
    riv2["discard"] = [c for c in riv2["discard"]
                       if c["id"] not in (DIPPLIN, m.Applin)]
    m.agent(o2)
    # The stadium is still on the table (the projection flag does not change)...
    assert m._festival_grounds_in_play is True
    # ...but there is nobody left to exploit Festival Lead: with no opposing Dipplin the
    # Do the Wave projection does not apply to their active.
    op_act2 = m.to_observation_class(o2).current.players[1 - yo].active[0]
    tapu = next(b for b in m.to_observation_class(o2).current.players[yo].bench
                if b.id == TAPU)
    assert m._op_active_attack_damage_to(op_act2, tapu) < 100


def test_without_festival_grounds_the_premise_stands():
    """Control: the veto is about the STADIUM, not the matchup.

    Without Festival Grounds there is no second attack, the promotion resolves at the
    end of the opponent's turn and we go back to the usual behaviour -- the doomed
    candidate stops being vetoed as "best attacker".
    """
    obs = _obs(without_stadium=True)
    m.agent(obs)
    assert m._festival_grounds_in_play is False
