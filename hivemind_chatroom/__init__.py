"""HiveMind Flask Chatroom — a multi-user Flask satellite for HiveMind.

The Flask app, the HiveMind ``MessageHandler``, and the CLI ``main`` entry point
all live in :mod:`hivemind_chatroom.__main__`; they are re-exported here so the
package can be imported as ``hivemind_chatroom`` (tests, embedding) without going
through ``python -m``.
"""
from hivemind_chatroom.__main__ import (
    app,
    bot_name,
    main,
    MessageHandler,
    platform,
)
from hivemind_chatroom.version import __version__

__all__ = [
    "app",
    "bot_name",
    "main",
    "MessageHandler",
    "platform",
    "__version__",
]
