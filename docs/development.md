# Development guide

This page covers packaging, the test layout, and the end-to-end harness. For
install and usage, see the [README](../README.md) and [usage.md](./usage.md).

## Packaging

`pyproject.toml` is the single source of truth. There is no `setup.py`,
`requirements.txt`, or `MANIFEST.in`.

- The version is dynamic, read from `hivemind_chatroom/version.py`
  (`[tool.setuptools.dynamic]` → `version = { attr =
  "hivemind_chatroom.version.__version__" }`). The shared OpenVoiceOS release
  workflows bump that file from conventional-commit prefixes; never edit it by
  hand.
- Runtime dependencies (`[project.dependencies]`): `flask`, `hivemind-bus-client`
  (`>=0.9.2a1,<1.0.0`, the bus-client 2.x line), `ovos-bus-client`
  (`>=2.0.0a3,<3.0.0`), `ovos-utils`. The pre-release floors are pinned as
  *minimum versions* so the resolver picks the 2.x-compatible alphas **without**
  `--pre`.
- The `[e2e]` extra adds the test stack: `pytest`, `pytest-timeout`,
  `hivescope`, `hivemind-core`, the agent/plugin/db packages, and `ovos-workshop`
  — again floored as pre-release min-pins so `uv`/`pip` resolve them with no
  `--pre`. The `[test]` extra is a back-compat alias pointing at `[e2e]` for the
  shared CI workflows.

## Test layout

A single `tests/` directory (no parallel `test/`):

```
tests/
  conftest.py              # pytest_plugins + the e2e chatroom_harness fixture
  test_smoke.py            # unit smoke tests — no network, bus is stubbed
  e2e/
    test_chatroom_e2e.py   # real hub + real chatroom round trip
    test_acl.py            # ACL policy-admission conformance (shared)
    test_bridge1_conformance.py  # OVOS-BRIDGE-1 / SESSION conformance (shared)
```

Run them with:

```bash
pip install -e ".[e2e]"
pytest tests/                # everything
pytest tests/test_smoke.py   # unit only
pytest tests/e2e/            # e2e only
```

There is no `importorskip` / `skipif` to dodge a missing dependency — the
`[e2e]` extra installs the full HiveMind 2.x stack, so every test runs for real.
(The single `skip` in the bridge conformance suite is an optional spec *MAY* the
bridge does not implement; the `xfail`s mark intentional defence-in-depth
behaviour, not pending merges.)

## How the e2e harness works

`tests/conftest.py` boots a **real** `hivemind-core` master in-process over
hivescope's loopback WebSocket transport, pre-registers one satellite key, and
connects a **real** `HiveMessageBusClient` to it. That live bus is injected into
the production `MessageHandler` via `MessageHandler.connect(bus=...)`, which binds
the real `speak` / `ovos.common_play.play` / `mycroft.audio.service.play`
handlers.

The Flask **browser surface** is the only thing mocked, and it is mocked by
calling the same functions the routes call rather than going over HTTP:

| Browser action | Flask route | What the test calls instead |
|----------------|-------------|-----------------------------|
| submit a chat line | `POST /send_message` | `harness.send(text)` → `MessageHandler.say(...)` |
| poll for replies | `GET /messages` | `harness.messages` → `MessageHandler.messages` |

So a test message flows:

```
harness.send()  →  MessageHandler.say()  →  real HiveMessageBusClient
   →  real localhost WebSocket  →  real hivemind-core master (agent bus)
```

and a reply flows back the same way:

```
master.emit_on_bus(speak, destination=peer)  →  real WebSocket
   →  chatroom's real HiveMessageBusClient  →  MessageHandler.handle_speak()
   →  MessageHandler.messages  (what GET /messages would return)
```

`test_full_round_trip` exercises both legs in one flow. The unit smoke tests in
`test_smoke.py` cover the Flask routes themselves through Flask's `test_client`
with the bus stubbed, so no socket is opened there.

## CI

All CI is wired to the shared
[OpenVoiceOS/gh-automations](https://github.com/OpenVoiceOS/gh-automations)
reusable workflows at `@dev` — never hand-rolled: `build_tests` (build +
clean-install + unit smoke across Python 3.10–3.13), `e2e_tests` (the
`tests/e2e/` suite on 3.11), `coverage`, `lint` (ruff), `license_tests`,
`pip_audit`, `release-preview`, and `repo-health`, alongside the
`conventional-label`, `publish_stable`, and `release_workflow` release jobs.
