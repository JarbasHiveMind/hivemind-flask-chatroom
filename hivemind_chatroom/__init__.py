from twisted.internet import reactor
from jarbas_hive_mind import HiveMindConnection
from jarbas_hive_mind.slave.terminal import HiveMindTerminal
from jarbas_utils import create_daemon
from jarbas_utils.log import LOG
from jarbas_utils.messagebus import Message

platform = "JarbasFlaskChatRoomV0.1"


class MessageHandler:
    messages = {}

    @staticmethod
    def append_message(incoming, message, username, room):
        if room not in MessageHandler.messages:
            MessageHandler.messages[room] = []
        MessageHandler.messages[room].append({'incoming': incoming,
                                              'username': username,
                                              'message': message})

    @staticmethod
    def get_messages(room):
        return MessageHandler.messages.get(room, [])


class JarbasWebTerminal(HiveMindTerminal):
    _autorun = False

    # terminal
    def say(self, utterance, username="Anon", room="general"):
        MessageHandler.append_message(False, utterance, username, room)
        msg = {"data": {"utterances": [utterance],
                        "lang": "en-us"},
               "type": "recognizer_loop:utterance",
               "context": {"source": platform,
                           "room": room,
                           "user": username,
                           "destination": "hive_mind",
                           "platform": platform}}
        self.send_to_hivemind_bus(msg)

    def speak(self, utterance, username="Mycroft", room="general"):
        MessageHandler.append_message(True, utterance, username, room)

    # parsed protocol messages
    def handle_incoming_mycroft(self, message):
        assert isinstance(message, Message)
        if message.msg_type == "speak":
            room = message.context["room"]
            user = message.context["user"]
            utterance = message.data["utterance"]
            self.speak(utterance, room=room)
        elif message.msg_type == "hive.complete_intent_failure":
            LOG.error("complete intent failure")
            room = message.context["room"]
            user = message.context["username"]
            utterance = "I don't know how to answer that"
            self.speak(utterance, room=room)

    def run(self):
        reactor.run()

    def run_threaded(self):
        create_daemon(reactor.run, args=(False,))


def get_connection(host="wss://127.0.0.1",
                   port=5678, name="JarbasChatRoomTerminal",
                   access_key="RESISTENCEisFUTILE",
                   crypto_key="resistanceISfutile",
                   useragent=platform):
    con = HiveMindConnection(host, port)
    # internal flag, avoid starting twisted reactor
    con._autorun = False

    terminal = JarbasWebTerminal(crypto_key=crypto_key,
                                 headers=con.get_headers(name, access_key),
                                 useragent=useragent)

    return con.connect(terminal)
