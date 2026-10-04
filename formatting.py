from .constants import STEPS


def format_status_line(status):
    freq = "—" if status.current_freq is None else f"{status.current_freq:,}".replace(",", ".")
    return (f"{freq} Hz | Stap {STEPS[status.current_step_idx]} Hz | "
            f"PTT {'aan' if status.ptt_on else 'uit'} | "
            f"Lock {'aan' if status.vfo_lock else 'uit'}")
