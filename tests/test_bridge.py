import queue
import tempfile
import threading
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from pa3eke_flexcontrol_bridge.bridge import FlexControlBridge
from pa3eke_flexcontrol_bridge.constants import STEPS
from pa3eke_flexcontrol_bridge.ports import PortManager
from pa3eke_flexcontrol_bridge import settings
from pa3eke_flexcontrol_bridge.tci import validate_url


class FakeTCI:
    def __init__(self, _url=""):
        self.commands = []
        self.messages = queue.Queue()
        self.closed = False
        self.fail = False

    def send(self, command):
        if self.fail:
            raise ConnectionError("verbinding weg")
        self.commands.append(command)

    def receive(self):
        try:
            return self.messages.get_nowait()
        except queue.Empty:
            return None

    def close(self):
        self.closed = True


class FakeSerial:
    def __init__(self, *args, **kwargs):
        self.data = b""
        self.closed = False
        self.fail = False

    @property
    def in_waiting(self):
        if self.fail:
            raise OSError("USB uitgetrokken")
        return len(self.data)

    def reset_input_buffer(self):
        self.data = b""

    def read(self, count):
        chunk, self.data = self.data[:count], self.data[count:]
        return chunk

    def close(self):
        self.closed = True


def wait_for(predicate, timeout=3):
    deadline = time.monotonic() + timeout
    while not predicate():
        if time.monotonic() > deadline:
            raise AssertionError("Timed out")
        time.sleep(0.01)


class ControlsTest(unittest.TestCase):
    def setUp(self):
        self.bridge = FlexControlBridge()
        self.client = FakeTCI()
        self.bridge.tci = self.client
        self.bridge._handle_tci("PROTOCOL:Thetis,1.8;VFO:0,0,14200650;TRX:0,false;ready;")

    def test_step_sequence_and_nearest_rounding(self):
        self.assertEqual(STEPS, [100, 250, 1000])
        for index in (0, 1, 2, 0):
            self.bridge._parse_and_handle_command("S")
            self.assertEqual(self.bridge.snapshot().current_step_idx, index)
        self.assertEqual(self.client.commands, ["vfo:0,0,14201000;"])

    def test_rounding_down_and_half_up(self):
        for frequency, expected in [(14200499, 14200000), (14200500, 14201000), (14201000, 14201000)]:
            self.bridge._next_step_idx = 2
            self.bridge._update(current_freq=frequency)
            self.bridge._handle_step_change()
            self.assertEqual(self.bridge.snapshot().current_freq, expected)

    def test_tune_and_fast_rotation(self):
        self.bridge._parse_and_handle_command("S")
        self.bridge._parse_and_handle_command("S")
        self.bridge._parse_and_handle_command("U")
        self.bridge._parse_and_handle_command("D03")
        self.assertEqual(self.client.commands, ["vfo:0,0,14200900;", "vfo:0,0,14200150;"])

    def test_lock_blocks_tuning_and_rounding(self):
        self.bridge._parse_and_handle_command("X3S")
        for cmd in ["U", "D", "S", "S", "S"]:
            self.bridge._parse_and_handle_command(cmd)
        self.assertEqual(self.client.commands, [])
        self.bridge._parse_and_handle_command("X3S")
        self.bridge._parse_and_handle_command("U")
        self.assertEqual(self.client.commands, ["vfo:0,0,14201650;"])

    def test_ptt_toggle(self):
        self.bridge._parse_and_handle_command("X1S")
        self.bridge._parse_and_handle_command("X1S")
        self.assertEqual(self.client.commands, ["trx:0,true;", "trx:0,false;"])
        self.assertFalse(self.bridge.snapshot().ptt_on)

    def test_stale_ptt_echo_does_not_rekey(self):
        self.bridge._handle_aux1()
        self.bridge._handle_tci("trx:0,false;")
        self.assertTrue(self.bridge.snapshot().ptt_on)
        self.bridge._handle_aux1()
        self.bridge._handle_tci("trx:0,true;")
        self.assertFalse(self.bridge.snapshot().ptt_on)

    def test_initial_frequency_required(self):
        self.bridge._update(ready=False, current_freq=None)
        for cmd in ["U", "X1S", "S", "S", "S"]:
            self.bridge._parse_and_handle_command(cmd)
        self.assertEqual(self.client.commands, [])

    def test_ignore_other_receivers_binary_and_invalid_messages(self):
        self.bridge._handle_tci("vfo:1,0,7000000;vfo:0,1,7100000;vfo:0,0,nope;vfo:0,0,-1;trx:0,nope;")
        self.assertEqual(self.bridge.snapshot().current_freq, 14200650)
        for cmd in ["X2S", "X1L", "C", "L", "Ubad", "U-3", "F0304"]:
            self.bridge._parse_and_handle_command(cmd)
        self.assertEqual(self.client.commands, [])

    def test_external_frequency_changes(self):
        self.bridge._handle_tci("vfo:0,0,7100000;trx:0,true;")
        self.bridge._handle_tuning("U", 1)
        self.assertEqual(self.client.commands, ["vfo:0,0,7100100;"])
        self.assertTrue(self.bridge.snapshot().ptt_on)

    def test_intermediate_echo_preserves_accumulated_tuning(self):
        self.bridge._handle_tuning("U", 1)
        self.bridge._handle_tuning("U", 1)
        self.bridge._handle_tci("vfo:0,0,14200750;")
        self.bridge._handle_tuning("U", 1)
        self.assertEqual(self.bridge.snapshot().current_freq, 14200950)
        self.bridge._handle_tci("vfo:0,0,14200850;vfo:0,0,14200950;")
        self.assertEqual(self.bridge._pending_freqs, [])

    def test_frequency_correction_after_echo_timeout(self):
        self.bridge._handle_tuning("U", 1)
        self.bridge._pending_until = 0
        self.bridge._handle_tci("vfo:0,0,14200000;")
        self.assertEqual(self.bridge.snapshot().current_freq, 14200000)

    def test_usb_loss_releases_own_ptt(self):
        self.bridge.flex = FakeSerial()
        self.bridge._handle_aux1()
        self.bridge._drop_flex()
        self.assertEqual(self.client.commands[-1], "trx:0,false;")
        self.assertFalse(self.bridge.snapshot().ptt_on)

    def test_does_not_release_external_ptt_on_stop(self):
        self.bridge._handle_tci("trx:0,true;")
        self.bridge._drop_flex()
        self.assertEqual(self.client.commands, [])

    def test_send_failure_clears_readiness_and_remembers_ptt_release(self):
        self.bridge._handle_aux1()
        self.client.fail = True
        self.bridge._handle_tuning("U", 1)
        self.assertFalse(self.bridge.snapshot().ready)
        self.assertTrue(self.bridge._release_pending)
        self.bridge.tci = FakeTCI()
        self.bridge._release_ptt()
        self.assertEqual(self.bridge.tci.commands, ["trx:0,false;"])
        self.assertFalse(self.bridge._release_pending)


class WorkerTest(unittest.TestCase):
    def test_serial_fragments_and_shutdown(self):
        usb = FakeSerial()
        client = FakeTCI()
        manager = SimpleNamespace(refresh_ports=lambda: [SimpleNamespace(device="test")],
                                  detect_flexcontrol=lambda: "test")
        bridge = FlexControlBridge(manager, lambda *a, **kw: usb, lambda url: client)
        self.addCleanup(lambda: (bridge.stop(), bridge.wait_stopped()))
        self.assertIsNone(bridge.start("test", "ws://localhost:40001"))
        wait_for(lambda: bridge.snapshot().flex_connected)
        client.messages.put("vfo:0,0,7100000;trx:0,false;")
        wait_for(lambda: bridge.snapshot().ready)
        usb.data = b"S;S;U0"
        wait_for(lambda: bridge.snapshot().current_step_idx == 1)
        usb.data += b"2;X1S;"
        wait_for(lambda: bridge.snapshot().ptt_on)
        self.assertIn("vfo:0,0,7100500;", client.commands)
        self.assertIsNotNone(bridge.start("test", "ws://localhost:40001"))
        bridge.stop()
        self.assertTrue(bridge.wait_stopped())
        self.assertEqual(client.commands[-1], "trx:0,false;")
        self.assertTrue(usb.closed and client.closed)

    def test_missing_devices_retry_without_blocking_caller(self):
        manager = SimpleNamespace(refresh_ports=lambda: [], detect_flexcontrol=lambda: None)
        bridge = FlexControlBridge(manager, tci_factory=lambda url: FakeTCI())
        self.addCleanup(lambda: (bridge.stop(), bridge.wait_stopped()))
        start = time.monotonic()
        self.assertIsNone(bridge.start("", "ws://localhost:40001"))
        self.assertLess(time.monotonic() - start, 0.5)
        wait_for(lambda: bridge.snapshot().tci_connected)
        self.assertFalse(bridge.snapshot().flex_connected)
        self.assertFalse(bridge.snapshot().ready)


class SettingsPortsTest(unittest.TestCase):
    def test_settings_roundtrip_corrupt_file_and_no_import_side_effect(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config" / "settings.json"
            with patch.object(settings, "get_settings_file", return_value=path):
                self.assertEqual(settings.load_settings(), {})
                settings.save_settings("COM8", "ws://192.168.1.20:40001", False)
                self.assertEqual(settings.load_settings(), {"flex_port": "COM8", "tci_url": "ws://192.168.1.20:40001", "autostart": False})
                path.write_text("invalid")
                self.assertEqual(settings.load_settings(), {})

    def test_only_known_devices_autodetected(self):
        def port(device, vid=None, pid=None, description=""):
            return SimpleNamespace(device=device, vid=vid, pid=pid, description=description,
                                   product="", manufacturer="")
        with patch("serial.tools.list_ports.comports", return_value=[port("CAT"), port("FLEX", 0x2192, 0x0010)]):
            self.assertEqual(PortManager().detect_flexcontrol(), "FLEX")
        with patch("serial.tools.list_ports.comports", return_value=[port("CAT")]):
            self.assertIsNone(PortManager().detect_flexcontrol())

    def test_url_validation(self):
        for url in ["ws://localhost:40001", "wss://radio.example:443", "ws://[::1]:40001"]:
            self.assertEqual(validate_url(url), url)
        for url in ["http://localhost", "ws://", "ws://host:wrong", "ws://user:pass@host", "ws://host#fragment"]:
            with self.assertRaises(ValueError):
                validate_url(url)
