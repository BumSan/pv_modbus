from pv_modbus_solarlog import SolarLogData
import datetime
import logging


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

    # calculate how much power we have to set
    # e.g. PV produces 6000 Watt, House consumes 4500 Watt (incl. Car charging!), Car charges with 4000 Watt
    # 6000 - 4500 + 4000 -> 5500 Watt we can use for charging the car
    @staticmethod
    def calc_available_power(solar_log_data: SolarLogData, already_used_charging_power_for_car) -> int:
        house_consumption = solar_log_data.actual_consumption - already_used_charging_power_for_car
        if house_consumption < 0:  # could happen as measurement is from different devices and times
            house_consumption = 0

        # calc how much we could assign to the cars
        available_power = solar_log_data.actual_output - house_consumption

        # sanity check, can´t be more than PV output
        if available_power > solar_log_data.actual_output:
            available_power = solar_log_data.actual_output
        if available_power < 0:
            available_power = 0
        logging.warning('Available power for PV charge: %s W', available_power)

        return available_power


class TimeTools:
    def __init__(self):
        self.time_start = datetime.datetime.now()

    def seconds_have_passed_since_trigger(self):
        time_diff = datetime.datetime.now() - self.time_start
        return time_diff.total_seconds()

    def trigger_time(self):
        self.time_start = datetime.datetime.now()