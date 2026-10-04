"""Exercise a real localhost WebSocket handshake, masking and text messages."""
import base64
import hashlib
import queue
import socket
import threading
import unittest

from pa3eke_flexcontrol_bridge.tci import TCIClient


def read_exact(connection, count):
    result = b""
    while len(result) < count:
        data = connection.recv(count - len(result))
        if not data:
            raise ConnectionError("Socket closed")
        result += data
    return result


class TCISocketTest(unittest.TestCase):
    def test_actual_websocket_commands_notifications_and_close(self):
        server = socket.socket()
        server.bind(("127.0.0.1", 0))
        server.listen(1)
        server.settimeout(3)
        results = queue.Queue()
        release = threading.Event()

        def serve():
            try:
                with server.accept()[0] as connection:
                    connection.settimeout(3)
                    request = b""
                    while not request.endswith(b"\r\n\r\n"):
                        request += read_exact(connection, 1)
                    headers = dict(line.split(": ", 1) for line in request.decode().split("\r\n")[1:] if ": " in line)
                    key = headers["Sec-WebSocket-Key"]
                    accept = base64.b64encode(hashlib.sha1((key + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11").encode()).digest()).decode()
                    connection.sendall(("HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\n"
                                        f"Connection: Upgrade\r\nSec-WebSocket-Accept: {accept}\r\n\r\n").encode())
                    message = b"vfo:0,0,14200650;trx:0,false;ready;"
                    connection.sendall(bytes([0x81, len(message)]) + message)
                    first, second = read_exact(connection, 2)
                    self.assertEqual(first, 0x81)
                    self.assertTrue(second & 0x80, "Client frames must be masked")
                    length = second & 0x7f
                    mask = read_exact(connection, 4)
                    payload = read_exact(connection, length)
                    results.put(bytes(b ^ mask[i % 4] for i, b in enumerate(payload)).decode())
                    release.wait(3)
                    connection.sendall(b"\x88\x02\x03\xe8")
                    read_exact(connection, 2)
            except Exception as exc:
                results.put(exc)

        thread = threading.Thread(target=serve, daemon=True)
        thread.start()
        client = None
        try:
            client = TCIClient(f"ws://127.0.0.1:{server.getsockname()[1]}")
            client.socket.settimeout(1)
            self.assertEqual(client.receive(), "vfo:0,0,14200650;trx:0,false;ready;")
            client.send("vfo:0,0,14201000;")
            self.assertEqual(results.get(timeout=3), "vfo:0,0,14201000;")
            release.set()
            with self.assertRaises(ConnectionError):
                client.receive()
        finally:
            release.set()
            if client:
                client.close()
            server.close()
            thread.join(3)
