"""
mllp_client.py

A tiny client for sending HL7 v2 messages over MLLP (Minimal Lower Layer
Protocol) — the same wire format real hospital systems use, and the same
one your Mirth channels are listening for.

MLLP framing is simple: wrap the raw HL7 text in three special bytes:

    <VT> ... HL7 message text ... <FS><CR>

    VT (0x0B) = "start of message"
    FS (0x1C) = "end of message"
    CR (0x0D) = trailing carriage return required by the spec

This is exactly what the PowerShell script in Part 2 did manually. Here
we wrap it in a small class so pytest can reuse it across every test.
"""

import socket

MLLP_START = b"\x0b"
MLLP_END = b"\x1c"
MLLP_CR = b"\x0d"


class MLLPConnectionError(Exception):
    """Raised when we can't reach the target Mirth channel at all."""


class MLLPClient:
    def __init__(self, host: str, port: int, timeout: float = 5.0):
        self.host = host
        self.port = port
        self.timeout = timeout

    def send(self, hl7_message: str) -> str:
        """
        Send one HL7 message and return the raw ACK text Mirth sends back.

        Raises MLLPConnectionError if the socket can't connect at all —
        this is what happens if Mirth isn't running or the port isn't
        published, and it's worth catching separately from "Mirth
        rejected my message," which is a totally different problem.
        """
        payload = MLLP_START + hl7_message.encode("utf-8") + MLLP_END + MLLP_CR

        try:
            with socket.create_connection((self.host, self.port), timeout=self.timeout) as sock:
                sock.sendall(payload)
                raw = sock.recv(4096)
        except (ConnectionRefusedError, socket.timeout, OSError) as exc:
            raise MLLPConnectionError(
                f"Could not reach Mirth at {self.host}:{self.port} — "
                f"is the container running and is this port published? ({exc})"
            ) from exc

        # Strip the MLLP wrapper bytes back off before handing the ACK to the caller
        return raw.strip(MLLP_START + MLLP_END + MLLP_CR).decode("utf-8", errors="replace")

    def is_reachable(self) -> bool:
        """Quick check used by fixtures to skip integration tests gracefully
        instead of failing with a confusing connection error."""
        try:
            with socket.create_connection((self.host, self.port), timeout=1.5):
                return True
        except OSError:
            return False


def get_ack_code(ack_text: str) -> str:
    """
    Pull the AA / AE / AR code out of an MSA segment, e.g.:
        MSA|AA|MSG00002|...
    Returns '' if no MSA segment is found (means something is badly wrong
    with the response, worth asserting on directly in a test).
    """
    for segment in ack_text.split("\r"):
        if segment.startswith("MSA|") or segment.startswith("MSA^"):
            fields = segment.split("|")
            if len(fields) > 1:
                return fields[1]
    return ""
