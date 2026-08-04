"""Cruel Arrow: the best target is NOT always the opposing active.

Scenario (user, episode 88714320 registro_004 step 54 vs Alakazam, turn 4):

    US                                        OPPONENT
    active  Fezandipiti ex 210, 4 effective   active  Alakazam 140/140
    bench   Meowth ex, 3x Ogerpon ex (2e),    bench   Kadabra 80, Kadabra 80,
            Meganium (freshly evolved)                Abra 50, Dunsparce 70
    hand    Dipplin, Night Stretcher, Grass, Unfair Stamp, Ultra Ball, Tapu Bulu
    energyAttached: YES    Teal Dance of all THREE Ogerpon: ALREADY used

The menu offered PLAY / ATTACK(183 = Cruel Arrow) / RETREAT / END. The agent
RETREATED the Fezandipiti ex -- discarding its energy -- to promote an Ogerpon
that could not even attack, and closed the turn without doing anything.

Cruel Arrow does a FIXED 100 to ANY ONE of the opponent's Pokemon, active or
bench ("don't apply Weakness and Resistance to Benched Pokemon"). It did not reach
the 140 HP Alakazam, but it KNOCKED OUT an 80 HP Kadabra on the bench: a free
prize, with no retreat cost and without exposing another body.

Two causes, both fixed:

  1. The WHOLE planner measured the ACTIVE's attack against the opposing ACTIVE.
     `_active_can_ko_now` (the retreat scorer) and `_active_already_kos` returned
     False, the turn looked sterile and the retreat pivots won the menu.
     Fix: `_snipe_best_target` evaluates ALL the opposing Pokemon and its three
     new consumers -- `_active_snipe_ko_now` (the active CAN knock out,
     so it does not retreat), `_snipe_attack_wins_now` (the snipe also closes
     the game) and the ATTACK's 8500+ band -- propagate it. It is the SAME
     ranking function (`_snipe_target_score`) the DAMAGE menu uses when choosing the
     real target, so the two scales cannot diverge.

  2. What won the menu was `_ogerpon_lethal_promote` (8900): "retreat and bring up
     an Ogerpon that with Teal Dance reaches 3 energies and finishes". But the Grass
     was UNREACHABLE -- the manual attachment was already spent and the three Ogerpon
     had used their Teal Dance that turn --, so the finisher did not exist. The
     detector now requires `_grass_attach_route_open`.

When the bench pivot IS real, the rule does not override it blindly: the snipe
only yields to a KO worth MORE prizes (here Alakazam is non-ex, 1 prize = the
Kadabra, so attacking wins).
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

FEZ = m.Fezandipiti_ex          # 140: active, Cruel Arrow (100 to anyone)
OGERPON = m.Teal_Mask_Ogerpon_ex
ALAKAZAM = 743                  # the opposing active, 140 HP, NON-ex (1 prize)
KADABRA = 742                   # the opposing bench, 80 HP  <- the right target
ABRA = 741                      # the opposing bench, 50 HP
DUNSPARCE = 305                 # the opposing bench, 70 HP
CRUEL_ARROW = 183

_FIX_MAIN = ROOT / "tests" / "fixtures" / "fez_cruel_arrow_remata_banca_step54.json"
_FIX_DMG = ROOT / "tests" / "fixtures" / "fez_cruel_arrow_objetivo_banca_step54.json"


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
    m._grass_attaches_this_turn = 0
    m._dodge_immune_serial = None
    m._dodge_immune_turn = -1
    yield
    m._init_cards_tracking()


def _obs(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)["observation"]


def _play(obs, choice):
    o = obs["select"]["option"][choice[0]]
    tipo = o["type"]
    if tipo == int(m.OptionType.ATTACK):
        return ("ATTACK", o.get("attackId"))
    if tipo == int(m.OptionType.RETREAT):
        return ("RETREAT", None)
    if tipo == int(m.OptionType.END):
        return ("END", None)
    if tipo == int(m.OptionType.PLAY):
        yo = obs["current"]["yourIndex"]
        return ("PLAY", obs["current"]["players"][yo]["hand"][o["index"]]["id"])
    return (tipo, None)


def _pk_elegido(obs, choice):
    """The opposing Pokemon pointed at by option `eleccion` of the DAMAGE menu."""
    o = obs["select"]["option"][choice[0]]
    rival = obs["current"]["players"][o["playerIndex"]]
    zona = rival["active"] if o["area"] == int(m.AreaType.ACTIVE) else rival["bench"]
    return zona[o["index"]]


# ---------------------------------------------------------------------------
# The real step 54
# ---------------------------------------------------------------------------

def _menu_step54():
    """The observation of step 54 (turn 4, action 23) with the TURN STATE
    already advanced.

    This used to be obtained by replaying the whole turn from the record; the
    records are transient local data (the output of `utils/split_turns.py`)
    and the test broke as soon as the user loaded a new game. The only thing
    the replay contributed was the `_grass_attaches_this_turn` accumulator, which is
    built from the ATTACH logs step by step and is what knows whether any charging
    route is still alive. Here it is injected explicitly -- and it also makes visible
    which datum makes the scenario: **4 Grass already placed this turn**
    (1 manual attachment + the 3 Teal Dance of the three Ogerpon), that is, no
    open route. `pre_turn` is set to the current turn so `agent()` does not
    take this observation for the start of a new turn and reset the
    counter.
    """
    obs = _obs(_FIX_MAIN)
    m.pre_turn = obs["current"]["turn"]
    m._grass_attaches_this_turn = 4
    return obs


def test_step54_attacks_with_cruel_arrow_instead_of_retreating():
    obs = _menu_step54()
    # The menu must offer both plays for the test to discriminate.
    plays = [_play(obs, [i]) for i in range(len(obs["select"]["option"]))]
    assert ("ATTACK", CRUEL_ARROW) in plays, plays
    assert ("RETREAT", None) in plays, plays

    assert _play(obs, m.agent(obs)) == ("ATTACK", CRUEL_ARROW)


def test_step54_the_ogerpon_finisher_was_impossible():
    """The retreat won the menu through a KO that did NOT exist: there was a Grass in
    hand, but no route to put it on the field."""
    obs = _menu_step54()
    st = m.to_observation_class(obs).current
    yo = st.players[1]

    assert st.energyAttached is True                  # manual attachment spent
    assert m._grass_attaches_this_turn == 4           # 1 manual + 3 Teal Dance
    assert sum(1 for p in yo.bench if p is not None
               and p.id == OGERPON) == 3              # the 3 Teal Dance used
    assert m._grass_attach_route_open(st, {OGERPON: 3}) is False
    assert any(c.id == m.Basic_Grass_Energy for c in yo.hand)


def test_step54_cruel_arrow_cannot_reach_the_active_but_can_reach_the_bench():
    """The state that made the mistake inevitable: measured against the opposing ACTIVE the
    turn is sterile, measured against the WHOLE opposing field there is a prize."""
    obs = _menu_step54()
    st = m.to_observation_class(obs).current
    active = st.players[1].active[0]
    rival = st.players[0]

    assert active.id == FEZ
    assert len(active.energies) >= 3                  # Cruel Arrow available
    assert rival.active[0].id == ALAKAZAM
    assert rival.active[0].hp == 140                  # 100 does NOT knock it out
    assert any(p is not None and p.id == KADABRA and p.hp == 80
               for p in rival.bench)                  # 100 DOES knock it out

    target, damage, es_ko = m._snipe_best_target(active, rival, len(active.energies),
                                                 m.meganium_in_play, False)
    assert (target.id, damage, es_ko) == (KADABRA, 100, True)


# ---------------------------------------------------------------------------
# The DAMAGE menu: where the arrow points
# ---------------------------------------------------------------------------

def test_cruel_arrow_aims_at_the_kadabra_not_the_active():
    obs = _obs(_FIX_DMG)
    elegido = _pk_elegido(obs, m.agent(obs))
    assert (elegido["id"], elegido["hp"]) == (KADABRA, 80)


def test_cruel_arrow_prefers_the_kadabra_over_abra_and_dunsparce():
    """Among the three bodies that die, the most developed one (Stage 1, 80 HP)."""
    obs = _obs(_FIX_DMG)
    rival = obs["current"]["players"][0]
    hp = {p["id"]: p["hp"] for p in rival["bench"]}
    assert hp[ABRA] == 50 and hp[DUNSPARCE] == 70 and hp[KADABRA] == 80

    from main import _snipe_target_score as sc
    st = m.to_observation_class(obs).current.players[0]
    by_id = {p.id: p for p in st.bench if p is not None}
    assert sc(100, by_id[KADABRA]) > sc(100, by_id[DUNSPARCE])
    assert sc(100, by_id[DUNSPARCE]) > sc(100, by_id[ABRA])
    # The active, which survives, stays below any KO.
    assert sc(100, st.active[0]) < sc(100, by_id[ABRA])


# ---------------------------------------------------------------------------
# The snipe evaluator, in isolation
# ---------------------------------------------------------------------------

def test_a_snipe_with_no_energy_proposes_nothing():
    obs = _obs(_FIX_DMG)
    st = m.to_observation_class(obs).current
    active = st.players[1].active[0]
    active.energies = active.energies[:2]             # Cruel Arrow costs 3
    assert m._snipe_best_target(active, st.players[0], 2,
                                False, False) == (None, 0, False)


def test_the_snipe_is_only_for_attackers_that_choose_a_target():
    """An Ogerpon ex does not snipe: its Myriad Leaf Shower only hits the active."""
    obs = _obs(_FIX_DMG)
    st = m.to_observation_class(obs).current
    ogerpon = next(p for p in st.players[1].bench if p is not None and p.id == OGERPON)
    assert m._snipe_best_target(ogerpon, st.players[0], 6,
                                False, False) == (None, 0, False)


def test_the_snipe_respects_ex_immunity():
    """Fezandipiti ex is an ex: against a wall that makes our ex useless the snipe
    does 0 and proposes no KO (the chip still chooses the least bad one)."""
    obs = _obs(_FIX_DMG)
    st = m.to_observation_class(obs).current
    active = st.players[1].active[0]
    rival = st.players[0]
    inmune = next(iter(m.EX_IMMUNE_IDS))
    for p in [rival.active[0]] + [b for b in rival.bench if b is not None]:
        p.id = inmune
    target, damage, es_ko = m._snipe_best_target(active, rival,
                                                 len(active.energies),
                                                 m.meganium_in_play, False)
    assert damage == 0 and es_ko is False


# ---------------------------------------------------------------------------
# The single-call fixture (the same verdict without a replay)
# ---------------------------------------------------------------------------

def test_fixture_step54_attacks():
    obs = _obs(_FIX_MAIN)
    assert _play(obs, m.agent(obs)) == ("ATTACK", CRUEL_ARROW)


def test_fixture_step54_does_not_retreat_even_if_the_ogerpon_looked_lethal():
    """Even if the Grass route were open, the Ogerpon pivot canNOT
    override the snipe: Alakazam is NON-ex, that is, the SAME prize as the
    Kadabra, and attacking pays no retreat cost and exposes no other body."""
    obs = copy.deepcopy(_obs(_FIX_MAIN))
    obs["current"]["energyAttached"] = False          # the manual attachment is free
    assert _play(obs, m.agent(obs)) == ("ATTACK", CRUEL_ARROW)


def test_the_snipe_yields_to_a_ko_worth_more_prizes_without_closing_the_turn():
    """The snipe rules over the filler plays, not over a bigger KO.

    With a 2-prize ex in front (Archaludon ex, 300 HP: Cruel Arrow does not reach it)
    and a benched Ogerpon whose Myriad DOES finish it, retreating takes twice as much. What
    must NEVER happen is that the snipe's veto on the retreat and the plan's
    veto on the attack cancel each other out and the turn closes
    blank -- hence the `plan.attacker <= 0` guard of `_active_snipe_ko_now`.
    """
    obs = copy.deepcopy(_obs(_FIX_MAIN))
    rival = obs["current"]["players"][0]["active"][0]
    archaludon = m.card_table[190]
    assert archaludon.ex and archaludon.hp == 300
    rival["id"] = 190
    rival["hp"] = rival["maxHp"] = archaludon.hp
    # A benched Ogerpon with energy to spare to finish the wall.
    obs["current"]["players"][1]["bench"][1]["energies"] = [1] * 12

    play = _play(obs, m.agent(obs))
    assert play != ("END", None), play
    assert play == ("RETREAT", None), play
