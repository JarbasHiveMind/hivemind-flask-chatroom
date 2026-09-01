"""Unit smoke tests for hivemind-flask-chatroom.

These run with no network and no real HiveMind connection: the
``MessageHandler.hivemind`` bus is stubbed with an in-process fake so the message
bookkeeping, OVOS ``Session`` handling, and the Flask HTTP routes can be exercised
in isolation. The real-bus / real-hub path is covered by ``tests/e2e``.
"""
from unittest.mock import MagicMock

import pytest
from ovos_bus_client.message import Message

import hivemind_chatroom
from hivemind_chatroom import MessageHandler, app, bot_name, platform


@pytest.fixture(autouse=True)
def _reset_handler():
    """Each test starts from a clean MessageHandler with a fake bus.

    The fake bus records ``emit_mycroft`` calls so outbound utterances can be
    asserted without any socket; nothing here touches the network.
    """
    MessageHandler.messages = []
    MessageHandler.sessions.clear()
    fake = MagicMock()
    fake.emitted = []
    fake.emit_mycroft.side_effect = lambda msg: fake.emitted.append(msg)
    MessageHandler.hivemind = fake
    yield
    MessageHandler.messages = []
    MessageHandler.sessions.clear()
    MessageHandler.hivemind = None


# ---------------------------------------------------------------------------
# Package surface
# ---------------------------------------------------------------------------

def test_package_exports():
    assert hivemind_chatroom.__version__
    assert callable(hivemind_chatroom.main)
    assert hivemind_chatroom.app is app
    assert hivemind_chatroom.MessageHandler is MessageHandler
    assert platform == "JarbasFlaskChatRoomV0.2"
    assert bot_name == "HiveMind"


# ---------------------------------------------------------------------------
# MessageHandler bookkeeping
# ---------------------------------------------------------------------------

def test_append_message_records_log_entry():
    MessageHandler.append_message(False, "hello", "alice")
    assert MessageHandler.messages == [
        {"incoming": False, "username": "alice", "message": "hello"}
    ]


def test_say_emits_utterance_and_logs_user_line():
    MessageHandler.say("what time is it", username="alice", lang="pt-pt",
                       site_id="kitchen")
    # the user's own line is logged as outgoing (incoming=False)
    assert MessageHandler.messages[0] == {
        "incoming": False, "username": "alice", "message": "what time is it"
    }
    # a single mycroft utterance was emitted upstream
    assert len(MessageHandler.hivemind.emitted) == 1
    msg = MessageHandler.hivemind.emitted[0]
    assert msg.msg_type == "recognizer_loop:utterance"
    assert msg.data["utterances"] == ["what time is it"]
    assert msg.data["lang"] == "pt-pt"
    assert msg.context["user"] == "alice"


def test_say_persists_per_user_preferences():
    MessageHandler.say("oi", username="bob", lang="pt-pt", site_id="garden")
    sess = MessageHandler.sessions["bob"]
    assert sess.lang == "pt-pt"
    assert sess.site_id == "garden"
    assert sess.session_id == "bob"


def test_handle_speak_appends_bot_reply():
    msg = Message("speak",
                  {"utterance": "it is sunny"},
                  {"user": "alice", "session": {"session_id": "alice"}})
    MessageHandler.handle_speak(msg)
    assert MessageHandler.messages[-1] == {
        "incoming": True, "username": bot_name, "message": "@alice - it is sunny"
    }


def test_handle_ocp_play_prints_track_text():
    msg = Message("ovos.common_play.play",
                  {"media": {"artist": "Pixies", "title": "Hey",
                             "uri": "file:///hey.mp3"}})
    MessageHandler.handle_ocp_play(msg)
    msgs = [m["message"] for m in MessageHandler.messages]
    assert "Pixies - Hey" in msgs
    assert "file:///hey.mp3" in msgs


def test_handle_legacy_play_prints_track_list():
    msg = Message("mycroft.audio.service.play", {"tracks": ["a.mp3", "b.mp3"]})
    MessageHandler.handle_legacy_play(msg)
    assert MessageHandler.messages[-1]["message"] == "a.mp3\nb.mp3"


# ---------------------------------------------------------------------------
# Flask HTTP surface (test client — no socket, no browser)
# ---------------------------------------------------------------------------

@pytest.fixture
def client():
    app.config.update(TESTING=True)
    return app.test_client()


def test_root_redirects_to_default_room(client):
    resp = client.get("/")
    assert resp.status_code == 302
    assert "/chatroom/anon_user/flask/en" in resp.headers["Location"]


def test_chatroom_renders(client):
    resp = client.get("/chatroom/alice/livingroom/en")
    assert resp.status_code == 200


def test_messages_returns_json_log(client):
    MessageHandler.append_message(True, "@alice - hi", bot_name)
    resp = client.get("/messages")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data == [{"incoming": True, "username": bot_name,
                     "message": "@alice - hi"}]


def test_send_message_drives_say_and_redirects(client):
    resp = client.post("/send_message", data={
        "username": "alice", "lang": "en", "site_id": "flask",
        "message": "hello hive",
    })
    assert resp.status_code == 302
    assert "/chatroom/alice/flask/en" in resp.headers["Location"]
    # the POST routed the utterance through the (faked) bus
    assert MessageHandler.hivemind.emitted[0].data["utterances"] == ["hello hive"]


def test_send_message_defaults_blank_fields(client):
    resp = client.post("/send_message", data={
        "username": "", "lang": "", "site_id": "", "message": "yo",
    })
    assert resp.status_code == 302
    loc = resp.headers["Location"]
    assert "/chatroom/anon_user/flask/en" in loc
