"""Shared pytest config for hivemind-flask-chatroom.

``pytest_plugins`` must live in the *root* conftest.py (pytest does not allow it
in non-top-level conftests), so hivescope's fixtures are registered here for the
whole suite.

The e2e fixtures boot a *real* hivemind-core master in-process via hivescope's
loopback WebSocket transport and connect the *real* chatroom ``MessageHandler``
to it over a real ``HiveMessageBusClient`` handshake. The only thing mocked is
the Flask **browser surface**: instead of going through the HTTP routes / a
websocket, tests call ``MessageHandler.say(...)`` (exactly what ``POST
/send_message`` invokes) and read ``MessageHandler.messages`` (exactly what ``GET
/messages`` serialises). There is no network beyond the localhost loopback
socket and no ``importorskip`` / ``skipif`` guard — the ``[e2e]`` extra installs
the full stack, so every test runs for real.
"""
import time
from dataclasses import dataclass
from typing import List

import pytest
from hivemind_bus_client.client import HiveMessageBusClient
from hivescope.topology import TopologyBuilder

from hivemind_chatroom import MessageHandler, platform

pytest_plugins = ["hivescope.pytest_fixtures"]

# Credentials the loopback master pre-registers and the real chatroom satellite
# authenticates with. A chatroom is a text satellite: it injects utterances and
# receives speak (plus the OCP/legacy playback messages it renders as text).
CHATROOM_ACCESS_KEY = "hivemind_chatroom_e2e_key_0000000000000"
CHATROOM_PASSWORD = "hivemind_chatroom_e2e_password"
CHATROOM_ALLOWED_TYPES = [
    "recognizer_loop:utterance",
    "speak",
    "ovos.common_play.play",
    "mycroft.audio.service.play",
]


@dataclass
class ChatroomHarness:
    """A real chatroom MessageHandler wired to a real loopback master.

    ``send`` drives the mocked Flask stdin side: it calls
    ``MessageHandler.say(...)`` — exactly the code path ``POST /send_message``
    takes once it has parsed the form. ``messages`` is the mocked Flask stdout
    side: the same list ``GET /messages`` serialises to JSON for the polling
    browser. No HTTP server or websocket-to-browser hop exists in the test.
    """

    builder: TopologyBuilder
    master: object
    bus: HiveMessageBusClient

    @property
    def peer(self) -> str:
        peers = self.master.connected_peers()
        assert peers, "no chatroom satellite connected to master"
        return peers[0]

    @property
    def messages(self) -> List[dict]:
        return MessageHandler.messages

    def send(self, utterance: str, username: str = "alice",
             lang: str = "en", site_id: str = "flask") -> None:
        """Submit an utterance as the Flask `/send_message` route would."""
        MessageHandler.say(utterance, username=username, lang=lang,
                           site_id=site_id)

    def wait_for_incoming(self, timeout: float = 5.0) -> List[dict]:
        """Wait until at least one bot/incoming line is appended to the log."""
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            incoming = [m for m in MessageHandler.messages if m["incoming"]]
            if incoming:
                return incoming
            time.sleep(0.02)
        return [m for m in MessageHandler.messages if m["incoming"]]


@pytest.fixture
def chatroom_harness():
    """Boot a loopback master, connect the real chatroom bus, mock the browser.

    Yields a :class:`ChatroomHarness`. Tears the whole stack down afterwards and
    resets the class-level ``MessageHandler`` state so tests stay isolated.
    """
    # clean class-level state from any previous test
    MessageHandler.messages = []
    MessageHandler.sessions.clear()

    builder = TopologyBuilder()
    master = builder.add_master("M0", use_loopback=True)
    master.register_satellite(
        key=CHATROOM_ACCESS_KEY,
        password=CHATROOM_PASSWORD,
        allowed_types=CHATROOM_ALLOWED_TYPES,
    )
    builder.start_all()

    bus = None
    try:
        url = master.network_protocol.url  # ws://127.0.0.1:<port>/
        host, port = url.rstrip("/").rsplit(":", 1)

        bus = HiveMessageBusClient(
            CHATROOM_ACCESS_KEY,
            host=host,
            port=int(port),
            password=CHATROOM_PASSWORD,
            useragent=platform,
        )
        bus.connect(site_id="e2e-flask")

        deadline = time.monotonic() + 10.0
        while time.monotonic() < deadline and not bus.connected_event.is_set():
            time.sleep(0.05)
        assert bus.connected_event.is_set(), \
            "real chatroom client failed to connect to master"

        # Wire the real MessageHandler around the connected bus. connect(bus=...)
        # is the injection seam: it skips the identity-file connect and binds the
        # real speak / OCP / legacy-play handlers onto this live bus.
        MessageHandler.connect(bus=bus)

        harness = ChatroomHarness(builder=builder, master=master, bus=bus)

        deadline = time.monotonic() + 5.0
        while time.monotonic() < deadline and not master.connected_peers():
            time.sleep(0.02)

        yield harness
    finally:
        if bus is not None:
            try:
                bus.close()
            except Exception:
                pass
        MessageHandler.hivemind = None
        MessageHandler.messages = []
        MessageHandler.sessions.clear()
        builder.stop_all()
