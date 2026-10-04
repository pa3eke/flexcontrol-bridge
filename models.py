from dataclasses import dataclass
from typing import Optional


@dataclass
class PortInfo:
    description: str = ""
    manufacturer: str = ""
    product: str = ""
    serial_number: str = ""
    vid: Optional[int] = None
    pid: Optional[int] = None
    hwid: str = ""


@dataclass
class BridgeStatus:
    current_freq: Optional[int] = None
    current_step_idx: int = 0
    ptt_on: bool = False
    vfo_lock: bool = False
    running: bool = False
    flex_connected: bool = False
    tci_connected: bool = False
    ready: bool = False
    message: str = "Gereed om te verbinden"
