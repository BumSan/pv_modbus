import pv_modbus_solarlog
import pv_modbus_wallbox
from pv_modbus_wallbox import WBDef
from pv_modbus_system_state import WBSystemState
import logging

# log level
logging.basicConfig()
log = logging.getLogger()
log.setLevel(logging.DEBUG)

WB1_SLAVEID = 1
WB2_SLAVEID = 2
WB_SYSTEM_MAX_CURRENT = 160  # Ampere*10
WB_MIN_CURRENT = 60  # Ampere*10

# Must have Features
# minimale Ladedauer (zB 5min)
#  min Dauer zwischen Ladevorgängen
# Umschalten PV/Sofort-Laden??


# main
wallbox1 = WBSystemState(WB1_SLAVEID)
wallbox2 = WBSystemState(WB2_SLAVEID)

# SolarLog
config_solar_log = pv_modbus_solarlog.ModbusTCPConfig('192.168.178.103', 502, slave_id=0x01)
solar_log = pv_modbus_solarlog.ModbusTCPSolarLog(config_solar_log, pv_modbus_solarlog.SolarLogReadInputs())
solar_log.get_actual_output_sync_ac()
solar_log.get_actual_consumption_sync_ac()

# RTU
config_wb_heidelberg = pv_modbus_wallbox.ModbusRTUConfig('rtu', '/dev/serial0', timeout=3, baudrate=19200, bytesize=8,
                                                         parity='E',
                                                         stopbits=1)
wb_heidelberg = pv_modbus_wallbox.ModbusRTUHeidelbergWB(wb_config=config_wb_heidelberg
                                                        , wb_read_input=pv_modbus_wallbox.HeidelbergWBReadInputs()
                                                        , wb_read_holding=pv_modbus_wallbox.HeidelbergWBReadHolding()
                                                        , wb_write_holding=pv_modbus_wallbox.HeidelbergWBWriteHolding())
wb_heidelberg.connect_wb_heidelberg()


# basically
# check if any car is attached to WB
# -> deactivate Standby, if active (if nothing attached: activate Standby)
# check PV or immediate 11 kW charge via Button position
# check how many WB are attached to Cars and charging
# if immediate: distribute 11 kW to WB; and divide by number of chargers (mind power 4 kW. 6A)
# if PV, check available Power (> threshold, 3-4 kW?),
# ->  check last charge time (> 5min Abstand?),
# ->  if already charging from PV, keep on for min 5min)

# check if we have to activate standby
def activate_standby(wallbox: WBSystemState):
    if wallbox.charge_state == WBDef.CHARGE_NOPLUG1 or wallbox.charge_state == WBDef.CHARGE_NOPLUG2:
        if wallbox.standby_active == WBDef.DISABLE_STANDBY:
            wb_heidelberg.set_standby_control(wallbox.slave_id, WBDef.ENABLE_STANDBY)


def plug_connected_and_charge_ready(wallbox: WBSystemState) -> bool:
    return wallbox.charge_state == WBDef.CHARGE_REQUEST1 or wallbox.charge_state == WBDef.CHARGE_REQUEST2


# loop from here

# check both WB for charge plug and charge request
try:
    charge_state_WB1 = wb_heidelberg.get_charging_state(wallbox1.slave_id)
    charge_state_WB2 = wb_heidelberg.get_charging_state(wallbox2.slave_id)

    # check for standby activation (.. saves 4 Watt if no Car is plugged in)
    if charge_state_WB1.noError():
        wallbox1.charge_state = charge_state_WB1
        activate_standby(wallbox1)
    if charge_state_WB2.noError():
        wallbox2.charge_state = charge_state_WB2
        activate_standby(wallbox2)

    # check Switch Position: Charge all or only PV
    # ToDo later. Have the switch static now
    pv_charge_only = False

    if not pv_charge_only:
        # check how many Plugs are connected in correct state
        connected = 0
        if plug_connected_and_charge_ready(wallbox1):
            connected += 1
        if plug_connected_and_charge_ready(wallbox2):
            connected += 1

        # assign respective power to the wallboxes, evenly
        if connected > 0:
            if plug_connected_and_charge_ready(wallbox1):
                wb_heidelberg.set_max_current(wallbox1.slave_id, WB_SYSTEM_MAX_CURRENT // connected)
                print('Wallbox 1 current set to ' + str(WB_SYSTEM_MAX_CURRENT // connected))
            if plug_connected_and_charge_ready(wallbox2):
                wb_heidelberg.set_max_current(wallbox2.slave_id, WB_SYSTEM_MAX_CURRENT // connected)
                print('Wallbox 2 current set to ' + str(WB_SYSTEM_MAX_CURRENT // connected))
    else:
        # Charge only via PV
        pv_actual_output = solar_log.get_actual_output_sync_ac()
        actual_consumption = solar_log.get_actual_consumption_sync_ac()

        # the difference between the 2 is our available PV Power for addtl. charging (keep actual charge of cars in mind)
        available_power_watt = pv_actual_output - actual_consumption

        # check how much we currently use for charging





except:
    print('Oh error. Something went wrong. ToDo ;)')
