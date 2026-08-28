"""The wire format a language client speaks: json-rpc in a header framed envelope.

Hand written rather than taken from a library, which is a decision worth stating. What a
diagnostics-only server has to understand is six messages, and the framing below is the whole
of it; against that, a dependency would have to be a runtime extra - the two runtime
dependencies of this package are a deliberate claim the tests enforce - and its handlers are
registered through decorators that a coverage gate of 100% has to reach somehow. If the
surface later grows completion, hover and rename, taking a library then is a smaller decision
than owning a protocol implementation from the start would have been.

Bytes rather than text on purpose: ``Content-Length`` counts encoded bytes, so a header read
off a stream that has already decoded utf-8 would be a byte count applied to characters, and
one non-ascii character anywhere in a message would put every following message out of step.
"""

from __future__ import annotations

import json
from typing import IO, Any

_HEADER_SEPARATOR = b":"
_CONTENT_LENGTH = b"content-length"


class ProtocolError(Exception):
    """The framing itself is broken, so the stream cannot be followed any further.

    Without a believable ``Content-Length`` there is no way to tell where the body ends and
    the next header begins; everything after this point would be read out of step. The only
    honest answer is to say so once and stop.
    """


class MessageError(Exception):
    """One framed body that is not a request the server can act on.

    The frame boundary itself survived - the length was read and honoured - so the client
    deserves a json-rpc error in reply and the conversation goes on with the next frame.
    """

    def __init__(self, code: int, message: str) -> None:
        super().__init__(message)
        self.code = code


def read_message(stream: IO[bytes]) -> dict[str, Any] | None:
    """The next message, or ``None`` once the client has stopped sending them.

    ``None`` covers both ways that happens: the stream reaching its end, which is what an
    editor closing the connection looks like, and a header block with no length in it, which
    cannot be followed into a body and is not worth guessing at.
    """
    headers: dict[bytes, bytes] = {}
    while True:
        line = stream.readline()
        if not line:
            return None
        stripped = line.strip()
        if not stripped:
            break
        name, _, value = stripped.partition(_HEADER_SEPARATOR)
        headers[name.strip().lower()] = value.strip()

    raw_length = headers.get(_CONTENT_LENGTH)
    if raw_length is None:
        return None
    try:
        length = int(raw_length)
    except ValueError:
        msg = (
            f"Content-Length is not a number: {raw_length.decode('utf-8', 'replace')!r}; "
            f"the stream cannot be re-synchronised"
        )
        raise ProtocolError(msg) from None
    body = stream.read(length)
    try:
        decoded = json.loads(body.decode("utf-8"))
    except ValueError:
        # Both a decode error and a json error land here: either way the frame held no
        # readable document, and json-rpc has a name and a code for exactly that.
        msg = "the message body is not json"
        raise MessageError(PARSE_ERROR, msg) from None
    if not isinstance(decoded, dict):
        msg = "the message is not a json-rpc request object; batch requests are not supported"
        raise MessageError(INVALID_REQUEST, msg)
    result: dict[str, Any] = decoded
    return result


def write_message(stream: IO[bytes], payload: dict[str, Any]) -> None:
    """Send one message and flush it.

    Flushed every time because the client is waiting on it: a response left in a buffer is a
    client that hangs, which looks exactly like a server that has crashed.
    """
    body = json.dumps(payload).encode("utf-8")
    stream.write(f"Content-Length: {len(body)}\r\n\r\n".encode("ascii"))
    stream.write(body)
    stream.flush()


def response(request_id: Any, result: Any) -> dict[str, Any]:
    """A successful answer to a request."""
    return {"jsonrpc": "2.0", "id": request_id, "result": result}


PARSE_ERROR = -32700
"""The json-rpc code for a body that could not be read as json at all."""

INVALID_REQUEST = -32600
"""The json-rpc code for a body that is json but not a request object."""

METHOD_NOT_FOUND = -32601
"""The json-rpc code for a request naming a method the server does not implement."""

INVALID_PARAMS = -32602
"""The json-rpc code for a request whose parameters are not the shape the method takes.

Its own code rather than a request failure, because the two say different things to whoever
reads the log: this one is the client's message being wrong, and ``REQUEST_FAILED`` is the
server declining a message it understood perfectly well.
"""

REQUEST_FAILED = -32803
"""A request the server understood and could not carry out; the message says why."""


def error(request_id: Any, code: int, message: str) -> dict[str, Any]:
    """A refusal, which a request always gets rather than being left unanswered."""
    return {"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}}


def notification(method: str, params: Any) -> dict[str, Any]:
    """A message the server sends without being asked and expects no answer to."""
    return {"jsonrpc": "2.0", "method": method, "params": params}
