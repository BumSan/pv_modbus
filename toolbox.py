import datetime

class Toolbox:

    @staticmethod
    def watt_to_amp(val_watt: int) -> float:
        return val_watt / (230 * 3)  # 3 Phases, 230V

    @staticmethod
    def watt_to_amp_rounded(val_watt: int) -> float:
        val_amp = val_watt / (230 * 3)  # 3 Phases, 230V
        val_amp *= 10
        val_amp = int(val_amp)
        val_amp /= 10
        return val_amp

    @staticmethod
    def amp_rounded_to_wb_format(val_amp: float) -> int:
        amp = val_amp
        amp *= 10
        amp = int(amp)
        return amp


class TimeTools:
    def __init__(self):
        self.time_start = datetime.datetime.now()

    def seconds_have_passed_since_trigger(self):
        time_diff = datetime.datetime.now() - self.time_start
        return time_diff.total_seconds()

    def trigger_time(self):
        self.time_start = datetime.datetime.now()