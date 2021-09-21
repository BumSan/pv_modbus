from wallbox_system_state import WBSystemState
from pv_modbus_wallbox import WBDef
import pv_modbus_wallbox
import datetime
from typing import List
from wallbox_proxy import WallboxProxy
from toolbox import Toolbox
import pytest


WB_SYSTEM_MAX_CURRENT = 16.0
WB_MIN_CURRENT = 6.0
PV_CHARGE_AMP_TOLERANCE = 2.0
MIN_TIME_PV_CHARGE = 60
MIN_WAIT_BEFORE_PV_ON = 60


def test_is_plug_connected_and_charge_ready():
    wbprox = WallboxProxy()
    wallbox = WBSystemState(1)
    wallbox.charge_state = WBDef.CHARGE_NOPLUG1
    val = wbprox.is_plug_connected_and_charge_ready(wallbox)
    assert not val

    wallbox.charge_state = WBDef.CHARGE_REQUEST1
    val = wbprox.is_plug_connected_and_charge_ready(wallbox)
    assert val

    wallbox.charge_state = WBDef.CHARGE_REQUEST2
    val = wbprox.is_plug_connected_and_charge_ready(wallbox)
    assert val


def create_fake_wallbox_connection():
    # RTU
    try:
        config_wb_heidelberg = pv_modbus_wallbox.ModbusRTUConfig('rtu', '/dev/serial0', timeout=3, baudrate=19200,
                                                                 bytesize=8,
                                                                 parity='E',
                                                                 stopbits=1)
        return pv_modbus_wallbox.ModbusRTUHeidelbergWB(wb_config=config_wb_heidelberg
                                                       , wb_read_input=pv_modbus_wallbox.HeidelbergWBReadInputs()
                                                       , wb_read_holding=pv_modbus_wallbox.HeidelbergWBReadHolding()
                                                       , wb_write_holding=pv_modbus_wallbox.HeidelbergWBWriteHolding())
    except:
        pass


def reset_wallboxes(wallboxes: List[WBSystemState]):
    for wb in wallboxes:
        wb.pv_charge_active = False
        wb.grid_charge_active = False
        wb.max_current_active = 0


@pytest.fixture
def setup_wallboxes_off_state(mocker):
    mocker.patch(
        'wallbox_proxy.ModbusRTUHeidelbergWB.set_max_current',
        return_value=True
    )

    wallbox = [WBSystemState(1), WBSystemState(2)]
    # init last charge
    for wb in wallbox:
        wb.last_charge_activation = datetime.datetime.now() - datetime.timedelta(seconds=MIN_TIME_PV_CHARGE + 1)
        wb.last_charge_deactivation = datetime.datetime.now() - datetime.timedelta(seconds=MIN_WAIT_BEFORE_PV_ON + 1)
        wb.charge_state = WBDef.CHARGE_REQUEST1

    return wallbox


@pytest.fixture
def setup_wallboxes_pv_on(mocker):
    mocker.patch(
        'wallbox_proxy.ModbusRTUHeidelbergWB.set_max_current',
        return_value=True
    )

    wbprox = WallboxProxy()
    wallbox = [WBSystemState(1), WBSystemState(2)]
    # init last charge
    for wb in wallbox:
        wb.last_charge_activation = datetime.datetime.now() - datetime.timedelta(seconds=MIN_TIME_PV_CHARGE + 1)
        wb.last_charge_deactivation = datetime.datetime.now() - datetime.timedelta(seconds=MIN_WAIT_BEFORE_PV_ON + 1)
        wb.charge_state = WBDef.CHARGE_REQUEST1
        wb.pv_charge_active = True

    return wallbox


@pytest.mark.activate
@pytest.mark.parametrize(
    "current,wb1_charge,wb1_current,wb2_charge,wb2_current",
    [
        (0, False, 0, False, 0)
        , (WB_MIN_CURRENT, True, WB_MIN_CURRENT, False, 0)
        , (WB_MIN_CURRENT - PV_CHARGE_AMP_TOLERANCE, True, WB_MIN_CURRENT - PV_CHARGE_AMP_TOLERANCE, False, 0)
        , (WB_MIN_CURRENT - PV_CHARGE_AMP_TOLERANCE - 0.1, False, 0, False, 0)
        , (WB_SYSTEM_MAX_CURRENT, True, WB_SYSTEM_MAX_CURRENT, False, 0)
        , (WB_SYSTEM_MAX_CURRENT + 0.1, True, WB_SYSTEM_MAX_CURRENT, False, 0)
        , (WB_SYSTEM_MAX_CURRENT * 2, True, WB_SYSTEM_MAX_CURRENT, True, WB_SYSTEM_MAX_CURRENT)
        , (WB_SYSTEM_MAX_CURRENT * 3, True, WB_SYSTEM_MAX_CURRENT, True, WB_SYSTEM_MAX_CURRENT)
    ])
def test_activate_pv_charge_with_different_currents_from_off_state(setup_wallboxes_off_state, current, wb1_charge,
                                                                   wb1_current, wb2_charge, wb2_current):
    """use different currents (min, max, <min, > max) from Wallbox off state"""
    connection = create_fake_wallbox_connection()
    wallbox = setup_wallboxes_off_state
    wbprox = WallboxProxy()

    # try charging less than min current - tolerance
    available_current = current
    print(' ')
    wbprox.activate_pv_charge(connection, wallbox, available_current)
    assert wallbox[0].pv_charge_active == wb1_charge
    assert wallbox[0].max_current_active == wb1_current
    assert wallbox[1].pv_charge_active == wb2_charge
    assert wallbox[1].max_current_active == wb2_current


@pytest.mark.activate
@pytest.mark.parametrize(
    "current,wb1_charge,wb1_current,wb2_charge,wb2_current",
    [
        (0, False, 0, False, 0)
        , (WB_MIN_CURRENT, True, WB_MIN_CURRENT, False, 0)
        , (WB_MIN_CURRENT - PV_CHARGE_AMP_TOLERANCE, True, WB_MIN_CURRENT - PV_CHARGE_AMP_TOLERANCE, False, 0)
        , (WB_MIN_CURRENT - PV_CHARGE_AMP_TOLERANCE - 0.1, False, 0, False, 0)
        , (WB_SYSTEM_MAX_CURRENT, True, WB_SYSTEM_MAX_CURRENT, False, 0)
        , (WB_SYSTEM_MAX_CURRENT + 0.1, True, WB_SYSTEM_MAX_CURRENT, False, 0)
        , (WB_SYSTEM_MAX_CURRENT * 2, True, WB_SYSTEM_MAX_CURRENT, True, WB_SYSTEM_MAX_CURRENT)
        , (WB_SYSTEM_MAX_CURRENT * 3, True, WB_SYSTEM_MAX_CURRENT, True, WB_SYSTEM_MAX_CURRENT)
    ])
def test_activate_pv_charge_with_different_currents_from_on_state(setup_wallboxes_pv_on, current, wb1_charge,
                                                                  wb1_current, wb2_charge, wb2_current):
    """use different currents (min, max, <min, > max) from Wallbox on state"""
    connection = create_fake_wallbox_connection()
    wallbox = setup_wallboxes_pv_on
    wbprox = WallboxProxy()

    # try charging less than min current - tolerance
    available_current = current
    print(' ')
    wbprox.activate_pv_charge(connection, wallbox, available_current)
    assert wallbox[0].pv_charge_active == wb1_charge
    assert wallbox[0].max_current_active == wb1_current
    assert wallbox[1].pv_charge_active == wb2_charge
    assert wallbox[1].max_current_active == wb2_current


@pytest.mark.activate
@pytest.mark.parametrize(
    "current,wb1_charge,wb1_current,wb2_charge,wb2_current",
    [
        (0, False, 0, False, 0)
        , (WB_MIN_CURRENT, False, 0, False, 0)
        , (WB_MIN_CURRENT - PV_CHARGE_AMP_TOLERANCE, False, 0, False, 0)
        , (WB_MIN_CURRENT - PV_CHARGE_AMP_TOLERANCE - 0.1, False, 0, False, 0)
        , (WB_SYSTEM_MAX_CURRENT, False, 0, False, 0)
        , (WB_SYSTEM_MAX_CURRENT + 0.1, False, 0, False, 0)
        , (WB_SYSTEM_MAX_CURRENT * 2, False, 0, False, 0)
        , (WB_SYSTEM_MAX_CURRENT * 3, False, 0, False, 0)
    ])
def test_activate_pv_charge_with_different_currents_without_plug(setup_wallboxes_pv_on, current, wb1_charge,
                                                                 wb1_current, wb2_charge, wb2_current):
    """use different currents (min, max, <min, > max) without charging plug connected"""
    connection = create_fake_wallbox_connection()
    wallbox = setup_wallboxes_pv_on
    wbprox = WallboxProxy()

    for wb in wallbox:
        wb.charge_state = WBDef.CHARGE_NOPLUG1

    # try charging less than min current - tolerance
    available_current = current
    print(' ')
    wbprox.activate_pv_charge(connection, wallbox, available_current)
    assert wallbox[0].pv_charge_active == wb1_charge
    assert wallbox[0].max_current_active == wb1_current
    assert wallbox[1].pv_charge_active == wb2_charge
    assert wallbox[1].max_current_active == wb2_current


@pytest.mark.activate
def test_activate_pv_charge_check_time_dependencies(setup_wallboxes_off_state):
    connection = create_fake_wallbox_connection()
    wallbox = setup_wallboxes_off_state
    wbprox = WallboxProxy()

    # now check the time dependencies
    print(' ')
    print('Time deps')
    wallbox[0].last_charge_activation = datetime.datetime.now()
    wallbox[0].last_charge_deactivation = datetime.datetime.now()
    wallbox[1].last_charge_activation = datetime.datetime.now()
    wallbox[1].last_charge_deactivation = datetime.datetime.now()

    # from inactive WBs
    print(' ')
    print('from inactive WBs to activate')
    available_current = WB_SYSTEM_MAX_CURRENT
    wbprox.activate_pv_charge(connection, wallbox, available_current)
    assert not wallbox[0].pv_charge_active
    assert wallbox[0].max_current_active == 0
    assert not wallbox[1].pv_charge_active
    assert wallbox[1].max_current_active == 0

    # now some time has passed
    print(' ')
    wallbox[0].last_charge_deactivation = datetime.datetime.now() - datetime.timedelta(
        seconds=MIN_WAIT_BEFORE_PV_ON + 1)
    wallbox[1].last_charge_deactivation = datetime.datetime.now() - datetime.timedelta(
        seconds=MIN_WAIT_BEFORE_PV_ON + 1)

    wbprox.activate_pv_charge(connection, wallbox, available_current)
    assert wallbox[0].pv_charge_active
    assert wallbox[0].max_current_active == WB_SYSTEM_MAX_CURRENT
    assert not wallbox[1].pv_charge_active
    assert wallbox[1].max_current_active == 0

    reset_wallboxes(wallbox)

    # from active WBs to inactivate
    wallbox[0].last_charge_activation = datetime.datetime.now()
    wallbox[1].last_charge_activation = datetime.datetime.now()

    print(' ')
    print('from active WBs to inactivate')
    wallbox[0].pv_charge_active = True
    wallbox[0].max_current_active == 6
    wallbox[1].pv_charge_active = True
    wallbox[1].max_current_active == 6
    available_current = 0

    wbprox.activate_pv_charge(connection, wallbox, available_current)
    assert wallbox[0].pv_charge_active
    assert wallbox[0].max_current_active == 6
    assert wallbox[1].pv_charge_active
    assert wallbox[1].max_current_active == 6

    # now some time has passed
    print(' ')
    wallbox[0].last_charge_activation = datetime.datetime.now() - datetime.timedelta(seconds=MIN_TIME_PV_CHARGE + 1)
    wallbox[1].last_charge_activation = datetime.datetime.now() - datetime.timedelta(seconds=MIN_TIME_PV_CHARGE + 1)

    wbprox.activate_pv_charge(connection, wallbox, available_current)
    assert not wallbox[0].pv_charge_active
    assert wallbox[0].max_current_active == 0
    assert not wallbox[1].pv_charge_active
    assert wallbox[1].max_current_active == 0

    reset_wallboxes(wallbox)

    # deactivate wallboxes right after they were activated
    print(' ')
    wallbox[0].last_charge_deactivation = datetime.datetime.now() - datetime.timedelta(
        seconds=MIN_WAIT_BEFORE_PV_ON + 1)
    wallbox[1].last_charge_deactivation = datetime.datetime.now() - datetime.timedelta(
        seconds=MIN_WAIT_BEFORE_PV_ON + 1)

    available_current = WB_SYSTEM_MAX_CURRENT * 2
    wbprox.activate_pv_charge(connection, wallbox, available_current)

    assert wallbox[0].pv_charge_active
    assert wallbox[0].max_current_active == WB_SYSTEM_MAX_CURRENT
    assert wallbox[1].pv_charge_active
    assert wallbox[1].max_current_active == WB_SYSTEM_MAX_CURRENT

    available_current = 0
    wbprox.activate_pv_charge(connection, wallbox, available_current)

    assert wallbox[0].pv_charge_active
    assert wallbox[0].max_current_active == WB_MIN_CURRENT
    assert wallbox[1].pv_charge_active
    assert wallbox[1].max_current_active == WB_MIN_CURRENT


@pytest.mark.activate
def test_activate_grid_charge(setup_wallboxes_off_state):
    connection = create_fake_wallbox_connection()
    wallbox = setup_wallboxes_off_state
    wbprox = WallboxProxy()

    print('')
    wbprox.activate_grid_charge(connection, wallbox)

    assert wallbox[0].grid_charge_active
    assert wallbox[0].max_current_active == WB_SYSTEM_MAX_CURRENT // 2
    assert wallbox[1].grid_charge_active
    assert wallbox[1].max_current_active == WB_SYSTEM_MAX_CURRENT // 2

    reset_wallboxes(wallbox)

    # try without connectors
    print('')
    print('No plugs')
    wallbox[0].charge_state = WBDef.CHARGE_NOPLUG2
    wallbox[1].charge_state = WBDef.CHARGE_NOPLUG2
    wbprox.activate_grid_charge(connection, wallbox)

    assert not wallbox[0].grid_charge_active
    assert wallbox[0].max_current_active == 0
    assert not wallbox[1].grid_charge_active
    assert wallbox[1].max_current_active == 0

    # try with 1 connectors
    print('')
    print('1 plugs')
    wallbox[0].charge_state = WBDef.CHARGE_NOPLUG2
    wallbox[1].charge_state = WBDef.CHARGE_REQUEST1
    wbprox.activate_grid_charge(connection, wallbox)

    assert not wallbox[0].grid_charge_active
    assert wallbox[0].max_current_active == 0
    assert wallbox[1].grid_charge_active
    assert wallbox[1].max_current_active == WB_SYSTEM_MAX_CURRENT

