from flask_terminal import get_connection, MessageHandler
from flask import Flask, render_template, request, redirect, url_for, jsonify

app = Flask(__name__)

hivemind = None


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
    hivemind.run_threaded()

    app.run(flask_host, flask_port)



