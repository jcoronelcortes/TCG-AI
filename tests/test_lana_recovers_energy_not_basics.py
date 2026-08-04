"""Lana's Aid: what is picked up from the discard is decided by THE BOARD, not by the
shape of the evolution lines.

Scenario (user, episode 88776459 registro_018 step 118 vs Crustle, LOST):

    US                                      OPPONENT
    active  Tapu Bulu   140/140  2e         active  Crustle  270/290
    bench   Meganium    160/160  2e         (a bench full of charged bodies)
            Meowth ex    50/170  2e
            Meganium    160/160  0e
            Ogerpon ex   90/210  2e
            Ogerpon ex  210/210  0e   <- bench FULL (5/5)
    hand    Hydrapple ex
    discard   4x Basic Grass, 2x Applin, 1x Dipplin (+ items)
    the turn's energy UNPLAYED

The agent played **Lana's Aid** -- the right card, as the user confirms -- and
picked up **2 Applin + 1 Dipplin**. With the bench FULL a Basic does not fit in
any way, and the Dipplin has no Applin in play to
evolve on top of: three DEAD cards. The turn died without attacking.

What the board was asking for was **energy**:

- with two Meganium in play (*Wild Growth*) ONE physical Grass is worth {G}{G}, so
  `_grass_attach_unit()` = 2;
- the ACTIVE Tapu Bulu has 2 effective and Wood Hammer asks for 4
  (`ATTACK_ENERGY_REQ`): **a single Grass puts it in attack range THIS turn**, and the
  manual attachment was still unspent;
- the other two Grass charge the Meganium for the next turn (the two
  Ogerpon ex in play also leave two *Teal Dance* alive).

Root cause: Lana's Aid had no branch of its own in the `TO_HAND` context and fell to
the generic recovery scorer, which only knows how to read evolution-line SHAPES
("am I missing this link?") and looks at neither the energy nor the bench slot. Its
numbers -- Applin 260 > Dipplin 250 > Grass 240 -- decided the menu.

The fix, in two pieces that share the SAME board reading:

 1. `_grass_plan`: it walks the `MAIN_ATTACKERS` in play, measures their deficit
    in Grass CARDS (`ceil((req - effective) / unit)`) and counts the turn's real
    attachment routes (manual + `_grass_ability_slots`: Teal Dance only
    charges its bearer, Ripening Charge anyone). It returns `demanda` and
    `unlocks_today`/`cards_to_attack`.
 2. The `Lanas_Aid` branch of the `TO_HAND` context, in three bands
    (`LANA_SEL_GRASS_UNLOCKS` > `LANA_SEL_GRASS_DEMAND` > development >
    `LANA_SEL_GRASS_SURPLUS`/`LANA_SEL_INJUGABLE`), with the ordinal
    `_lana_grass_order` so that only the FIRST `demanda` Grass get the
    high band -- otherwise, four tied copies would take all 3 choices
    even if the board could only use one.

Along the way, `_lana_energy_enables_attack` (the PLAY layer, which decides whether Lana's Aid
deserves the 950 points against Lillie's) switches to the same
`_grass_plan`: before it only knew how to look at Hydrapple ex and that is why it stayed silent with
a Tapu Bulu one Grass away from firing.
"""

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import main as m
from state_builder import G, Escenario, pk

GRASS = m.Basic_Grass_Energy
TAPU = m.Tapu_Bulu                 # Wood Hammer: 4 effective energies
MEGANIUM = m.Meganium              # Wild Growth: each physical Grass is worth {G}{G}
OGERPON = m.Teal_Mask_Ogerpon_ex
MEOWTH = m.Meowth_ex
HYDRAPPLE = m.Hydrapple_ex
APPLIN = m.Applin
DIPPLIN = m.Dipplin
CHIKORITA = m.Chikorita
LANA = m.Lanas_Aid
CRUSTLE = m.Crustle_Grass
DWEBBLE = m.Dwebble_Grass

_FIXTURE = (ROOT / "tests" / "fixtures"
            / "crustle_lana_levanta_energia_no_basicos_step118.json")


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
    m._grass_attaches_this_turn = 0
    yield
    m._init_cards_tracking()


def _chosen_cards(obs, choice):
    """The discard ids the selection returns, in order of preference."""
    discard = obs["current"]["players"][obs["current"]["yourIndex"]]["discard"]
    return [discard[obs["select"]["option"][i]["index"]]["id"] for i in choice]


# ---------------------------------------------------------------------------
# The real step 118
# ---------------------------------------------------------------------------

def test_step118_picks_up_the_three_energies():
    with open(_FIXTURE, encoding="utf-8") as f:
        fixture = json.load(f)
    obs = fixture["observation"]

    # The real menu offered 4 Grass, 2 Applin and 1 Dipplin.
    ofrecidas = _chosen_cards(obs, range(len(obs["select"]["option"])))
    assert sorted(ofrecidas) == sorted([GRASS] * 4 + [APPLIN] * 2 + [DIPPLIN])
    assert obs["select"]["maxCount"] == 3

    # What was played in the game (and lost the turn).
    assert _chosen_cards(obs, fixture["recorded_action"]) == [APPLIN, APPLIN,
                                                                 DIPPLIN]

    assert _chosen_cards(obs, m.agent(obs)) == [GRASS, GRASS, GRASS]


def test_step118_one_grass_puts_the_tapu_bulu_in_attack_range():
    """The core of the board reading: with Meganium in play the Tapu Bulu is
    ONE Grass card away from being able to attack, and the turn's attachment is still free."""
    with open(_FIXTURE, encoding="utf-8") as f:
        obs = json.load(f)["observation"]
    m.agent(obs)  # it sets the turn's globals (meganium_in_play, ...)

    o = m.to_observation_class(obs)
    mi = o.current.players[o.current.yourIndex]
    campo = {}
    for p in mi.active + mi.bench:
        if p is not None:
            campo[p.id] = campo.get(p.id, 0) + 1
    hand = {}
    for c in (mi.hand or []):
        hand[c.id] = hand.get(c.id, 0) + 1

    assert m.meganium_in_play and m._grass_attach_unit() == 2
    tapu = mi.active[0]
    assert tapu.id == TAPU
    assert len(tapu.energies) == 2 and m.ATTACK_ENERGY_REQ[TAPU] == 4

    plan = m._grass_plan(mi, o.current, campo, hand)
    assert plan.unlocks_today
    assert plan.cards_to_attack == 1
    assert plan.demanda == 3          # the Meganium/Ogerpon ask for the rest


def test_step118_applin_and_dipplin_are_dead_cards():
    """Bench 5/5 and no Applin in play: neither does the Basic fit nor does the Stage 1
    evolve anything."""
    with open(_FIXTURE, encoding="utf-8") as f:
        obs = json.load(f)["observation"]
    o = m.to_observation_class(obs)
    mi = o.current.players[o.current.yourIndex]
    campo = {}
    for p in mi.active + mi.bench:
        if p is not None:
            campo[p.id] = campo.get(p.id, 0) + 1
    bench = len([p for p in mi.bench if p is not None])

    assert bench == mi.benchMax
    assert m._pokemon_injugable(APPLIN, campo, bench, mi.benchMax)
    assert m._pokemon_injugable(DIPPLIN, campo, bench, mi.benchMax)
    assert not m._pokemon_injugable(GRASS, campo, bench, mi.benchMax)


# ---------------------------------------------------------------------------
# `_grass_plan`: the board reading, in isolation
# ---------------------------------------------------------------------------

def _plan(active, bench=(), hand=(), energy_played=False, cambio=False):
    obs = (Escenario(turn=10, energy_played=energy_played)
           .my_active(active)
           .my_bench(*bench)
           .my_hand(*hand)
           .op_active(pk(CRUSTLE))
           .op_zonas(hand=5, deck=30, prizes=6)
           .menu_hand()
           .build())
    o = m.to_observation_class(obs)
    mi = o.current.players[o.current.yourIndex]
    campo = {}
    for p in mi.active + mi.bench:
        if p is not None:
            campo[p.id] = campo.get(p.id, 0) + 1
    m.meganium_in_play = campo.get(MEGANIUM, 0) >= 1
    m._grass_attaches_this_turn = 0
    cuentas = {}
    for c in (mi.hand or []):
        cuentas[c.id] = cuentas.get(c.id, 0) + 1
    return m._grass_plan(mi, o.current, campo, cuentas,
                             can_switch=cambio)


def test_plan_all_charged_means_no_demand():
    """With no deficit there is no demand: energy stops being worth anything even if
    there are attachments left free."""
    plan = _plan(pk(TAPU, energies=[G] * 4, fisicas=4),
                 bench=[pk(OGERPON, energies=[G] * 3, fisicas=3)])
    assert plan.demanda == 0
    assert not plan.unlocks_today


def test_plan_with_no_free_attachment_it_unlocks_nothing_but_demand_remains():
    """With the manual attachment spent and no charging abilities, the Grass does not reach
    the field TODAY -- but it goes to hand and the attacker goes on asking for it."""
    plan = _plan(pk(TAPU, energies=[G] * 2, fisicas=2), energy_played=True)
    assert not plan.unlocks_today
    assert plan.demanda >= 1


def test_plan_the_grass_already_in_hand_unlocks_it():
    """With the Grass already in hand, recovering another unlocks nothing: the
    detector cannot charge twice for the same attack."""
    plan = _plan(pk(TAPU, energies=[G] * 2, fisicas=2), hand=[GRASS])
    assert not plan.unlocks_today


def test_plan_a_bench_attacker_only_unlocks_if_we_can_switch():
    bench = [pk(MEGANIUM, energies=[G] * 2, fisicas=1)]
    active = pk(MEOWTH)               # Meowth ex is not a MAIN_ATTACKER
    assert not _plan(active, bench=bench).unlocks_today
    assert _plan(active, bench=bench, cambio=True).unlocks_today


def test_plan_with_abilities_off_only_the_manual_attachment_is_left():
    """Under Watchtower / Iron Thorns (`meowth_ability_lock`) there is no Teal Dance
    or Ripening Charge: treating those routes as alive invents unlocks that do not
    exist (measured: -3.9 points of winrate vs the Iron Thorns deck)."""
    active = pk(OGERPON, energies=[G], fisicas=1)      # 1 of 3 effective
    bench = [pk(OGERPON, energies=[G] * 2, fisicas=2)]

    obs = (Escenario(turn=10)
           .my_active(active).my_bench(*bench)
           .op_active(pk(CRUSTLE)).op_zonas(hand=5, deck=30, prizes=6)
           .menu_hand().build())
    o = m.to_observation_class(obs)
    mi = o.current.players[o.current.yourIndex]
    campo = {OGERPON: 2}
    m.meganium_in_play = False
    m._grass_attaches_this_turn = 0

    # With the abilities alive: the manual attachment + 2 Teal Dance -> 3 slots, and the
    # active (1 of 3) reaches 3 with 2 Grass.
    vivas = m._grass_plan(mi, o.current, campo, {})
    assert vivas.slots_today == 3 and vivas.unlocks_today

    # With the lock on, only the manual attachment is left: 1 Grass is not enough.
    apagadas = m._grass_plan(mi, o.current, campo, {},
                                 abilities_off=True)
    assert apagadas.slots_today == 1 and not apagadas.unlocks_today


def test_plan_non_attackers_do_not_invent_demand():
    """Chikorita and Applin have a cost in `ATTACK_ENERGY_REQ` but are not in
    `MAIN_ATTACKERS`: with them on the bench the board asks for no energy."""
    plan = _plan(pk(TAPU, energies=[G] * 4, fisicas=4),
                 bench=[pk(CHIKORITA), pk(APPLIN)])
    assert plan.demanda == 0


# ---------------------------------------------------------------------------
# `_pokemon_injugable`: the dead-card floor
# ---------------------------------------------------------------------------

def test_unplayable_with_a_bench_slot_nothing_is_dead():
    campo = {MEGANIUM: 1}
    assert not m._pokemon_injugable(APPLIN, campo, 3, 5)
    assert not m._pokemon_injugable(DIPPLIN, campo, 3, 5)


def test_unplayable_full_bench_the_evolution_lives_if_its_preevo_is_in_play():
    """The Dipplin is still playable with a full bench if there is an Applin in
    play: it evolves on top of it, it takes no slot."""
    campo = {APPLIN: 1, MEGANIUM: 4}
    assert not m._pokemon_injugable(DIPPLIN, campo, 5, 5)
    assert m._pokemon_injugable(APPLIN, campo, 5, 5)


def test_unplayable_does_not_apply_to_what_is_not_a_pokemon():
    assert not m._pokemon_injugable(GRASS, {}, 5, 5)
    assert not m._pokemon_injugable(LANA, {}, 5, 5)


# ---------------------------------------------------------------------------
# The selection, synthetically
# ---------------------------------------------------------------------------

def _seleccion_lana(active, bench, discard, hand=(), energy_played=False):
    obs = (Escenario(turn=10, partidario_jugado=True,
                     energy_played=energy_played)
           .my_active(active)
           .my_bench(*bench)
           .my_hand(*hand)
           .my_discard(*discard)
           .op_active(pk(CRUSTLE))
           .op_bench(pk(DWEBBLE))
           .op_zonas(hand=5, deck=30, prizes=6)
           .fetch_discard(LANA, cuantas=3, only=(GRASS, APPLIN, DIPPLIN,
                                                  CHIKORITA))
           .build())
    return obs, _chosen_cards(obs, m.agent(obs))


def test_selection_full_bench_the_energy_beats_development():
    """registro_018, synthetically."""
    _, elegidas = _seleccion_lana(
        active=pk(TAPU, energies=[G] * 2, fisicas=1),
        bench=[pk(MEGANIUM, energies=[G] * 2, fisicas=1), pk(MEOWTH),
               pk(MEGANIUM), pk(OGERPON, energies=[G] * 2, fisicas=1),
               pk(OGERPON)],
        discard=[GRASS, GRASS, GRASS, APPLIN, APPLIN, DIPPLIN])
    assert elegidas == [GRASS, GRASS, GRASS]


def test_selection_with_no_energy_demand_development_returns():
    """Boundary: with the active ALREADY charged and room on the bench, the energy is surplus and
    the recovery goes back to being development (starting the Hydrapple line)."""
    _, elegidas = _seleccion_lana(
        active=pk(TAPU, energies=[G] * 4, fisicas=4),
        bench=[pk(MEOWTH)],
        discard=[GRASS, GRASS, GRASS, APPLIN, DIPPLIN],
        energy_played=True)
    assert APPLIN in elegidas, elegidas


def test_selection_only_the_needed_grass_gets_the_high_band():
    """With a demand of ONE Grass and room on the bench, the SECOND choice is already
    development: the ordinal stops four tied copies taking the whole
    menu (the surplus Grass falls to `LANA_SEL_GRASS_SURPLUS`, below
    the Applin that starts the Hydrapple line)."""
    obs, elegidas = _seleccion_lana(
        active=pk(TAPU, energies=[G] * 2, fisicas=1),
        bench=[pk(MEGANIUM, energies=[G] * 4, fisicas=2), pk(MEOWTH)],
        discard=[GRASS, GRASS, GRASS, GRASS, APPLIN, CHIKORITA])
    assert elegidas[:2] == [GRASS, APPLIN], elegidas
