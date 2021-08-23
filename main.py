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
WB_SYSTEM_MAX_CURRENT = 16  # Ampere
WB_MIN_CURRENT = 6  # Ampere
PV_CHARGE_AMP_TOLERANCE = 2  # Amp -> if we do not have enough PV power to reach the WB min, use this threshold value
# and take up to x Amp from grid

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
def do_we_need_to_standby(wallbox: WBSystemState):
    if wallbox.charge_state == WBDef.CHARGE_NOPLUG1 or wallbox.charge_state == WBDef.CHARGE_NOPLUG2:
        if wallbox.standby_active == WBDef.DISABLE_STANDBY:
            wb_heidelberg.set_standby_control(wallbox.slave_id, WBDef.ENABLE_STANDBY)


def is_plug_connected_and_charge_ready(wallbox: WBSystemState) -> bool:
    return wallbox.charge_state == WBDef.CHARGE_REQUEST1 or wallbox.charge_state == WBDef.CHARGE_REQUEST2


def check_for_error_and_assign (val_to_check, assign_to):
    if val_to_check.noError():
        assign_to = val_to_check


def set_power_for_wallbox(wallbox:WBSystemState):
    pass


def watt_to_amp (val_watt: int) -> float:
    val_amp = val_watt / (230*3)  # 3 Phases, 230V
    return val_amp


# loop from here


try:
    # ToDo: Read out all; to update our WB1+2 states

    # check both WB for charge plug and charge request
    charge_state_WB1 = wb_heidelberg.get_charging_state(wallbox1.slave_id)
    charge_state_WB2 = wb_heidelberg.get_charging_state(wallbox2.slave_id)

    # check for standby activation (.. saves 4 Watt if no Car is plugged in)
    if charge_state_WB1.noError():
        wallbox1.charge_state = charge_state_WB1
        do_we_need_to_standby(wallbox1)
    if charge_state_WB2.noError():
        wallbox2.charge_state = charge_state_WB2
        do_we_need_to_standby(wallbox2)

    # check Switch Position: Charge all or only PV
    # ToDo later. Have the switch static now
    pv_charge_only = False

    # charge max (11 kW overall)
    if not pv_charge_only:
        # check how many Plugs are connected in correct state
        connected = 0
        if is_plug_connected_and_charge_ready(wallbox1):
            connected += 1
        if is_plug_connected_and_charge_ready(wallbox2):
            connected += 1

        # assign respective power to the wallboxes, evenly
        if connected > 0:
            if is_plug_connected_and_charge_ready(wallbox1):
                wb_heidelberg.set_max_current(wallbox1.slave_id, WB_SYSTEM_MAX_CURRENT // connected)
                print('Wallbox 1 current set to ' + str(WB_SYSTEM_MAX_CURRENT // connected))
            if is_plug_connected_and_charge_ready(wallbox2):
                wb_heidelberg.set_max_current(wallbox2.slave_id, WB_SYSTEM_MAX_CURRENT // connected)
                print('Wallbox 2 current set to ' + str(WB_SYSTEM_MAX_CURRENT // connected))
    else:
        # Charge only via PV

        # Get the PV data (all in Watt)
        pv_actual_output = solar_log.get_actual_output_sync_ac()
        actual_consumption = solar_log.get_actual_consumption_sync_ac()

        # check at WB how much we currently use for charging
        already_used_charging_power_for_car=0
        if is_plug_connected_and_charge_ready(wallbox1):
            val = wb_heidelberg.get_actual_charge_power(wallbox1.slave_id)
            if val.noError():
                already_used_charging_power_for_car += val
        if is_plug_connected_and_charge_ready(wallbox2):
            val = wb_heidelberg.get_actual_charge_power(wallbox2.slave_id)
            if val.noError():
                already_used_charging_power_for_car += val
        print ('Currently used power for charging: ' + str(already_used_charging_power_for_car) + ' Watt')

        # calculate how much power we have to set
        # e.g. PV produces 6000 Watt, House consumes 4500 Watt (incl. Car charging!), Car charges with 4000 Watt
        # 6000 - 4500 + 4000 -> 5500 Watt we can use for charging the car
        available_power= pv_actual_output - actual_consumption + already_used_charging_power_for_car

        # check for enough power to use PV
        if watt_to_amp(available_power) >= (WB_MIN_CURRENT - PV_CHARGE_AMP_TOLERANCE):
            if is_plug_connected_and_charge_ready(wallbox1):
                # ToDo: Charge with what we have
                pass
            elif is_plug_connected_and_charge_ready(wallbox2):
                # ToDo: Charge with what we have
                pass
        else:
            # ToDO: Deactivate Charging for all WB (set current to 0)
            pass




except:
    print('Oh error. Something went wrong. ToDo ;)')