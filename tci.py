"""Thetis TCI uses text messages over WebSocket; binary audio is ignored."""
from urllib.parse import urlsplit
import websocket


def validate_url(url: str) -> str:
    parts = urlsplit(url.strip())
    if parts.scheme not in ("ws", "wss") or not parts.hostname:
        raise ValueError("Gebruik een TCI-adres zoals ws://127.0.0.1:40001")
    if parts.username or parts.password or parts.fragment:
        raise ValueError("Het TCI-adres mag geen inloggegevens of fragment bevatten")
    try:
        _ = parts.port
    except ValueError as exc:
        raise ValueError("Ongeldige TCI-poort") from exc
    return url.strip()


class TCIClient:
    def __init__(self, url: str):
        self.socket = websocket.create_connection(validate_url(url), timeout=2,
                                                   http_no_proxy=["*"])
        self.socket.settimeout(0.02)

    def send(self, command: str):
        self.socket.send(command)

    def receive(self):
        try:
            message = self.socket.recv()
        except websocket.WebSocketTimeoutException:
            return None
        if message == "":
            raise ConnectionError("TCI-verbinding gesloten")
        return message if isinstance(message, str) else None

    def close(self):
        self.socket.close(timeout=0.2)
