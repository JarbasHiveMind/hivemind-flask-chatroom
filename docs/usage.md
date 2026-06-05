# Usage guide

This page covers identity provisioning, multi-user routing, and the HTTP message
API. For install and the quickstart, see the [README](../README.md).

## Identity provisioning

The chatroom is a single HiveMind satellite. It does not take credentials on the
command line; instead it reads the HiveMind **identity file** at
`~/.config/hivemind/_identity.json`. Populate it once with the
[`hivemind-bus-client`](https://github.com/JarbasHiveMind/hivemind-websocket-client)
CLI using an access key from `hivemind-core add-client`:

```bash
hivemind-client set-identity \
  --key <access-key> \
  --password <password> \
  --host 127.0.0.1 --port 5678 \
  --siteid flask
hivemind-client test-identity      # confirm it connects
```

`--host` may be a bare host or a `ws://` / `wss://` URL; a bare host is treated
as `ws://`. The `--siteid` becomes the default `site_id` for the satellite.

## Multi-user model

A single `HiveMessageBusClient` carries traffic for every browser user. The app
keeps one OVOS `Session` per username so skills can tell users apart and
per-user preferences persist across turns:

- `username` — identifies the speaker; the assistant's reply is shown as
  `@<username> - <utterance>`.
- `lang` — the language tag sent with each utterance (default `en`).
- `site_id` — the location identifier placed in `message.context` (default
  `flask`).

These come from the room URL, so different users (or rooms) are just different
paths:

```
/chatroom/alice/livingroom/en
/chatroom/bob/kitchen/pt-pt
```

`GET /` redirects to `/chatroom/anon_user/flask/en`.

## HTTP routes

| Method | Route | Purpose |
|--------|-------|---------|
| `GET`  | `/` | Redirect into the default room |
| `GET`  | `/chatroom/<username>/<site_id>/<lang>` | Render the chat room |
| `POST` | `/send_message` | Submit an utterance (form fields: `username`, `lang`, `site_id`, `message`) |
| `GET`  | `/messages` | Return the running message log as JSON; the page polls this |

A `/messages` entry looks like:

```json
{ "incoming": true, "username": "HiveMind", "message": "@alice - the weather is sunny" }
```

`incoming: true` marks a message from the assistant; `false` marks a user line.

## What the assistant sends back

The satellite subscribes to three OVOS bus messages from the hub and appends
them to the room log:

- `speak` — spoken responses, shown as `@<user> - <utterance>`.
- `ovos.common_play.play` — OCP media playback; the artist/title and URI are
  printed as text (in-browser playback is left as an extension point).
- `mycroft.audio.service.play` — legacy audio playback; track list printed as
  text.

## Deployment

The browser-to-Flask hop is plain HTTP. For anything beyond local use, run the
app behind a TLS reverse proxy (nginx, Caddy). The Flask-to-hub hop is always
encrypted end to end by HiveMind, independent of the proxy. Logs default to
`<xdg_state>/hivemind/flask-chat.log`; pass `--log-path stdout` to log to the
console instead.
