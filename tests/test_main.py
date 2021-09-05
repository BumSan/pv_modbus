from wallbox_system_state import WBSystemState
from pv_modbus_wallbox import WBDef
import pv_modbus_wallbox
from main import *


def test_is_plug_connected_and_charge_ready():
    wallbox = WBSystemState(1)
    wallbox.charge_state = WBDef.CHARGE_NOPLUG1
    val = is_plug_connected_and_charge_ready(wallbox)
    assert not val

    wallbox.charge_state = WBDef.CHARGE_REQUEST1
    val = is_plug_connected_and_charge_ready(wallbox)
    assert val

    wallbox.charge_state = WBDef.CHARGE_REQUEST2
    val = is_plug_connected_and_charge_ready(wallbox)
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


def test_activate_pv_charge(mocker):
    mocker.patch(
        'pv_modbus.main.pv_modbus_wallbox.ModbusRTUHeidelbergWB.set_max_current',
        return_value=True
    )

    connection = create_fake_wallbox_connection()
    wallbox = [WBSystemState(1), WBSystemState(2)]
    # init last charge
    for wb in wallbox:
        wb.last_charge_activation = datetime.datetime.now() - datetime.timedelta(seconds=MIN_TIME_PV_CHARGE + 1)
        wb.last_charge_deactivation = datetime.datetime.now() - datetime.timedelta(seconds=MIN_WAIT_BEFORE_PV_ON + 1)

    # have charge request active for all WBs
    wallbox[0].charge_state = WBDef.CHARGE_REQUEST1
    wallbox[1].charge_state = WBDef.CHARGE_REQUEST1

    print(' ')
    print('WBs from off state')

    # 1 try charging min current
    available_current = WB_MIN_CURRENT
    activate_pv_charge(connection, wallbox, available_current)
    assert wallbox[0].pv_charge_active
    assert wallbox[0].max_current_active == WB_MIN_CURRENT

    # reset both WBs
    reset_wallboxes(wallbox)

    # 2 try charging min current - tolerance. should work for WB1
    available_current = WB_MIN_CURRENT - PV_CHARGE_AMP_TOLERANCE
    activate_pv_charge(connection, wallbox, available_current)
    assert wallbox[0].pv_charge_active
    assert wallbox[0].max_current_active == available_current

    # reset both WBs
    reset_wallboxes(wallbox)

    # 3 try charging less than min current - tolerance
    available_current = WB_MIN_CURRENT - PV_CHARGE_AMP_TOLERANCE - 0.1
    activate_pv_charge(connection, wallbox, available_current)
    assert not wallbox[0].pv_charge_active
    assert wallbox[0].max_current_active == 0

    reset_wallboxes(wallbox)

    # 4 try charging more than WB_SYSTEM_MAX_CURRENT
    available_current = WB_SYSTEM_MAX_CURRENT + 0.1
    activate_pv_charge(connection, wallbox, available_current)
    assert wallbox[0].pv_charge_active
    assert wallbox[0].max_current_active == 16
    assert not wallbox[1].pv_charge_active
    assert wallbox[1].max_current_active == 0

    reset_wallboxes(wallbox)

    # 5try charging WB_SYSTEM_MAX_CURRENT*2
    available_current = WB_SYSTEM_MAX_CURRENT * 2
    activate_pv_charge(connection, wallbox, available_current)
    assert wallbox[0].pv_charge_active
    assert wallbox[0].max_current_active == 16
    assert wallbox[1].pv_charge_active
    assert wallbox[1].max_current_active == 16

    reset_wallboxes(wallbox)

    # 6 try charging WB_SYSTEM_MAX_CURRENT*3
    available_current = WB_SYSTEM_MAX_CURRENT * 3
    activate_pv_charge(connection, wallbox, available_current)
    assert wallbox[0].pv_charge_active
    assert wallbox[0].max_current_active == 16
    assert wallbox[1].pv_charge_active
    assert wallbox[1].max_current_active == 16

    reset_wallboxes(wallbox)

    # 7 try charging WB_SYSTEM_MAX_CURRENT*3 but without charge requests
    wallbox[0].charge_state = WBDef.CHARGE_NOPLUG1
    wallbox[1].charge_state = WBDef.CHARGE_NOPLUG1

    available_current = WB_SYSTEM_MAX_CURRENT * 3
    activate_pv_charge(connection, wallbox, available_current)
    assert not wallbox[0].pv_charge_active
    assert wallbox[0].max_current_active == 0
    assert not wallbox[1].pv_charge_active
    assert wallbox[1].max_current_active == 0

    reset_wallboxes(wallbox)

    # have charge request active for all WBs
    wallbox[0].charge_state = WBDef.CHARGE_REQUEST1
    wallbox[1].charge_state = WBDef.CHARGE_REQUEST1

    # now try with already active wallbox
    print(' ')
    print('Already active WBs')
    wallbox[0].pv_charge_active = True
    wallbox[0].max_current_active == 4

    # 1 try charging min current - tolerance. should work for WB1
    available_current = WB_MIN_CURRENT - PV_CHARGE_AMP_TOLERANCE
    activate_pv_charge(connection, wallbox, available_current)
    assert wallbox[0].pv_charge_active
    assert wallbox[0].max_current_active == available_current
    assert not wallbox[1].pv_charge_active
    assert wallbox[1].max_current_active == 0

    reset_wallboxes(wallbox)

    # 2 now try with already active wallbox + adtl current
    wallbox[0].pv_charge_active = True
    wallbox[0].max_current_active == 4

    # 2 try charging min current - tolerance. should work for WB1
    available_current = WB_SYSTEM_MAX_CURRENT * 2
    activate_pv_charge(connection, wallbox, available_current)
    assert wallbox[0].pv_charge_active
    assert wallbox[0].max_current_active == WB_SYSTEM_MAX_CURRENT
    assert wallbox[1].pv_charge_active
    assert wallbox[1].max_current_active == WB_SYSTEM_MAX_CURRENT

    reset_wallboxes(wallbox)

    # 2 try charging WB_SYSTEM_MAX_CURRENT*3 but without charge requests
    wallbox[0].pv_charge_active = True
    wallbox[0].max_current_active == WB_SYSTEM_MAX_CURRENT
    wallbox[1].pv_charge_active = True
    wallbox[1].max_current_active == WB_SYSTEM_MAX_CURRENT

    wallbox[0].charge_state = WBDef.CHARGE_NOPLUG1
    wallbox[1].charge_state = WBDef.CHARGE_NOPLUG1
    available_current = WB_SYSTEM_MAX_CURRENT * 2

    activate_pv_charge(connection, wallbox, available_current)
    assert not wallbox[0].pv_charge_active
    assert wallbox[0].max_current_active == 0
    assert not wallbox[1].pv_charge_active
    assert wallbox[1].max_current_active == 0

    reset_wallboxes(wallbox)

    # have charge request active for all WBs
    wallbox[0].charge_state = WBDef.CHARGE_REQUEST1
    wallbox[1].charge_state = WBDef.CHARGE_REQUEST1

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
    activate_pv_charge(connection, wallbox, available_current)
    assert not wallbox[0].pv_charge_active
    assert wallbox[0].max_current_active == 0
    assert not wallbox[1].pv_charge_active
    assert wallbox[1].max_current_active == 0

    # now some time has passed
    print(' ')
    wallbox[0].last_charge_deactivation = datetime.datetime.now() - datetime.timedelta(seconds=MIN_TIME_PV_CHARGE + 1)
    wallbox[1].last_charge_deactivation = datetime.datetime.now() - datetime.timedelta(seconds=MIN_TIME_PV_CHARGE + 1)

    activate_pv_charge(connection, wallbox, available_current)
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

    activate_pv_charge(connection, wallbox, available_current)
    assert wallbox[0].pv_charge_active
    assert wallbox[0].max_current_active == 6
    assert wallbox[1].pv_charge_active
    assert wallbox[1].max_current_active == 6

    # now some time has passed
    print(' ')
    wallbox[0].last_charge_activation = datetime.datetime.now() - datetime.timedelta(seconds=MIN_TIME_PV_CHARGE + 1)
    wallbox[1].last_charge_activation = datetime.datetime.now() - datetime.timedelta(seconds=MIN_TIME_PV_CHARGE + 1)

    activate_pv_charge(connection, wallbox, available_current)
    assert not wallbox[0].pv_charge_active
    assert wallbox[0].max_current_active == 0
    assert not wallbox[1].pv_charge_active
    assert wallbox[1].max_current_active == 0


def test_activate_grid_charge(mocker):
    mocker.patch(
        'pv_modbus.main.pv_modbus_wallbox.ModbusRTUHeidelbergWB.set_max_current',
        return_value=True
    )

    connection = create_fake_wallbox_connection()
    wallbox = [WBSystemState(1), WBSystemState(2)]
    for wb in wallbox:
        wb.last_charge_activation = datetime.datetime.now() - datetime.timedelta(seconds=MIN_TIME_PV_CHARGE + 1)
        wb.last_charge_deactivation = datetime.datetime.now() - datetime.timedelta(seconds=MIN_WAIT_BEFORE_PV_ON + 1)

    # have charge request active for all WBs
    wallbox[0].charge_state = WBDef.CHARGE_REQUEST1
    wallbox[1].charge_state = WBDef.CHARGE_REQUEST1
    print('')
    activate_grid_charge(connection, wallbox)

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
    activate_grid_charge(connection, wallbox)

    assert not wallbox[0].grid_charge_active
    assert wallbox[0].max_current_active == 0
    assert not wallbox[1].grid_charge_active
    assert wallbox[1].max_current_active == 0

    # try with 1 connectors
    print('')
    print('1 plugs')
    wallbox[0].charge_state = WBDef.CHARGE_NOPLUG2
    wallbox[1].charge_state = WBDef.CHARGE_REQUEST1
    activate_grid_charge(connection, wallbox)

    assert not wallbox[0].grid_charge_active
    assert wallbox[0].max_current_active == 0
    assert wallbox[1].grid_charge_active
    assert wallbox[1].max_current_active == WB_SYSTEM_MAX_CURRENT



