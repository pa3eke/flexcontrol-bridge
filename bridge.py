import queue
import re
import threading
import time
from dataclasses import replace

import serial

from .constants import AUX1_CMD, AUX3_CMD, BAUD_FLEX, RETRY_SECONDS, STEPS
from .models import BridgeStatus
from .ports import PortManager
from .tci import TCIClient, validate_url


class FlexControlBridge:
    """A single worker owns both connections; the GUI only reads snapshots."""
    def __init__(self, port_manager=None, serial_factory=None, tci_factory=None):
        self.port_manager = port_manager or PortManager()
        self.serial_factory = serial_factory or serial.Serial
        self.tci_factory = tci_factory or TCIClient
        self.state_lock = threading.RLock()
        self.state = BridgeStatus()
        self.stop_event = threading.Event()
        self.error_queue = queue.Queue()
        self.actions = queue.Queue()
        self.bridge_thread = None
        self.flex = None
        self.tci = None
        self._next_step_idx = 0
        self._owns_ptt = False
        self._release_pending = False
        self._pending_freqs = []
        self._pending_until = 0.0
        self._pending_ptt = None
        self._ptt_pending_until = 0.0
        self._buffer = ""

    def snapshot(self):
        with self.state_lock:
            return replace(self.state)

    def _update(self, **values):
        with self.state_lock:
            for key, value in values.items():
                setattr(self.state, key, value)

    def _notice(self, message):
        self._update(message=message)
        self.error_queue.put(message)

    def start(self, flex_port, tci_url):
        if self.bridge_thread and self.bridge_thread.is_alive():
            return "De bridge is al gestart."
        try:
            tci_url = validate_url(tci_url)
        except ValueError as exc:
            return str(exc)
        self.stop_event.clear()
        self.actions = queue.Queue()
        self._next_step_idx = 0
        self._update(running=True, ready=False, current_freq=None, current_step_idx=0,
                     ptt_on=False, vfo_lock=False, message="Verbinding maken…")
        self.bridge_thread = threading.Thread(target=self._run, args=(flex_port, tci_url),
                                              daemon=True, name="flexcontrol-tci")
        self.bridge_thread.start()
        return None

    def request(self, action):
        if self.snapshot().running:
            self.actions.put(action)

    def stop(self):
        self.stop_event.set()

    def wait_stopped(self, timeout=5):
        if self.bridge_thread:
            self.bridge_thread.join(timeout)
        return not self.bridge_thread or not self.bridge_thread.is_alive()

    def _send(self, command):
        if self.tci is None:
            return False
        try:
            self.tci.send(command)
            return True
        except Exception as exc:
            self._drop_tci(f"TCI verbroken: {exc}")
            return False

    def _set_freq(self, freq):
        freq = max(0, int(freq))
        if self._send(f"vfo:0,0,{freq};"):
            self._pending_freqs.append(freq)
            self._pending_until = time.monotonic() + 0.8
            self._update(current_freq=freq)

    def _release_ptt(self):
        if self._owns_ptt or self._release_pending:
            self._release_pending = True
            if self._send("trx:0,false;"):
                self._owns_ptt = False
                self._release_pending = False
                self._pending_ptt = False
                self._ptt_pending_until = time.monotonic() + 0.8
                self._update(ptt_on=False)

    def _handle_step_change(self):
        idx = self._next_step_idx
        self._next_step_idx = (idx + 1) % len(STEPS)
        self._update(current_step_idx=idx)
        state = self.snapshot()
        if STEPS[idx] == 1000 and not state.vfo_lock and state.ready:
            self._set_freq(((state.current_freq + 500) // 1000) * 1000)

    def _handle_tuning(self, direction, multiplier):
        state = self.snapshot()
        if not state.ready or state.vfo_lock:
            return
        change = STEPS[state.current_step_idx] * max(1, multiplier)
        self._set_freq(state.current_freq + (change if direction == "U" else -change))

    def _handle_aux1(self):
        state = self.snapshot()
        if not state.ready:
            return
        new_ptt = not state.ptt_on
        if self._send(f"trx:0,{str(new_ptt).lower()};"):
            self._owns_ptt = new_ptt
            self._pending_ptt = new_ptt
            self._ptt_pending_until = time.monotonic() + 0.8
            self._update(ptt_on=new_ptt)

    def _handle_aux3(self):
        self._update(vfo_lock=not self.snapshot().vfo_lock)

    def _parse_and_handle_command(self, cmd):
        if cmd == "S":
            self._handle_step_change()
        elif cmd == AUX1_CMD:
            self._handle_aux1()
        elif cmd == AUX3_CMD:
            self._handle_aux3()
        else:
            match = re.fullmatch(r"([UD])(\d{1,3})?", cmd)
            if match:
                self._handle_tuning(match[1], int(match[2] or 1))

    def _handle_tci(self, message):
        for command in message.split(";"):
            name, _, payload = command.strip().partition(":")
            args = [value.strip() for value in payload.split(",")]
            try:
                if name.lower() == "vfo" and len(args) == 3 and args[:2] == ["0", "0"]:
                    frequency = int(args[2])
                    if frequency < 0:
                        continue
                    # Intermediate echoes must not move the next rotary tick backwards.
                    if self._pending_freqs and time.monotonic() < self._pending_until:
                        if frequency in self._pending_freqs:
                            index = self._pending_freqs.index(frequency)
                            self._pending_freqs = self._pending_freqs[index + 1:]
                            if self._pending_freqs:
                                continue
                        else:
                            continue
                    self._pending_freqs.clear()
                    self._update(current_freq=frequency, ready=True)
                elif name.lower() == "trx" and len(args) >= 2 and args[0] == "0":
                    if args[1].lower() in ("true", "false"):
                        on = args[1].lower() == "true"
                        if self._pending_ptt is not None:
                            if on != self._pending_ptt and time.monotonic() < self._ptt_pending_until:
                                continue
                            self._pending_ptt = None
                        self._update(ptt_on=on)
                        if not on:
                            self._owns_ptt = False
            except ValueError:
                continue

    def _drop_tci(self, message):
        if self._owns_ptt:
            self._release_pending = True
        self._owns_ptt = False
        client, self.tci = self.tci, None
        if client:
            try:
                client.close()
            except Exception:
                pass
        self._pending_freqs.clear()
        self._pending_ptt = None
        self._update(tci_connected=False, ready=False, current_freq=None, ptt_on=False)
        self._notice(message)

    def _drop_flex(self):
        self._release_ptt()
        port, self.flex = self.flex, None
        if port:
            try:
                port.close()
            except Exception:
                pass
        self._buffer = ""
        self._update(flex_connected=False)

    def _run(self, preferred_port, url):
        retry_flex = retry_tci = 0.0
        last_query = 0.0
        try:
            while not self.stop_event.is_set():
                now = time.monotonic()
                if self.tci is None and now >= retry_tci:
                    retry_tci = now + RETRY_SECONDS
                    try:
                        self.tci = self.tci_factory(url)
                        self._update(tci_connected=True)
                        self._notice("TCI verbonden; frequentie ophalen…")
                        self._release_ptt()
                        self._send("vfo:0,0;")
                    except Exception as exc:
                        self._drop_tci(f"Wacht op Thetis: {exc}")
                if self.flex is None and now >= retry_flex:
                    retry_flex = now + RETRY_SECONDS
                    try:
                        devices = self.port_manager.refresh_ports()
                        port = preferred_port if any(p.device == preferred_port for p in devices) else None
                        port = port or self.port_manager.detect_flexcontrol()
                        if not port:
                            raise ConnectionError("Sluit de FlexControl aan of kies de USB-poort")
                        self.flex = self.serial_factory(port, BAUD_FLEX, timeout=0.02, write_timeout=0.2)
                        self.flex.reset_input_buffer()
                        self._update(flex_connected=True)
                        self._notice(f"FlexControl verbonden op {port}")
                    except Exception as exc:
                        self._drop_flex()
                        self._notice(f"Wacht op FlexControl: {exc}")
                if self.tci:
                    try:
                        message = self.tci.receive()
                        if message:
                            self._handle_tci(message)
                        if now - last_query > 1.0:
                            self._send("vfo:0,0;")
                            last_query = now
                    except Exception as exc:
                        self._drop_tci(f"TCI verbroken: {exc}")
                if self.flex:
                    try:
                        data = self.flex.read(min(self.flex.in_waiting, 4096))
                        self._buffer += data.decode("ascii", errors="ignore")
                        while ";" in self._buffer:
                            cmd, self._buffer = self._buffer.split(";", 1)
                            if not self.stop_event.is_set():
                                self._parse_and_handle_command(cmd.strip())
                        if len(self._buffer) > 256:
                            self._buffer = ""
                    except Exception as exc:
                        self._drop_flex()
                        self._notice(f"USB verbroken: {exc}")
                while not self.actions.empty() and not self.stop_event.is_set():
                    action = self.actions.get_nowait()
                    if action == "ptt_off":
                        if self._send("trx:0,false;"):
                            self._owns_ptt = False
                            self._release_pending = False
                            self._pending_ptt = False
                            self._ptt_pending_until = time.monotonic() + 0.8
                            self._update(ptt_on=False)
                    elif action == "lock":
                        self._handle_aux3()
                    elif action == "step":
                        self._handle_step_change()
                self.stop_event.wait(0.005)
        finally:
            self._drop_flex()
            self._drop_tci("Bridge gestopt")
            self._update(running=False)
