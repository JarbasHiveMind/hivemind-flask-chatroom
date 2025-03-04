import argparse
import os
import threading
from collections import defaultdict
from typing import Dict

from flask import Flask, render_template, request, redirect, url_for, \
    jsonify
from ovos_bus_client.message import Message
from ovos_bus_client.session import Session, SessionManager
from ovos_utils.fakebus import FakeBus
from ovos_utils.log import init_service_logger, LOG
from ovos_utils.xdg_utils import xdg_state_home

from hivemind_bus_client import HiveMessageBusClient

platform = "JarbasFlaskChatRoomV0.2"
bot_name = "HiveMind"

app = Flask(__name__)


class MessageHandler:
    messages = []
    hivemind: HiveMessageBusClient = None
    sessions: Dict[str, Session] = defaultdict(Session)
    _lock = threading.Lock()

    @classmethod
    def connect(cls):
        cls.hivemind = HiveMessageBusClient(useragent=platform,
                                            internal_bus=FakeBus())
        cls.hivemind.connect(site_id="flask")
        cls.hivemind.on_mycroft("speak", cls.handle_speak)
        cls.hivemind.on_mycroft("ovos.common_play.play", cls.handle_ocp_play)
        cls.hivemind.on_mycroft('mycroft.audio.service.play', cls.handle_legacy_play)

    @classmethod
    def handle_legacy_play(cls, message: Message):
        tracks = message.data["tracks"]
        # TODO - implement playback in browser if desired
        cls.append_message(True, "\n".join([str(t) for t in tracks]),
                           bot_name)

    @classmethod
    def handle_ocp_play(cls, message: Message):
        track = message.data["media"]
        # TODO - implement playback and nice UI card in browser if desired
        msg = f"{track['artist']} - {track['title']}"
        cls.append_message(True, msg, bot_name)
        cls.append_message(True, track['uri'], bot_name)

    @classmethod
    def handle_speak(cls, message: Message):
        utterance = message.data["utterance"]
        user = message.context["user"]  # could have been handled in skill
        cls.append_message(True, f"@{user} - {utterance}", bot_name)
        # update any changes from ovos-core since we overwrite session per user on every utterance
        cls.sessions[user] = SessionManager.get(message)

    @classmethod
    def say(cls, utterance, username="Anon", lang="en", site_id="flask"):
        cls.append_message(False, utterance, username)
        msg = Message("recognizer_loop:utterance",
                      {"utterances": [utterance], "lang": lang},
                      {"source": platform,
                       "user": username,
                       "destination": "skills",
                       "platform": platform}
                      )

        # keep track of preferences per user
        cls.sessions[username].lang = lang
        cls.sessions[username].site_id = site_id
        cls.sessions[username].session_id = username
        msg.context["session"] = cls.sessions[username].serialize()
        with cls._lock:
            cls.hivemind.session_id = username  # TODO - tied to the base class, allow as kwarg in emit
            cls.hivemind.emit_mycroft(msg)
            cls.hivemind.session_id = "default"

    @classmethod
    def append_message(cls, incoming, message, username):
         cls.messages.append({'incoming': incoming,
                                        'username': username,
                                        'message': message})


@app.route('/', methods=['GET'])
def general():
    return redirect(url_for("chatroom",
                            site_id="flask", lang="en", username="anon_user"))


@app.route('/chatroom/<username>/<site_id>/<lang>', methods=['GET'])
def chatroom(username, site_id, lang):
    return render_template('room.html',
                           username=username, site_id=site_id, lang=lang)


@app.route('/messages', methods=['GET'])
def messages():
    return jsonify(MessageHandler.messages)


@app.route('/send_message', methods=['POST'])
def send_message():
    user = request.form['username'] or "anon_user"
    lang = request.form['lang'] or "en"
    site_id = request.form['site_id'] or "flask"
    MessageHandler.say(request.form['message'],
                       user,
                       lang,
                       site_id)
    return redirect(url_for("chatroom", site_id=site_id,
                            lang=lang, username=user))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", help="Chatroom port number",
                        default=8985)
    parser.add_argument("--host", help="Chatroom host",
                        default="0.0.0.0")
    parser.add_argument('--log-level', type=str, default="DEBUG",
                        help="Set the logging level (e.g., DEBUG, INFO, ERROR).")
    parser.add_argument('--log-path', type=str, default=None, help="Set the directory path for logs.")
    args = parser.parse_args()

    # Set log level
    init_service_logger("flask-chat")
    LOG.set_level(args.log_level)

    # Set log path if provided, otherwise use default
    if args.log_path:
        LOG.base_path = args.log_path
    else:
        LOG.base_path = os.path.join(xdg_state_home(), "hivemind")

    if LOG.base_path == "stdout":
        LOG.info("logs printed to stdout (not saved to file)")
    else:
        LOG.info(f"log files can be found at: {LOG.base_path}/flask-chat.log")

    MessageHandler.connect()
    app.run(args.host, args.port, debug=False)


if __name__ == "__main__":
    main()
