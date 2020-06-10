from hivemind_chatroom import get_connection
from hivemind_chatroom import MessageHandler
from flask import Flask, render_template, request, redirect, url_for, \
    jsonify, Response

app = Flask(__name__)

hivemind = None


@app.route('/', methods=['GET'])
def general():
    room = "general"
    return redirect(url_for("chatroom", room=room))


@app.route('/<room>', methods=['GET'])
def chatroom(room):
    return render_template('room.html', room=room)


@app.route('/messages/<room>', methods=['GET'])
def messages(room):
    return jsonify(MessageHandler.get_messages(room))


@app.route('/send_message/<room>', methods=['POST'])
def send_message(room):
    hivemind.say(request.form['message'], request.form['username'], room)
    return redirect(url_for("chatroom", room=room))


def main():
    global hivemind
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--access_key", help="access key",
                        default="RESISTENCEisFUTILE")
    parser.add_argument("--crypto_key", help="payload encryption key",
                        default="resistanceISfutile")
    parser.add_argument("--name", help="human readable device name",
                        default="JarbasChatRoomTerminal")
    parser.add_argument("--host", help="HiveMind host",
                        default="wss://127.0.0.1")
    parser.add_argument("--port", help="HiveMind port number", default=5678)
    parser.add_argument("--flask-port", help="Chatroom port number",
                        default=8081)
    parser.add_argument("--flask-host", help="Chatroom host",
                        default="0.0.0.0")
    args = parser.parse_args()
    hivemind = get_connection(args.host, args.port, args.name,
                              args.access_key, args.crypto_key)
    hivemind.run_threaded()
    app.run(args.flask_host, args.flask_port)


if __name__ == "__main__":
    main()
