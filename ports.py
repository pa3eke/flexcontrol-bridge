"""USB enumeration only: never open unrelated serial devices to probe them."""
import serial.tools.list_ports
from .constants import FLEXCONTROL_PID, FLEXCONTROL_VID


class PortManager:
    def refresh_ports(self):
        return list(serial.tools.list_ports.comports())

    def classify_port(self, port) -> str:
        text = f"{port.description} {port.product} {port.manufacturer}".lower()
        if (port.vid, port.pid) == (FLEXCONTROL_VID, FLEXCONTROL_PID) or "flexcontrol" in text:
            return "flexcontrol"
        return ""

    def detect_flexcontrol(self, **_kwargs):
        return next((p.device for p in self.refresh_ports()
                     if self.classify_port(p) == "flexcontrol"), None)
