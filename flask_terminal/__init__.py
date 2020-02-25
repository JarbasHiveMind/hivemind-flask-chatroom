from twisted.internet import reactor
from jarbas_hive_mind import HiveMindConnection
from jarbas_hive_mind.slave.terminal import HiveMindTerminal
from jarbas_utils import create_daemon
from jarbas_utils.log import LOG
from jarbas_utils.messagebus import Message


platform = "JarbasFlaskTerminalV0.1"


class MessageHandler:
    messages = []

    @staticmethod
    def append_message(incoming, message):
        MessageHandler.messages.append({'incoming': incoming,
                                        'message': message})

    @staticmethod
    def get_messages():
        return MessageHandler.messages


class JarbasWebTerminal(HiveMindTerminal):
    # terminal
    def say(self, utterance):
        MessageHandler.append_message(False, utterance)
        msg = {"data": {"utterances": [utterance],
                        "lang": "en-us"},
               "type": "recognizer_loop:utterance",
               "context": {"source": self.client.peer,
                           "destination": "hive_mind",
                           "platform": platform}}
        self.send_to_hivemind_bus(msg)

    def speak(self, utterance):
        MessageHandler.append_message(True, utterance)

    # parsed protocol messages
    def handle_incoming_mycroft(self, message):
        assert isinstance(message, Message)
        if message.msg_type == "speak":
            utterance = message.data["utterance"]
            self.speak(utterance)
        elif message.msg_type == "hive.complete_intent_failure":
            LOG.error("complete intent failure")
            self.speak('I don\'t know how to answer that')

    def run(self):
        reactor.run()

    def run_threaded(self):
        create_daemon(reactor.run, args=(False,))


def get_connection(host="wss://127.0.0.1",
                   port=5678, name="JarbasWebTerminal",
                   key="dummy_key", crypto_key=None,
                   useragent=platform):
    con = HiveMindConnection(host, port)
    # internal flag, avoid starting twisted reactor
    con._autorun = False

    terminal = JarbasWebTerminal(crypto_key=crypto_key,
                                 headers=con.get_headers(name, key),
                                 useragent=useragent)

    return con.connect(terminal)
