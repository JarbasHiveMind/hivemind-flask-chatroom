from flask_terminal import JarbasWebTerminal, MessageHandler, platform
from jarbas_hive_mind import HiveMindConnection
from jarbas_utils import create_daemon
from flask import Flask, render_template, request, redirect, url_for, jsonify

app = Flask(__name__)

hivemind = None


def get_connection(host="wss://127.0.0.1",
                   port=5678, name="JarbasWebTerminal",
                   key="dummy_key", crypto_key=None,
                   useragent=platform):
    con = HiveMindConnection(host, port)
    con._autorun = False

    terminal = JarbasWebTerminal(crypto_key=crypto_key,
                                 headers=con.get_headers(name, key),
                                 useragent=useragent)

    return con.connect(terminal)


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/messages')
def messages():
    return jsonify(MessageHandler.get_messages())


@app.route('/send_message', methods=['POST'])
def send_message():
    global hivemind
    hivemind.say(request.form['message'])
    return redirect(url_for('index'))


if __name__ == "__main__":
    # TODO argparse
    flask_port = 8081
    flask_host = "127.0.0.1"  # change to 0.0.0.0 if you want external access

    hivemind_port = 5678
    hivemind_host = "wss://127.0.0.1"
    hivemind_key = "dummy_key"
    hivemind_crypto_key = None

    hivemind = get_connection(hivemind_host,
                              hivemind_port,
                              key=hivemind_key,
                              crypto_key=hivemind_crypto_key)
    create_daemon(hivemind.run)

    app.run(flask_host, flask_port)



