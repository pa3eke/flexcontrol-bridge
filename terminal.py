"""Optional headless TCI bridge: python -m pa3eke_flexcontrol_bridge.terminal."""
import argparse
import queue
from .bridge import FlexControlBridge
from .constants import DEFAULT_TCI_URL


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--usb", default="", help="USB-poort; standaard automatische detectie")
    parser.add_argument("--tci", default=DEFAULT_TCI_URL)
    args = parser.parse_args()
    bridge = FlexControlBridge()
    error = bridge.start(args.usb, args.tci)
    if error:
        parser.error(error)
    try:
        while not bridge.stop_event.wait(0.2):
            try:
                print(bridge.error_queue.get_nowait(), flush=True)
            except queue.Empty:
                pass
    except KeyboardInterrupt:
        pass
    finally:
        bridge.stop()
        bridge.wait_stopped()


if __name__ == "__main__":
    main()
