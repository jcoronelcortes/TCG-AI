"""The front spot after a KO goes to the body that ATTACKS, and the sacrifice
of a cheap body is a decision the END of our turn takes.

Scenario (`records/registro_008_pasos_094_hasta_109.json`, step 109, turn 8,
episode 93497723, LOST vs Archaludon ex):

    US (3 prizes)                          RIVAL (2 prizes)
    active  -- (their Archaludon ex has    active  Archaludon ex 300/300, 5 {M}
            just taken our Hydrapple ex            **resists {G} -30**
            with 220)
    bench   Meganium 160, 2/4              bench   Duraludon, Wugtrio
            Teal Mask Ogerpon ex 210, **4/3**
            Teal Mask Ogerpon ex 210, 2/3
            Tapu Bulu 140, **0/4, retreat 4**
            Fezandipiti ex 210, 0/3

The first Ogerpon ex is on FOUR effective Grass -- Meganium's Wild Growth makes
each card worth two -- so it swings today for 30+30x(4+5) = 300, which their
Grass resistance takes to 270 on a 300 HP body. Not a knockout. But ONE more
attachment puts it at six: 30+30x(6+5) = 360, resisted 330, and their main
attacker falls on OUR turn for two prizes.

The agent promoted the **Tapu Bulu**, on a bare base score of 142, and lost. Two
separate readings put it there:

  1. The `_best_promote_card` loop priced the Ogerpon's swing at 300 instead of
     270 -- it was the sixth inline copy of the damage arithmetic and the last
     one that still applied weakness without resistance -- and 300 on a 300 HP
     body is a KNOCKOUT.
  2. Because that Ogerpon "could attack", `_promote_setup_ko_attacker` -- the
     almost-ready finisher, +9500, and with it the exemption from the match
     point veto -- was skipped entirely: its guard read `_best_promote_card is
     None`. So `_mp_price_ends_the_game` removed every 2-prize body at -30000
     (their pile is TWO, and a 2-prize ex their 220 takes IS their pile) and the
     only thing left standing was a body that needs four energy, carries none,
     and cannot pay its retreat of four. It could not attack and could not step
     aside.

The guard was never the sentence. What earns the front spot here is that ONE
attachment turns the body into a KNOCKOUT, and a body already able to swing for
less than lethal is the same almost-ready body one attachment earlier. So the
selector is offered the boards where NOBODY KNOCKS OUT
(`PROMOTION_READS_THE_KNOCKOUT_NOT_THE_ATTACK`) instead of only the boards where
nobody can attack at all -- and the damage model it reads that from is the
canonical one, without which that 270 still reads as 300 and the guard never
opens.

The other two rules this file pins are the rest of the same sentence:

  * `PROMOTE_DEFERS_THE_SACRIFICE` (`_promo_deferred_attacker`): when nothing
    knocks out and nothing can even attack, the front spot goes to the body
    CLOSEST to attacking rather than to the biggest one -- but never bought with
    prizes and never with survival. It breaks a tie the measured rules leave to
    raw HP; it does not create one.
  * `SACRIFICE_WAITS_FOR_THE_TURN` (`_active_can_still_be_charged`): the pivot
    that cashes the sacrifice must not fire while the turn can still turn the
    active into an attacker. Promoting a body one attachment short is only
    honest if the retreat waits for the attachment.
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
            / "archaludon_promote_the_charged_attacker_step109.json")

OGERPON = m.Teal_Mask_Ogerpon_ex
TAPU = m.Tapu_Bulu
MEGANIUM = m.Meganium
FEZA = m.Fezandipiti_ex
ARCHALUDON = 190


@pytest.fixture(autouse=True)
def reset_main_state():
    m._init_cards_tracking()
    m.plan = m.AttackPlan()
    m.pre_turn = 0
    yield
    m._init_cards_tracking()


@pytest.fixture
def flags():
    """Rebind the three switches and put them back, whatever the test does."""
    names = ("PROMOTION_READS_THE_KNOCKOUT_NOT_THE_ATTACK",
             "PROMOTE_DEFERS_THE_SACRIFICE",
             "SACRIFICE_WAITS_FOR_THE_TURN")
    before = {n: getattr(m, n) for n in names}
    try:
        yield lambda **kw: [setattr(m, n, v) for n, v in kw.items()]
    finally:
        for n, v in before.items():
            setattr(m, n, v)


def _obs(op_hp=None):
    """The board of step 109.

    `op_hp` raises their Archaludon out of reach: with more HP than the
    completed Myriad Leaf Shower can carry, the Ogerpon stops being a finisher
    and the rule must hand the slot back.
    """
    o = copy.deepcopy(json.load(open(_FIXTURE, encoding="utf-8"))["observation"])
    if op_hp is not None:
        act = o["current"]["players"][1 - o["current"]["yourIndex"]]["active"][0]
        act["hp"] = op_hp
        act["maxHp"] = max(op_hp, act["maxHp"])
    return o


def _chosen(obs):
    yo = obs["current"]["yourIndex"]
    opt = obs["select"]["option"][m.agent(obs)[0]]
    return obs["current"]["players"][yo]["bench"][opt["index"]]


# ---------------------------------------------------------------------------
# 1. The scenario. Without these the rest of the file measures nothing.
# ---------------------------------------------------------------------------

def test_the_fixture_is_the_forced_promotion_at_their_match_point():
    o = _obs()
    yo = o["current"]["yourIndex"]
    mine, them = o["current"]["players"][yo], o["current"]["players"][1 - yo]

    assert not mine["active"]                 # they knocked our active out
    assert o["select"]["context"] == 4        # the forced promotion menu
    assert them["active"][0]["id"] == ARCHALUDON
    assert them["active"][0]["hp"] == 300
    assert len(them["prize"]) == 2            # a 2-prize ex IS their whole pile
    assert len(mine["prize"]) == 3

    charged = [b for b in mine["bench"]
               if b["id"] == OGERPON and len(b["energies"]) == 4]
    assert len(charged) == 1, "el escenario exige el Ogerpon ex a 4 efectivas"
    tapu = [b for b in mine["bench"] if b["id"] == TAPU]
    assert tapu and not tapu[0]["energies"], "el Tapu Bulu entra a 0 energias"


def test_the_charged_ogerpon_swings_today_but_does_not_knock_out():
    """270 on a 300 HP body: it can attack, and that is exactly the trap.

    Archaludon ex is the one archetype in the meta that RESISTS us, which is
    what the sixth inline copy of the damage arithmetic did not know: it
    doubled for weakness and never subtracted, so 270 read as 300 and 300 is a
    knockout on a 300 HP body. This pins the canonical model instead.
    """
    assert m.card_table[ARCHALUDON].resistance == m.card_table[OGERPON].energyType
    assert m.card_table[ARCHALUDON].weakness != m.card_table[OGERPON].energyType

    o = m.to_observation_class(_obs())
    yo = o.current.yourIndex
    ogerpon = next(b for b in o.current.players[yo].bench
                   if b.id == OGERPON and len(b.energies) == 4)
    arch = o.current.players[1 - yo].active[0]

    # Myriad Leaf Shower counts the energy on BOTH actives: 4 ours + 5 theirs.
    today = m._our_effective_damage(ogerpon, arch, 30 + 30 * (4 + 5),
                                    meganium_active=True)
    assert today == 270 < arch.hp, "hoy pega, pero NO noquea"

    # One more attachment is worth TWO under Wild Growth: 6 ours + 5 theirs.
    completed = m._our_effective_damage(ogerpon, arch, 30 + 30 * (6 + 5),
                                        meganium_active=True)
    assert completed == 330 >= arch.hp, "con una carga mas, si noquea"


def test_the_promotion_loop_no_longer_reads_that_swing_as_a_knockout():
    """The defect underneath the guard: `_best_promote_key[0]` is the flag the
    widened guard reads, and with the old weakness-only arithmetic it was 1 --
    the board would have looked like 'somebody already knocks out' and the
    selector would have stayed shut for a second, independent reason."""
    seen = {}
    orig = m.score_option

    def spy(ctx, opt, score):
        if getattr(ctx, "_forced_ko_promote", False):
            seen["key"] = ctx._best_promote_key
            seen["setup"] = ctx._promote_setup_ko_attacker
        return orig(ctx, opt, score)

    m.score_option = spy
    try:
        m.agent(_obs())
    finally:
        m.score_option = orig

    assert seen["key"] is not None
    assert seen["key"][0] == 0, (
        "270 sobre 300 no es un remate: si lo fuera, el guard 'nadie noquea' "
        f"no se abriria; leyo {seen['key']}")
    assert seen["setup"] is not None and seen["setup"].id == OGERPON


def test_the_tapu_bulu_can_neither_attack_nor_step_aside():
    """The body the old reading promoted: 0/4 energy and a retreat it cannot pay."""
    o = _obs()
    yo = o["current"]["yourIndex"]
    tapu = next(b for b in o["current"]["players"][yo]["bench"]
                if b["id"] == TAPU)
    assert len(tapu["energies"]) < m.ATTACK_ENERGY_REQ_BASE[TAPU]
    assert len(tapu["energies"]) < m.RETREAT_COST[TAPU]


# ---------------------------------------------------------------------------
# 2. The rule
# ---------------------------------------------------------------------------

def test_the_front_spot_goes_to_the_body_one_attachment_from_lethal():
    assert _chosen(_obs())["id"] == OGERPON, (
        "sube el Ogerpon ex a 4 efectivas -- una carga de 360 sobre su "
        "Archaludon de 300 -- y no el Tapu Bulu clavado a 0/4")


def test_the_body_it_beats_is_the_one_that_cannot_move():
    o = _obs()
    picked = _chosen(o)
    assert picked["id"] != TAPU
    assert len(picked["energies"]) >= m.RETREAT_COST[picked["id"]], (
        "el cuerpo promovido conserva su SALIDA: si la Grass no llega, se "
        "retira y el muro sube entonces")


# ---------------------------------------------------------------------------
# 3. Its controls: each one puts the old answer back
# ---------------------------------------------------------------------------

def test_with_the_switch_off_the_nailed_wall_returns(flags):
    """The rule is the ONLY difference between the two answers."""
    flags(PROMOTION_READS_THE_KNOCKOUT_NOT_THE_ATTACK=False)
    assert _chosen(_obs())["id"] == TAPU


def test_a_knockout_out_of_reach_is_not_a_knockout(flags):
    """With their active beyond what the completed attack carries, the Ogerpon
    is no longer a finisher: it would swing for less than lethal and die for two
    prizes, and the sacrifice rules are right again."""
    picked = _chosen(_obs(op_hp=400))
    assert picked["id"] != OGERPON, (
        "330 no llega a 400: sin remate no hay exencion y el veto de match "
        f"point vuelve a mandar; promovio {picked['id']}")


def test_the_rule_only_speaks_when_nothing_knocks_out(flags):
    """The guard is 'nobody knocks out', and it is read from the corrected
    damage model. Give their Archaludon so much HP that even the completed
    attack falls short and the selector must go quiet again -- which is the
    same control as `test_a_knockout_out_of_reach_is_not_a_knockout`, asked of
    the flag instead of the answer."""
    seen = {}
    orig = m.score_option

    def spy(ctx, opt, score):
        if getattr(ctx, "_forced_ko_promote", False):
            seen["setup"] = ctx._promote_setup_ko_attacker
        return orig(ctx, opt, score)

    m.score_option = spy
    try:
        m.agent(_obs(op_hp=400))
    finally:
        m.score_option = orig

    assert seen.get("setup") is None, (
        "330 no llega a 400: sin remate el selector no debe nombrar a nadie")


# ---------------------------------------------------------------------------
# 4. The deferred attacker never buys the slot with prizes or with survival
# ---------------------------------------------------------------------------

def test_the_deferred_attacker_does_not_outbid_a_cheaper_body():
    """`_promo_deferred_attacker` breaks a tie; it does not create one.

    Emptying the charged Ogerpon leaves a board where nothing knocks out and
    nothing can attack. The 2-prize ex must still not take the slot from the
    1-prize bodies: the discount the sacrifice is priced on is real here --
    their pile is at two, so a 1-prize body does NOT close their count and an
    ex does. "The turn can improve the situation" is not a licence to pay for
    the improvement in advance.
    """
    o = _obs()
    yo = o["current"]["yourIndex"]
    for b in o["current"]["players"][yo]["bench"]:
        if b["id"] == OGERPON:
            b["energies"], b["energyCards"] = [], []
    picked = _chosen(o)
    assert picked["id"] not in m.OUR_EX_IDS, (
        "con todo mudo, el cuerpo de 2 premios no compra el frente; "
        f"promovio {picked['id']}")


def _all_doomed_board(op_prizes=5):
    """The band `_promo_deferred_attacker` lives in, WITH the HP inversion that
    makes the rule the difference.

    Only 2-prize ex on the bench, so prizes no longer separate them; their
    Archaludon takes all of them, so survival does not either; and nothing can
    attack, because the charged Ogerpon is emptied. What the measured rules have
    left at that point is raw HP -- and the body one attachment from attacking
    is the DAMAGED one, at 120 against two intact 210s. That inversion is the
    whole point: without it the base score's own `+ energy_count` term already
    prefers the body with Grass on it and the rule would be measuring nothing.

    `op_prizes` moves them off their match point: at two prizes `_mp_last_stand`
    speaks first and rightly so, which is exactly where this rung was placed
    below it.
    """
    o = _obs()
    yo = o["current"]["yourIndex"]
    o["current"]["players"][1 - yo]["prize"] = [None] * op_prizes
    mine = o["current"]["players"][yo]
    mine["bench"] = [b for b in mine["bench"] if b["id"] in (OGERPON, FEZA)]
    for b in mine["bench"]:
        if b["id"] == OGERPON and len(b["energies"]) == 4:
            b["energies"], b["energyCards"] = [], []
        elif b["id"] == OGERPON and len(b["energies"]) == 2:
            b["hp"] = 120
    o["select"]["option"] = [{"area": 5, "index": i, "playerIndex": 0, "type": 3}
                             for i in range(len(mine["bench"]))]
    return o


def test_with_nothing_surviving_the_front_goes_to_the_body_closest_to_attacking():
    picked = _chosen(_all_doomed_board())
    assert picked["id"] == OGERPON and len(picked["energies"]) == 2, (
        "entre cuerpos igual de caros y todos condenados, sube el que esta a "
        f"UNA carga de atacar y puede pagar su retirada; promovio {picked}")
    assert picked["hp"] == 120, "y lo hace AUNQUE sea el de menos PV"


def test_with_the_switch_off_the_bigger_mute_tank_takes_the_slot_back(flags):
    flags(PROMOTE_DEFERS_THE_SACRIFICE=False)
    picked = _chosen(_all_doomed_board())
    assert len(picked["energies"]) == 0 and picked["hp"] == 210, (
        "sin la regla el desempate cae en los PV crudos y sube el tanque mudo; "
        f"promovio {picked}")


def test_at_their_match_point_the_last_stand_still_speaks_first(flags):
    """The rung is 9200 and `PROMO_LAST_STAND` is 9450, on purpose: when their
    next knockout ends the game, who absorbs the reply outranks who attacks
    soonest."""
    o = _all_doomed_board(op_prizes=2)
    assert len(o["current"]["players"][1 - o["current"]["yourIndex"]]["prize"]) == 2
    picked = _chosen(o)
    assert len(picked["energies"]) == 0, (
        "a su match point manda el last stand, no este desempate; "
        f"promovio {picked}")


# ---------------------------------------------------------------------------
# 5. The other half: the sacrifice waits while the turn can still charge
# ---------------------------------------------------------------------------

def test_a_body_already_able_to_attack_is_not_waiting_for_anything():
    """`_active_can_still_be_charged` is about a body one attachment SHORT.

    It is the guard that keeps the wait from swallowing every pivot: an active
    that already reaches its cost is not waiting on an energy, so the retreat
    ladder above it is untouched.
    """
    from ptcg.calc.damage import _active_can_still_be_charged

    class _S:
        pass

    st = _S()
    st.active = [type("P", (), {"id": OGERPON, "energies": [1, 1, 1],
                                "energyCards": []})()]
    assert _active_can_still_be_charged(
        st, _S(), {}, {}, 0) is False


def test_with_no_active_there_is_nothing_to_charge():
    from ptcg.calc.damage import _active_can_still_be_charged

    class _S:
        pass

    st = _S()
    st.active = []
    assert _active_can_still_be_charged(st, _S(), {}, {}, 0) is False
