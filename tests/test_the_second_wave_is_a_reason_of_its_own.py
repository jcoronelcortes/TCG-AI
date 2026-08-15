"""The second wave is a reason of its own, not a consolation for a doomed ex.

Scenario (user, `records/registro_010_pasos_099_hasta_114.json`, episode
93242395, turn 10 vs *Festival Lead* -- WON, and won three turns later than it
had to be):

    US (3 prizes)                        RIVAL (3 prizes)
    active  Teal Mask Ogerpon ex         active  Applin    40/40
            210/210, 2 {G} cards         bench   Thwackey 100/100
    bench   Meganium 160                         Thwackey 100/100
            Teal Mask Ogerpon ex 210             Applin    40/40
            **Dipplin 80, no energy**            Grookey   70/70
            Chikorita 70
            Meowth ex 170                stadium **Festival Grounds** (theirs)
    hand    Hydrapple ex, **1 {G}**, ...

THE TURN THAT WAS AVAILABLE. The Grass goes onto the benched Dipplin, the ex
retreats (cost 1, it carries two cards) and *Do the Wave* is 20 x 5 = **100**:
their 40 HP Applin dies, and because Festival Grounds is on the field the SAME
wave lands again on whatever they promote -- every body they hold is 100 HP or
less. TWO prizes, from three down to one, and the body left in the front spot is
worth ONE prize instead of two.

WHAT THE AGENT PLAYED. Teal Dance banked that Grass on a benched Ogerpon ex that
already carried four energies; the Dipplin, now with nothing to charge it, was
evolved into Hydrapple ex; and Syrup Storm hit the 40 HP Applin for **330**. One
prize, 290 damage on the floor, a 2-prize ex in front and no second wave.

WHY NOTHING SAW IT -- and this is the part that matters, because every reading
involved was already RIGHT:

  * `prizes_today` read **2** on this very board (`_prizes_via_promote` counts
    the second wave). It labels a turn; it does not execute one.
  * `_promote_ko_active_prizes` answered **2** as well. Its only executing
    consumer is `_win_ko_active_via_promote`, which asks the route to CLOSE the
    game -- 2 >= 3 is false. The turn read RACE, and a RACE turn cashes the
    prize the body in front can already see.
  * the evolve veto under `_festival_lead_pays_us_now` DID fire: at that action
    Hydrapple ex on top of the Dipplin scored SCORE_VETO. It protected the BODY
    and nothing protected the ENERGY -- so Teal Dance took the Grass, the
    detector went False on the next action for want of it, the veto lifted, and
    the body it had been protecting was evolved.
  * `_festival_sac_pivot` is exactly this swap, and it was DEFENSIVE: its only
    door in was `active_ko_likely`. Here the ex stood at 210/210 in front of a
    40 HP Applin with nothing to fear.

THE FIX, in two halves, because two different things were missing:

  1. `_festival_sac_pivot` gains an OFFENSIVE arm. The doomed ex is not what
     makes the wave worth a retreat -- the SECOND WAVE is. The arm opens on the
     criterion `_promote_ko_active_prizes` already uses to overrule "the active
     can finish it itself": `_festival_second_wave_prizes` has to really close a
     second body, which it refuses to claim unless EVERY body they can promote
     dies to the same wave.
  2. `_festival_wave_needs_the_grass` holds the card the wave is counting on.
     The Teal Dance rung it stands in front of (31050) is a DEVELOPMENT charge --
     "the active already knocks out, bank the Grass on a benched Ogerpon" -- and
     banking it is right only while the alternative is nothing. Here the
     alternative was the second prize. It is a reserve, not a veto: with a
     second Grass in hand the dance keeps its say.

MEASURED. Rolled forward in the REAL engine from that board (K=50
determinizations, our own agent as the policy for both seats):

    attach the Grass to the Dipplin   our prizes left after this turn 1.00  (2 taken)
    Teal Dance (what was played)      ...                             1.86
    evolve into Hydrapple ex          ...                             2.00  (1 taken)

The self-play gate cannot see it and says so: N=1000 against
`deck/real_opponents/festival_lead_5.csv` reads -0.7 pp for the candidate against
a **-0.4 pp control** (HEAD's own main.py against HEAD at the same N) -- the
reference bot puts Festival Grounds on the field in a minority of games and
cannot pilot the deck behind it. `utils/census_the_second_wave_is_a_reason_of_its_own.py`
counts the firing instead: over 40 games, 91 of our menus with the stadium on the
field, 29 with a lethal wave and **13 where this arm fires**; and a flat zero on
every counter against a deck that does not bring the stadium.

INERT WITHOUT THE STADIUM, by construction: both halves live behind
`AGENT_STATE._festival_grounds_in_play`, and we do not carry Festival Grounds in
`deck.csv`. `test_without_the_stadium_the_record_line_is_unchanged` pins it.
"""

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import main as m  # noqa: E402
import golden_corpus as gc  # noqa: E402
from state_builder import Scenario, pk, G  # noqa: E402

OGERPON = m.Teal_Mask_Ogerpon_ex
MEGANIUM = m.Meganium
CHIKORITA = m.Chikorita
BAYLEEF = m.Bayleef
MEOWTH = m.Meowth_ex
DIPPLIN = m.Dipplin
APPLIN = m.Applin
HYDRAPPLE = m.Hydrapple_ex

# The opponent's own printings, read off the record: their Applin is id 42 (a
# different card from ours) and their Grookey/Thwackey line is 89/90.
OP_APPLIN = 42
GROOKEY = 89
THWACKEY = 90            # 100 HP: exactly what a 5-body wave kills
# A body the wave does NOT kill, for the half of the test that must stay shut.
SURVIVOR = m.Fezandipiti_ex      # 210 HP


@pytest.fixture(autouse=True)
def reset_main_state():
    m.AGENT_STATE.reset()
    m._init_cards_tracking()
    yield
    m.AGENT_STATE.reset()
    m._init_cards_tracking()


def _record_board(with_stadium=True, op_bench=None, extra_grass=False,
                  dipplin_energies=(), grass_in_hand=True, op_prizes=3):
    """registro_010 turn 10 at turnActionCount 5: the Dipplin is on the bench
    with nothing on it and the single Grass of the turn is still in hand."""
    gc.reset_agent(m)
    hand = [HYDRAPPLE] + ([m.Basic_Grass_Energy] if grass_in_hand else [])
    if extra_grass:
        hand.append(m.Basic_Grass_Energy)
    sc = (Scenario(turn=10, step=103, tac=5, own_prizes=3,
                   energy_played=not grass_in_hand)
          .my_active(pk(OGERPON, energies=[G] * 4, fisicas=2))
          .my_bench(pk(MEGANIUM, pre_evo=[CHIKORITA, BAYLEEF]),
                    pk(OGERPON, energies=[G] * 4, fisicas=2),
                    pk(DIPPLIN, energies=list(dipplin_energies),
                       pre_evo=[APPLIN]),
                    pk(CHIKORITA),
                    pk(MEOWTH))
          .my_hand(*hand)
          .op_active(pk(OP_APPLIN, hp=40, max_hp=40))
          .op_bench(*(op_bench or [pk(THWACKEY, hp=100, max_hp=100),
                                   pk(THWACKEY, hp=100, max_hp=100),
                                   pk(OP_APPLIN, hp=40, max_hp=40),
                                   pk(GROOKEY, hp=70, max_hp=70)]))
          .op_zones(hand=6, deck=25, prizes=op_prizes))
    if with_stadium:
        sc = sc.stadium(m.Festival_Grounds, of_the_opponent=True)
    obs = sc.menu_hand(with_retreat=True, with_attachment=grass_in_hand,
                       with_attack=True).build()
    return _hydrapple_as_an_evolution(obs)


def _hydrapple_as_an_evolution(obs):
    """`menu_hand` offers every card in hand as a plain PLAY; the simulator
    offers a Stage 2 as an EVOLVE onto the body it evolves from, and nothing
    else -- a Hydrapple ex cannot be benched. The difference is the whole test:
    the veto this turn depends on lives in the EVOLVE scorer, which a PLAY
    option never reaches.
    """
    mine = obs["current"]["players"][obs["current"]["yourIndex"]]
    hand_i = next(i for i, c in enumerate(mine["hand"]) if c["id"] == HYDRAPPLE)
    bench_i = next(i for i, b in enumerate(mine["bench"])
                   if b is not None and b["id"] == DIPPLIN)
    options = [o for o in obs["select"]["option"]
               if not (o["type"] == int(m.OptionType.PLAY)
                       and o["index"] == hand_i)]
    options.insert(0, {"type": int(m.OptionType.EVOLVE),
                       "area": int(m.AreaType.HAND), "index": hand_i,
                       "inPlayArea": int(m.AreaType.BENCH),
                       "inPlayIndex": bench_i})
    obs["select"]["option"] = options
    return obs


def _decide(obs):
    choice = list(m.agent(obs))
    return obs["select"]["option"][choice[0]]


def _sides(obs):
    cur = obs["current"]
    players = m.to_observation_class(obs).current.players
    return players[cur["yourIndex"]], players[1 - cur["yourIndex"]]


def _flag(obs, name):
    """A LOCAL of `agent()` on return -- the flag, not the choice it produced."""
    captured = {}

    def tracer(frame, event, arg):
        if frame.f_code.co_name != "agent":
            return None
        if event == "return" and name in frame.f_locals:
            captured[name] = frame.f_locals[name]
        return tracer

    previous = sys.gettrace()
    sys.settrace(tracer)
    try:
        m.agent(obs)
    finally:
        sys.settrace(previous)
    return captured.get(name)


def _is_attach_to_dipplin(obs, opt):
    """The option is the manual attachment onto the benched Dipplin."""
    if opt["type"] != int(m.OptionType.ATTACH):
        return False
    mine = obs["current"]["players"][obs["current"]["yourIndex"]]
    if opt.get("inPlayArea") != int(m.AreaType.BENCH):
        return False
    body = mine["bench"][opt["inPlayIndex"]]
    return body is not None and body["id"] == DIPPLIN


# ---------------------------------------------------------------------------
# 1. The reading was always right; nothing executed it
# ---------------------------------------------------------------------------

def test_the_promote_route_reads_two_prizes_on_this_board():
    obs = _record_board()
    _decide(obs)                       # builds AGENT_STATE off this board
    mine, theirs = _sides(obs)
    assert m._promote_ko_active_prizes(
        mine, theirs.active[0], True, False, True,
        m.count_total_grass_energy(mine), len(mine.bench),
        m.AGENT_STATE.meganium_in_play, False, op_state=theirs) == 2


def test_the_second_wave_needs_every_body_they_can_promote_to_die():
    """The claim that is NOT made: one survivor and the wave is worth one prize."""
    obs = _record_board()
    _decide(obs)
    _, theirs = _sides(obs)
    koed = theirs.active[0]
    assert m._festival_second_wave_prizes(theirs, 100, koed) == 1
    assert m._festival_second_wave_prizes(theirs, 80, koed) == 0


# ---------------------------------------------------------------------------
# 2. The turn: the Grass goes to the body that is the attack
# ---------------------------------------------------------------------------

def test_the_grass_goes_onto_the_dipplin_and_not_into_teal_dance():
    obs = _record_board()
    opt = _decide(obs)
    assert _is_attach_to_dipplin(obs, opt), opt


def test_the_offensive_arm_of_the_pivot_is_what_fired():
    obs = _record_board()
    assert _flag(obs, "_festival_sac_pivot") is True
    assert _flag(obs, "_festival_wave_outprizes_the_front") is True
    # ...and the ex in front is in no danger at all: this is not the old arm.
    assert _flag(obs, "active_ko_likely") is False


def test_the_reserve_holds_the_single_grass_the_wave_is_counting_on():
    assert _flag(_record_board(), "_festival_wave_needs_the_grass") is True


def test_the_evolution_that_would_undo_the_turn_is_still_vetoed():
    """Hydrapple ex on top of that Dipplin is a bigger body and a smaller turn."""
    obs = _record_board()
    scores = _scores(obs)
    evolve = next(i for i, o in enumerate(obs["select"]["option"])
                  if o["type"] == int(m.OptionType.EVOLVE))
    assert scores[evolve] <= 0


def _scores(obs):
    """The score of every option in the menu."""
    from patching import instalar
    seen = {}

    def spy(context, select, sc, ob, my_index, top_n=3):
        seen.setdefault("s", list(sc))

    restore_spy = instalar("_debug_log_decision", spy)
    restore_flag = instalar("DEBUG_DECISIONS", True)
    try:
        m.agent(obs)
    finally:
        restore_flag()
        restore_spy()
    return seen["s"]


def test_the_retreat_that_executes_the_route_is_priced_to_be_taken():
    obs = _record_board()
    scores = _scores(obs)
    retreat = next(i for i, o in enumerate(obs["select"]["option"])
                   if o["type"] == int(m.OptionType.RETREAT))
    assert scores[retreat] > 0


def test_with_the_dipplin_already_charged_the_turn_spends_itself_on_the_swap():
    """Later in the same turn: the Grass is on the Dipplin and the attachment is
    spent, so the only thing left that the route needs is the swap itself."""
    obs = _record_board(dipplin_energies=[G], grass_in_hand=False)
    opt = _decide(obs)
    assert opt["type"] == int(m.OptionType.RETREAT), opt


# ---------------------------------------------------------------------------
# 3. The two halves that must stay shut
# ---------------------------------------------------------------------------

def test_a_survivor_on_their_bench_closes_the_offensive_arm():
    """They choose who comes up. One body that lives through the wave and the
    swap buys nothing the body in front was not already worth."""
    obs = _record_board(op_bench=[pk(THWACKEY, hp=100, max_hp=100),
                                  pk(SURVIVOR, hp=210, max_hp=210)])
    assert _flag(obs, "_festival_wave_outprizes_the_front") is not True
    assert not _is_attach_to_dipplin(obs, _decide(obs))


def test_the_arm_stands_aside_when_the_body_it_leaves_closes_their_count():
    """At their match point the 80 HP Dipplin we put in front is a prize they
    were not going to reach; the healthy ex stays where it is."""
    obs = _record_board(op_prizes=1)
    assert _flag(obs, "_festival_wave_outprizes_the_front") is not True
    assert _flag(obs, "_festival_sac_pivot") is not True
    # The SWAP is what the guard refuses, and the swap is the whole route: with
    # the Dipplin already charged and nothing else left to pay, the turn does
    # NOT hand it the front spot.
    charged = _record_board(op_prizes=1, dipplin_energies=[G],
                            grass_in_hand=False)
    assert _decide(charged)["type"] != int(m.OptionType.RETREAT)


def test_without_the_stadium_the_record_line_is_unchanged():
    """No Festival Grounds, no second wave, no reason to hold the Grass: the
    turn goes back to the charge it always made."""
    obs = _record_board(with_stadium=False)
    assert _flag(obs, "_festival_wave_outprizes_the_front") is not True
    assert _flag(obs, "_festival_wave_needs_the_grass") is not True
    assert not _is_attach_to_dipplin(obs, _decide(obs))


def test_a_second_grass_in_hand_is_not_reserved():
    """A reserve holds what the route needs and no more: with two Grass the hand
    pays the wave AND the dance."""
    assert _flag(_record_board(extra_grass=True),
                 "_festival_wave_needs_the_grass") is not True
