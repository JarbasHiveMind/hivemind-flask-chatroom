"""End-to-end tests for the HiveMind Flask chatroom satellite.

These boot a *real* hivemind-core master in-process via hivescope's loopback
WebSocket transport and drive the *real* chatroom ``MessageHandler`` over a
*real* ``HiveMessageBusClient``. The only thing mocked is the Flask **browser
surface**:

* incoming (browser -> Flask) — instead of an HTTP ``POST /send_message`` from a
  browser, the test calls ``harness.send(text)``, which invokes the exact
  ``MessageHandler.say(...)`` code path the route runs once it has parsed the
  form fields.
* outgoing (Flask -> browser) — instead of the browser polling ``GET /messages``
  over HTTP, the test reads ``harness.messages`` (the same
  ``MessageHandler.messages`` list the route serialises to JSON).

Everything between the chatroom and the hub is the genuine production
``HiveMessageBusClient`` + hivemind-core stack over a localhost WebSocket
(hivescope's loopback hub). There is no ``importorskip`` / ``skipif`` — the full
2.x stack is a hard ``[e2e]`` dependency.
"""
import time

import pytest
from ovos_bus_client.message import Message
from ovos_bus_client.session import Session

pytestmark = pytest.mark.timeout(60)


# ---------------------------------------------------------------------------
# Connection / handshake
# ---------------------------------------------------------------------------

def test_chatroom_connects_to_master(chatroom_harness):
    """The real chatroom client completes the HiveMind handshake against a real
    master; a connected peer appears in the master's peer table."""
    assert chatroom_harness.bus.connected_event.is_set()
    assert chatroom_harness.master.connected_peers(), \
        "chatroom peer not registered at master"
    assert chatroom_harness.peer


# ---------------------------------------------------------------------------
# Inbound — a chat message reaches the hub's agent bus
# ---------------------------------------------------------------------------

def test_chat_message_reaches_hub(chatroom_harness):
    """A message typed in the room (via say) reaches the master's OVOS agent bus.

    This is the core promise: browser line -> Flask -> hive bus -> hub.
    """
    seen = []
    chatroom_harness.master.agent_protocol.bus.on(
        "recognizer_loop:utterance", seen.append)

    chatroom_harness.send("what is the weather", username="alice")

    deadline = time.monotonic() + 5.0
    while time.monotonic() < deadline and not seen:
        time.sleep(0.02)

    assert seen, "chat message never reached the agent bus"
    assert seen[0].data["utterances"] == ["what is the weather"]


def test_chat_message_recorded_as_bus_message(chatroom_harness):
    """The master records the injected utterance as a BUS HiveMessage."""
    chatroom_harness.send("hello hive", username="alice")

    rec = chatroom_harness.master.recorder.wait_for(
        "recognizer_loop:utterance", direction="bus_inject", timeout=5.0)
    assert rec is not None, "utterance not recorded at master"


def test_chat_message_carries_user_lang(chatroom_harness):
    """The room stamps the user's configured lang onto outbound utterances."""
    seen = []
    chatroom_harness.master.agent_protocol.bus.on(
        "recognizer_loop:utterance", seen.append)

    chatroom_harness.send("olá", username="bob", lang="pt-pt", site_id="kitchen")

    deadline = time.monotonic() + 5.0
    while time.monotonic() < deadline and not seen:
        time.sleep(0.02)

    assert seen, "utterance never reached the agent bus"
    assert seen[0].data.get("lang") == "pt-pt"


def test_multiple_users_arrive_in_order(chatroom_harness):
    """Lines from several room users reach the hub in send order (FIFO)."""
    seen = []
    chatroom_harness.master.agent_protocol.bus.on(
        "recognizer_loop:utterance", seen.append)

    sent = [("alice", "one"), ("bob", "two"), ("alice", "three")]
    for user, utt in sent:
        chatroom_harness.send(utt, username=user)
        time.sleep(0.05)

    deadline = time.monotonic() + 5.0
    while time.monotonic() < deadline and len(seen) < len(sent):
        time.sleep(0.02)

    got = [m.data["utterances"][0] for m in seen]
    assert got == [utt for _, utt in sent], f"expected order broke: {got}"


def test_user_line_appended_to_room_log(chatroom_harness):
    """The user's own message is appended to the room log as an outgoing line —
    what the browser sees when it polls GET /messages."""
    chatroom_harness.send("good morning", username="alice")
    own = [m for m in chatroom_harness.messages if not m["incoming"]]
    assert own, "user's own line was not added to the room log"
    assert own[-1] == {"incoming": False, "username": "alice",
                       "message": "good morning"}


# ---------------------------------------------------------------------------
# Outbound — a speak from the hub is routed back into the room
# ---------------------------------------------------------------------------

def test_speak_from_hub_routed_into_room(chatroom_harness):
    """A `speak` emitted by the hub for the chatroom peer reaches the real bus,
    the real handle_speak runs, and the reply lands in the room log prefixed with
    the addressed user — what the browser would render."""
    chatroom_harness.master.emit_on_bus(Message(
        "speak",
        {"utterance": "the weather is sunny"},
        {"destination": chatroom_harness.peer, "user": "alice",
         "session": Session(session_id="alice").serialize()},
    ))

    incoming = chatroom_harness.wait_for_incoming(timeout=5.0)
    assert incoming, "hub speak never reached the room"
    assert incoming[-1]["message"] == "@alice - the weather is sunny"
    assert incoming[-1]["username"] == "HiveMind"


def test_full_round_trip(chatroom_harness):
    """A user types a message, the hub answers with a speak addressed to that
    user, and the reply is routed back into the room. Exercises both directions
    over the real bus in one flow."""
    seen = []
    chatroom_harness.master.agent_protocol.bus.on(
        "recognizer_loop:utterance", seen.append)

    chatroom_harness.send("tell me a joke", username="alice")

    deadline = time.monotonic() + 5.0
    while time.monotonic() < deadline and not seen:
        time.sleep(0.02)
    assert seen, "utterance never reached the hub"

    # the hub answers the addressed user
    chatroom_harness.master.emit_on_bus(Message(
        "speak",
        {"utterance": "why did the bee get married"},
        {"destination": chatroom_harness.peer, "user": "alice",
         "session": Session(session_id="alice").serialize()},
    ))

    incoming = chatroom_harness.wait_for_incoming(timeout=5.0)
    assert any("why did the bee get married" in m["message"] for m in incoming), \
        "hub reply was not routed back into the room"


def test_ocp_play_from_hub_rendered_as_text(chatroom_harness):
    """An `ovos.common_play.play` from the hub is rendered into the room as the
    artist/title and URI text lines."""
    chatroom_harness.master.emit_on_bus(Message(
        "ovos.common_play.play",
        {"media": {"artist": "Pixies", "title": "Hey",
                   "uri": "https://example.com/hey.mp3"}},
        {"destination": chatroom_harness.peer},
    ))

    incoming = chatroom_harness.wait_for_incoming(timeout=5.0)
    rendered = [m["message"] for m in incoming]
    assert any("Pixies - Hey" in r for r in rendered), \
        f"OCP play not rendered into the room: {rendered}"
