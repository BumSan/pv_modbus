from toolbox import Toolbox, TimeTools
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
