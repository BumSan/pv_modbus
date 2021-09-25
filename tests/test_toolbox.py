from toolbox import Toolbox, TimeTools
from pv_modbus_solarlog import SolarLogData
import datetime
import pytest


@pytest.mark.toolbox
def test_amp_rounded_to_wb_format():
    assert Toolbox.amp_rounded_to_wb_format(8.999999) == 89
    assert Toolbox.amp_rounded_to_wb_format(8.9) == 89
    assert Toolbox.amp_rounded_to_wb_format(9.1) == 91
    assert Toolbox.amp_rounded_to_wb_format(9.00001) == 90
    assert Toolbox.amp_rounded_to_wb_format(9.0) == 90


@pytest.mark.toolbox
def test_seconds_have_passed_since_trigger():
    time_tools = TimeTools()
    time_tools.time_start = datetime.datetime.now() - datetime.timedelta(seconds=10)

    assert 10 == time_tools.seconds_have_passed_since_trigger()

    time_tools.time_start = datetime.datetime.now() + datetime.timedelta(seconds=10)
    assert -10 == time_tools.seconds_have_passed_since_trigger()


@pytest.mark.toolbox
def test_trigger_time():
    time_tools = TimeTools()
    time_tools.time_start = datetime.datetime.now() - datetime.timedelta(seconds=10)  # set old time
    assert 10 == time_tools.seconds_have_passed_since_trigger()

    time_tools.trigger_time()  # set actual time
    assert 0 == time_tools.seconds_have_passed_since_trigger()


@pytest.mark.toolbox
def test_watt_to_amp_rounded():
    assert Toolbox.watt_to_amp_rounded(690) == 1.0
    assert Toolbox.watt_to_amp_rounded(691) == 1.0
    assert Toolbox.watt_to_amp_rounded(689) == 0.9


@pytest.mark.toolbox
def test_watt_to_amp():
    assert Toolbox.watt_to_amp(690) == 1.0
    assert Toolbox.watt_to_amp(691) == 1.0014492753623188
    assert Toolbox.watt_to_amp(689) == 0.9985507246376811


@pytest.fixture
def setup_solar_log_data():

    solar_log_data = SolarLogData()
    return solar_log_data


@pytest.mark.toolbox
@pytest.mark.parametrize(
    "actual_output, actual_consumption, already_used_charging_power_for_car, result",
    [
        (6370, 5160, 4440, 5650)
        , (6330, 5870, 5120, 5580)
        , (6380, 6550, 4420, 4250)
        , (6370, 5160, 5130, 6340)
        , (6370, 6510, 5880, 5740)
        , (6370, 6510, 4430, 4290)
        , (6460, 6610, 5860, 5710)
        , (3940, 5240, 4430, 3130)
        , (2960, 5200, 4440, 2200)
        , (0, 500, 11000, 0)
        , (0, 500, 0, 0)
    ])
def test_calc_available_power(actual_consumption, actual_output, already_used_charging_power_for_car, result):
    solar_log_data = SolarLogData()
    solar_log_data.actual_consumption = actual_consumption
    solar_log_data.actual_output = actual_output

    assert Toolbox.calc_available_power(solar_log_data, already_used_charging_power_for_car) == result

