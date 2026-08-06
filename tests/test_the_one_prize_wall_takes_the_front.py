"""The one-prize wall takes the front even when nothing is threatening yet.

Scenario (`records/registro_002_pasos_012_hasta_034.json`, step 25, turn 2 --
our first turn, going second, vs Alakazam):

    US (6 prizes)                          RIVAL (Alakazam)
    active  Teal Mask Ogerpon ex 210 (1 {G})  active  Shaymin 80
    bench   Applin 40                          bench   Abra 50, Abra 50
            Teal Mask Ogerpon ex 210 (2 {G})
    hand    Bayleef, Ultra Ball x2, Dipplin, **Tapu Bulu x2**, Meganium,
            Grass, Forest, **Lillie's Determination**

The agent played the Lillie's, which shuffles the whole hand into the deck, and
BOTH Tapu Bulu went with it. That half is already answered by the rule of
`tests/test_first_turn_one_prize_wall.py`: on our first turn the wall goes down
before the refill can take it.

WHAT THIS FILE ADDS is the second half of the same turn (user, ago 2026). With
the wall on the bench the turn still closed in END, with a 2-prize ex in front,
because the pivot asked for a THREAT: their projection had to knock our body in
front down. On this board it does not -- a bare Shaymin does not reach 210 HP --
so the ex stayed in front and the record shows what that is worth against a deck
whose whole plan is knocking things out.

THE SECOND ARM (user): the prize count is a reason on its own. An ex in front is
a 2-prize body sitting where a 1-prize body could sit; their bench is not
assembled yet, so the KO does not come this turn or the next -- and by the time
it does, the swap is no longer free, because an ex with its energy on it cannot
be pulled back for one Grass. Paying the fee now buys three things: an opponent
who has to chew through a body that endures, ONE prize instead of two when it
falls, and the turns in between to build the bench.

WHAT THE ARM DOES NOT DO, and it is the difference with the threat arm: it does
not BUY the fee. Diverting the one attachment of the turn to a body we are about
to walk away from is an energy that does not go to the attacker being assembled;
only a threat that lands next turn pays for that. The prize arm fires when the
fee is ALREADY on the active -- here, the Grass that Teal Dance attached this
same turn.

THE MATCHUP THAT DOES NOT WANT IT (user): Crustle and Cornerstone Mask Ogerpon
ex. There our ex do ZERO damage to what is in front, so the one-prize body is
not a shield we spend, it is the only attacker we have -- and the ladder already
puts it down as such. Hiding an ex behind our own attacker, and burning on the
retreat the energy that should be assembling it, is the opposite of the plan.
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

import main as m
from state_builder import Scenario, pk

_FIXTURE = ROOT / "tests" / "fixtures" / "alakazam_t2_the_wall_takes_the_front_step25.json"

G = int(m.EnergyType.GRASS)

TAPU = m.Tapu_Bulu
OGERPON = m.Teal_Mask_Ogerpon_ex
SHAYMIN = 343      # the opponent's opener in the record: 80 HP, no attack that reaches us


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
    m._dodge_immune_serial = None
    m._dodge_immune_turn = -1
    yield
    m._init_cards_tracking()


def _prizes(card_id):
    return m.prize_count(SimpleNamespace(id=card_id, energyCards=[], tools=[]))


def _obs_fixture():
    return copy.deepcopy(json.load(open(_FIXTURE, encoding="utf-8"))["observation"])


def _walk(o, limit=8):
    """Play the turn out: every PLAY is applied and the menu is trimmed, the
    way the other record tests do it, until a decision that is not a PLAY.

    It returns the list of ids played and the OptionType the turn closed with.
    The hand refill is NOT simulated (the Lillie's does not shuffle here): what
    is being read is the ORDER of the decisions and how the turn CLOSES.
    """
    played = []
    for _ in range(limit):
        opt = o["select"]["option"][m.agent(copy.deepcopy(o))[0]]
        if opt.get("type") != int(m.OptionType.PLAY):
            return played, int(opt["type"])
        cur = o["current"]
        mine = cur["players"][cur["yourIndex"]]
        card = mine["hand"][opt["index"]]
        data = m.card_table[card["id"]]
        played.append(card["id"])
        mine["hand"] = [c for i, c in enumerate(mine["hand"]) if i != opt["index"]]
        mine["handCount"] = len(mine["hand"])
        if data.cardType == int(m.CardType.POKEMON):
            mine["bench"] = list(mine["bench"]) + [{
                "id": card["id"], "serial": card["serial"],
                "playerIndex": cur["yourIndex"], "hp": data.hp, "maxHp": data.hp,
                "appearThisTurn": True, "energies": [], "energyCards": [],
                "tools": [], "preEvolution": []}]
        o["select"]["option"] = [x for i, x in enumerate(o["select"]["option"])
                                 if x is not opt]
        for x in o["select"]["option"]:
            if x.get("type") == int(m.OptionType.PLAY) and x.get("index", 0) > opt["index"]:
                x["index"] -= 1
    raise AssertionError(f"el turno no cerro en {limit} decisiones: {played}")


def _op_bench_add(o, card_id):
    """Put a body on the OPPONENT's bench (their deck has no accounting)."""
    cur = o["current"]
    riv = cur["players"][1 - cur["yourIndex"]]
    data = m.card_table[card_id]
    riv["bench"] = list(riv["bench"]) + [{
        "id": card_id, "serial": 9000 + len(riv["bench"]),
        "playerIndex": 1 - cur["yourIndex"], "hp": data.hp, "maxHp": data.hp,
        "appearThisTurn": False, "energies": [], "energyCards": [],
        "tools": [], "preEvolution": []}]
    return o


# ---------------------------------------------------------------------------
# 1. The record: nothing threatens us and the ex is still in front
# ---------------------------------------------------------------------------

def test_the_fixture_is_the_turn_2_that_ended_with_the_ex_in_front():
    o = _obs_fixture()
    cur = o["current"]
    mine = cur["players"][cur["yourIndex"]]
    riv = cur["players"][1 - cur["yourIndex"]]

    assert cur["turn"] == 2 and cur["firstPlayer"] != cur["yourIndex"]
    assert not cur["supporterPlayed"]

    # In front, a 2-prize ex with the retreat cost ALREADY on it: the fee of
    # the pivot is the Grass that Teal Dance attached this same turn.
    assert mine["active"][0]["id"] == OGERPON
    assert _prizes(OGERPON) == 2 and _prizes(TAPU) == 1
    assert len(mine["active"][0]["energies"]) >= m.RETREAT_COST[OGERPON]
    # ...and no attack: Myriad Leaf Shower needs more than what it carries.
    assert len(mine["active"][0]["energies"]) < m.ATTACK_ENERGY_REQ[OGERPON]

    # Nothing on their side reaches those 210 HP: the THREAT arm is off, which
    # is why this board used to close the turn with the ex in front.
    assert m._op_active_attack_damage_to(
        SimpleNamespace(id=riv["active"][0]["id"], energies=[], hp=80, maxHp=80),
        SimpleNamespace(id=OGERPON, energies=[], hp=210, maxHp=210),
        riv["handCount"]) < 210

    hand = [c["id"] for c in mine["hand"]]
    assert hand.count(TAPU) == 2 and m.Lillie_Determination in hand
    offered = {mine["hand"][opt["index"]]["id"]
               for opt in o["select"]["option"]
               if opt["type"] == int(m.OptionType.PLAY)}
    assert {TAPU, m.Lillie_Determination} <= offered
    assert any(opt["type"] == int(m.OptionType.RETREAT)
               for opt in o["select"]["option"]), (
        "el menu YA ofrecia la retirada: la decision es de eleccion, no de legalidad")


def test_the_wall_goes_down_and_the_turn_closes_with_the_retreat():
    played, closed = _walk(_obs_fixture())
    assert played[0] == TAPU, (
        f"el muro se baja ANTES del refresco: la Lillie's baraja la mano "
        f"entera y se lo lleva al mazo; jugo {played}")
    assert m.Lillie_Determination in played, (
        "el refresco no se veta, se pospone: se juega en el mismo turno")
    assert closed == int(m.OptionType.RETREAT), (
        f"con el muro en banca y la retirada ya pagada, el turno termina "
        f"poniendolo delante; cerro en {m.OptionType(closed).name}")


def test_the_promotion_brings_up_the_wall_and_not_the_charged_ex():
    # One observation later the SWITCH menu decides WHICH body goes up, and by
    # then nothing on the board says why we retreated: the generic ranking
    # (prizes x 1000 + HP) would promote the charged ex, which is the very body
    # the pivot exists to hide.
    o = (Scenario(turn=2, step=25, tac=14, first_player=1,
                  energy_played=True, supporter_played=True)
         .my_active(pk(OGERPON, energies=[G], fisicas=1))
         .my_bench(pk(TAPU), pk(OGERPON, energies=[G, G], fisicas=2))
         .my_hand(m.Night_Stretcher)
         .op_active(pk(SHAYMIN))
         .op_zones(hand=6, deck=36, prizes=6)
         .promote_after_retreat().build())
    opt = o["select"]["option"][m.agent(o)[0]]
    mine = o["current"]["players"][o["current"]["yourIndex"]]
    assert mine["bench"][opt["index"]]["id"] == TAPU, (
        "tras la retirada sube el muro de 1 premio, no el ex cargado")


# ---------------------------------------------------------------------------
# 2. The matchup where the wall is the attacker: Crustle / Cornerstone
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("op_id,name", [(m.Dwebble_Grass, "Crustle"),
                                        (m.Cornerstone_Mask_Ogerpon_ex, "Cornerstone")])
def test_control_the_wall_is_not_spent_when_it_is_our_attacker(op_id, name):
    # Same board, one body added to their bench. Against these decks our ex do
    # ZERO damage to what they put in front, so the one-prize body is not a
    # shield: it is the only attacker we have. The pivot stands down and the
    # ladder of the matchup -- which puts the same body down as THE attacker --
    # owns the turn.
    played, closed = _walk(_op_bench_add(_obs_fixture(), op_id))
    assert closed != int(m.OptionType.RETREAT), (
        f"vs {name} el Tapu Bulu es el atacante principal: no se gasta como "
        f"muro para esconder un ex detras; jugo {played}")


def test_control_the_exception_reads_the_matchup_and_not_the_body():
    # The exception is switched on by the OPPONENT's deck, not by which card of
    # ours is playing the part: with no Crustle/Cornerstone on their board the
    # same turn does pivot. This is what keeps the rule deck-agnostic.
    _, closed_plain = _walk(_obs_fixture())
    _, closed_wall = _walk(_op_bench_add(_obs_fixture(), m.Dwebble_Grass))
    assert closed_plain == int(m.OptionType.RETREAT)
    assert closed_wall != closed_plain


# ---------------------------------------------------------------------------
# 3. The boundaries of the new arm
# ---------------------------------------------------------------------------

def test_control_turn_1_going_first_denies_nothing():
    # Going FIRST on turn 1 the opponent has not played a card yet: there is no
    # prize to deny and sacrificing early development only slows us down. It is
    # the same seat the prize mismatch already exempts.
    o = _obs_fixture()
    o["current"]["turn"] = 1
    o["current"]["firstPlayer"] = o["current"]["yourIndex"]
    played, closed = _walk(o)
    assert closed != int(m.OptionType.RETREAT), (
        f"primer turno partiendo primeros: no se paga la tasa; jugo {played}")


def _charge_board(op_active):
    """A damaged 2-prize ex in front, the wall on the bench and ONE Grass in
    hand: the only thing that changes between the two runs is what the opponent
    has in front, which is what the threat arm reads."""
    return (Scenario(turn=2, step=20, tac=3, first_player=1,
                     energy_played=False, supporter_played=True)
            .my_active(pk(m.Meowth_ex, hp=50))
            .my_bench(pk(TAPU), pk(m.Applin))
            .my_hand(m.Basic_Grass_Energy)
            .op_active(op_active)
            .op_zones(hand=4, deck=40, prizes=6)
            .menu_hand(with_attachment=True).build())


def _charge_flag(op_active, monkeypatch):
    """`_ft_wall_charge_active` as the turn computed it.

    It is read where the turn HANDS IT OVER (the energy context) and not
    through the decision: on this board the Grass ends up on the active either
    way -- it is a wounded attacker -- so the decision cannot tell the two arms
    apart, and a control that cannot fail is not a control.
    """
    seen = []
    real = m.CtxEnergyScoreBase

    def spy(*a, **kw):
        seen.append(kw.get("_ft_wall_charge_active"))
        return real(*a, **kw)

    monkeypatch.setattr(m, "CtxEnergyScoreBase", spy)
    m.agent(_charge_board(op_active))
    assert seen, "el contexto de energia no llego a construirse"
    return any(seen)


def test_the_threat_arm_buys_the_fee_and_the_prize_arm_does_not(monkeypatch):
    # The two arms differ in exactly one thing: whether they are worth this
    # turn's attachment. With a Chewtle in front (60 damage: it knocks the
    # wounded Meowth ex out and does NOT knock the wall out) the threat arm
    # buys the fee, which is the only thing that makes the engine OFFER the
    # retreat. With a Shaymin in front nothing is threatening: the prize arm
    # waits for a fee that is already paid instead of spending the turn's
    # energy on a body we would be walking away from.
    assert _charge_flag(pk(m.Chewtle, energies=[int(m.EnergyType.WATER)] * 2,
                           fisicas=2), monkeypatch), (
        "con amenaza la tasa se compra por adelantado")
    assert not _charge_flag(pk(SHAYMIN), monkeypatch), (
        "sin amenaza el brazo de premios NO compra la tasa")
