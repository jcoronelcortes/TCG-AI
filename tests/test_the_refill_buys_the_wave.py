"""The refill buys the wave the evolution would delete.

Scenario (user, `records/registro_006_pasos_061_hasta_085.json`, episode
93378353, turn 6 vs *Festival Lead* -- LOST):

    US (6 prizes)                        RIVAL (5 prizes)
    active  Teal Mask Ogerpon ex         active  Dipplin 80/80, 1 {G}
            210/210, 3 {G}                       (Brave Bangle)
    bench   Fezandipiti ex 210           bench   Thwackey 100/100
            **Dipplin 80, no energy**            Thwackey 100/100
            Meowth ex 170                        Applin   40/40, 1 {G}
    hand    Hydrapple ex, LILLIE'S,              Applin   40/40
            Lana's Aid, Meganium,                Grookey  70/70
            Boss's Orders -- **no Grass**
                                         stadium **Festival Grounds** (theirs)

WHAT THE AGENT PLAYED: it evolved that Dipplin into Hydrapple ex. On the bench,
at zero energy, with no Grass in hand, the new body could not attack and could
not even use *Ripening Charge* -- both take their Grass from hand. It was a
330 HP body parked for later, and the price of parking it was the only card on
the board whose value their own stadium changes.

WHAT THE BOARD WAS OFFERING. Festival Grounds is SHARED: with it on the field
our Dipplin throws *Do the Wave* TWICE, and every body they own is 100 HP or
less. The bench had two free seats, the Supporter slot was untouched, and the
hand held Lillie's Determination -- at exactly six prizes it draws EIGHT. Those
eight cards are the Grass the wave needs and the bodies the wave counts; the
recorded game drew four Grass and two benchable bodies with them, and still had
the Ogerpon's attack afterwards, because a Supporter does not end the turn.

WHY THE TWO EXISTING READINGS STAY SILENT, and both for the same reason -- they
ask the board as it STANDS:

  * `_festival_lead_pays_us_now` needs the wave to knock their Active out TODAY.
    The Dipplin has nothing to charge it with, and 20 x 3 benched = 60 against
    80 HP would not reach even if it had.
  * `_festival_sac_pivot` needs the same thing before it will commit a retreat.

Both shortages are the HAND's. `_festival_refill_buys_the_wave` is the same
sentence one turn earlier: the stadium is on the field, our Dipplin is in play
and can take the front spot, there are free seats, the Supporter slot still
holds the refill -- and at a FULL bench the wave (20 x 5 = 100) buries their
Active AND every body they could promote behind it
(`_festival_second_wave_prizes`, which answers 0 the moment one survivor
stands). The full bench is the honest bound: the refill can only buy seats we
already have.

THE EVOLUTION HAS TO BE INERT for any of this to be a trade. A Hydrapple ex that
reaches Syrup Storm today is cashing a prize today and outranks a wave that has
yet to be bought -- `test_a_hydrapple_that_can_attack_today_is_still_evolved`
is that half, and it must not move.

MEASURED on the board it comes from, both arms being the same tree with the flag
rebound:

    turn yield (40 determinised worlds, the agent finishing the turn in both,
    `utils/turn_yield_the_refill_buys_the_wave.py`)

        con la lectura   1.50 prizes   front: Dipplin 20 / Hydrapple ex 15
        sin ella         1.00 prizes   front: Hydrapple ex 37
        20/40 worlds take MORE prizes, 0 take fewer

    rules oracle (K=100, `utils/oracle_the_refill_buys_the_wave.py`)

        con la lectura   99/100  margin +3.92
        sin ella         96/100  margin +3.29
        delta +3 pp / +0.63 against the board's own floor of 2 pp / 0.19

INERT WITHOUT THE STADIUM, by construction: the block lives behind
`AGENT_STATE._festival_grounds_in_play`, and we do not carry Festival Grounds in
`deck.csv`. `test_without_the_stadium_the_dipplin_is_evolved` pins it, and
`utils/census_the_refill_buys_the_wave.py` reports a flat zero on every counter
against a list that cannot put it there.
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
FEZANDIPITI = m.Fezandipiti_ex
MEOWTH = m.Meowth_ex
DIPPLIN = m.Dipplin
APPLIN = m.Applin
HYDRAPPLE = m.Hydrapple_ex
LILLIE = m.Lillie_Determination
MEGANIUM = m.Meganium
LANA = m.Lanas_Aid
BOSS = m.Boss_Orders

# Their side of this record uses the same printings we do for the Applin line,
# and the Grookey/Thwackey line is 89/90.
GROOKEY = 89
THWACKEY = 90            # 100 HP: exactly what a 5-body wave kills
BRAVE_BANGLE = m.Brave_Bangle


@pytest.fixture(autouse=True)
def reset_main_state():
    m.AGENT_STATE.reset()
    m._init_cards_tracking()
    yield
    m.AGENT_STATE.reset()
    m._init_cards_tracking()


def _record_board(with_stadium=True, with_lillie=True, supporter_played=False,
                  dipplin_energies=(), grass_in_hand=False, op_bench=None,
                  my_bench_extra=()):
    """registro_006 turn 6 at turnActionCount 1: the Dipplin is on the bench
    with nothing on it, there is no Grass in hand and the Supporter slot is
    free."""
    gc.reset_agent(m)
    hand = [HYDRAPPLE, MEGANIUM, LANA, BOSS]
    if with_lillie:
        hand.insert(1, LILLIE)
    if grass_in_hand:
        hand.append(m.Basic_Grass_Energy)
    sc = (Scenario(turn=6, step=61, tac=1, own_prizes=6,
                   supporter_played=supporter_played)
          .my_active(pk(OGERPON, energies=[G] * 3))
          .my_bench(pk(FEZANDIPITI),
                    pk(DIPPLIN, energies=list(dipplin_energies),
                       pre_evo=[APPLIN]),
                    pk(MEOWTH),
                    *my_bench_extra)
          .my_hand(*hand)
          .op_active(pk(DIPPLIN, hp=80, max_hp=80, energies=[G],
                        pre_evo=[APPLIN], tools=[BRAVE_BANGLE]))
          .op_bench(*(op_bench or [pk(THWACKEY, hp=100, max_hp=100),
                                   pk(THWACKEY, hp=100, max_hp=100),
                                   pk(APPLIN, hp=40, max_hp=40, energies=[G]),
                                   pk(APPLIN, hp=40, max_hp=40),
                                   pk(GROOKEY, hp=70, max_hp=70)]))
          .op_zones(hand=4, deck=33, prizes=5))
    if with_stadium:
        sc = sc.stadium(m.Festival_Grounds, of_the_opponent=True)
    obs = sc.menu_hand(with_retreat=True, with_attachment=grass_in_hand,
                       with_attack=True).build()
    return _hydrapple_as_an_evolution(obs)


def _hydrapple_as_an_evolution(obs):
    """`menu_hand` offers every card in hand as a plain PLAY; the simulator
    offers a Stage 2 as an EVOLVE onto the body it evolves from, and nothing
    else -- a Hydrapple ex cannot be benched. The difference is the whole test:
    the veto lives in the EVOLVE scorer, which a PLAY option never reaches.
    """
    mine = obs["current"]["players"][obs["current"]["yourIndex"]]
    hand_i = next(i for i, c in enumerate(mine["hand"]) if c["id"] == HYDRAPPLE)
    bench_i = next(i for i, b in enumerate(mine["bench"])
                   if b is not None and b["id"] == DIPPLIN)
    # ...and the same correction for the OTHER Stage in that hand: a Meganium
    # with no Bayleef in play is not a legal play and the record's menu did not
    # offer it. `menu_hand` offers every card indiscriminately, so a menu built
    # from it holds options the board never had.
    dead = {hand_i}
    dead |= {i for i, c in enumerate(mine["hand"]) if c["id"] == MEGANIUM}
    options = [o for o in obs["select"]["option"]
               if not (o["type"] == int(m.OptionType.PLAY)
                       and o["index"] in dead)]
    options.insert(0, {"type": int(m.OptionType.EVOLVE),
                       "area": int(m.AreaType.HAND), "index": hand_i,
                       "inPlayArea": int(m.AreaType.BENCH),
                       "inPlayIndex": bench_i})
    obs["select"]["option"] = options
    return obs


def _decide(obs):
    choice = list(m.agent(obs))
    return obs["select"]["option"][choice[0]]


def _is_evolve(obs, opt):
    return opt["type"] == int(m.OptionType.EVOLVE)


def _is_lillie(obs, opt):
    if opt["type"] != int(m.OptionType.PLAY):
        return False
    mine = obs["current"]["players"][obs["current"]["yourIndex"]]
    return mine["hand"][opt["index"]]["id"] == LILLIE


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


def _evolve_index(obs):
    return next(i for i, o in enumerate(obs["select"]["option"])
                if o["type"] == int(m.OptionType.EVOLVE))


# ---------------------------------------------------------------------------
# 1. The board: what the two existing readings say, and what they miss
# ---------------------------------------------------------------------------

def test_the_wave_does_not_reach_yet_so_the_old_veto_is_silent():
    """The turn cannot throw the wave TODAY: no Grass in hand and 3 benched."""
    obs = _record_board()
    assert _flag(obs, "_festival_lead_pays_us_now") is False
    assert _flag(obs, "_festival_sac_pivot") is False


def test_at_a_full_bench_the_wave_closes_two_bodies():
    """The arithmetic the new flag stands on, asserted on its own."""
    obs = _record_board()
    _decide(obs)                       # builds AGENT_STATE off this board
    cur = obs["current"]
    players = m.to_observation_class(obs).current.players
    theirs = players[1 - cur["yourIndex"]]
    assert m._festival_second_wave_prizes(theirs, 100, theirs.active[0]) == 1
    # ...and one seat short of a full bench it closes NOTHING: their Thwackey
    # survives 80, and a survivor is worth zero here.
    assert m._festival_second_wave_prizes(theirs, 80, theirs.active[0]) == 0


def test_the_refill_is_what_buys_it():
    assert _flag(_record_board(), "_festival_refill_buys_the_wave") is True


# ---------------------------------------------------------------------------
# 2. The turn: the refill goes first and the body survives it
# ---------------------------------------------------------------------------

def test_the_turn_plays_lillie_and_not_the_evolution():
    obs = _record_board()
    opt = _decide(obs)
    assert _is_lillie(obs, opt), opt


def test_the_inert_evolution_onto_that_dipplin_is_vetoed():
    obs = _record_board()
    assert _scores(obs)[_evolve_index(obs)] <= 0


# ---------------------------------------------------------------------------
# 3. The halves that must NOT move
# ---------------------------------------------------------------------------

def test_without_the_stadium_the_dipplin_is_evolved():
    """No Festival Grounds, no double wave, no reason to keep the body."""
    obs = _record_board(with_stadium=False)
    assert _flag(obs, "_festival_refill_buys_the_wave") is False
    assert _is_evolve(obs, _decide(obs))


def test_with_no_refill_in_hand_the_dipplin_is_evolved():
    """The flag is about a card the hand HOLDS: without it there is nothing to
    prefer the wave to, and the evolution is the play again."""
    obs = _record_board(with_lillie=False)
    assert _flag(obs, "_festival_refill_buys_the_wave") is False
    assert _is_evolve(obs, _decide(obs))


def test_with_the_supporter_slot_already_spent_the_dipplin_is_evolved():
    obs = _record_board(supporter_played=True)
    assert _flag(obs, "_festival_refill_buys_the_wave") is False
    assert _is_evolve(obs, _decide(obs))


def test_a_survivor_on_their_bench_shuts_the_reading():
    """The second wave is refused whole the moment one body outlives it: a
    130 HP body on their bench and the flag never lights."""
    obs = _record_board(op_bench=[pk(THWACKEY, hp=100, max_hp=100),
                                  pk(m.Fezandipiti_ex, hp=210, max_hp=210),
                                  pk(APPLIN, hp=40, max_hp=40),
                                  pk(GROOKEY, hp=70, max_hp=70)])
    assert _flag(obs, "_festival_refill_buys_the_wave") is False


def test_with_no_seat_left_the_wave_cannot_grow():
    """A full bench is a wave that is already as big as it will get, which is
    `_festival_lead_pays_us_now`'s question and not this one."""
    obs = _record_board(my_bench_extra=(pk(m.Chikorita), pk(m.Applin)))
    assert _flag(obs, "_festival_refill_buys_the_wave") is False


def test_a_hydrapple_that_can_attack_today_is_still_evolved():
    """The veto is on an INERT stage. With the Dipplin already carrying one
    Grass and another in hand, Hydrapple ex reaches Syrup Storm on the turn it
    lands -- a prize today outranks a wave that has yet to be bought."""
    obs = _record_board(dipplin_energies=[G], grass_in_hand=True)
    assert _scores(obs)[_evolve_index(obs)] > 0
