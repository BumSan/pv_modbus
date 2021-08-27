import pv_modbus_solarlog
import pv_modbus_wallbox
from pv_modbus_wallbox import WBDef
from wallbox_system_state import WBSystemState
import logging
import time
import datetime
import pymodbus.exceptions

# log level
logging.basicConfig()
log = logging.getLogger()
log.setLevel(logging.FATAL)

WB1_SLAVEID = 1
WB2_SLAVEID = 2
WB_SYSTEM_MAX_CURRENT = 16  # Ampere
WB_MIN_CURRENT = 6  # Ampere
PV_CHARGE_AMP_TOLERANCE = 2  # Amp -> if we do not have enough PV power to reach the WB min, use this threshold value
# and take up to x Amp from grid

# time constraints
MIN_TIME_PV_CHARGE = 5 * 60  # secs. We want to charge at least for x secs before switch on->off (PV charge related)
MIN_WAIT_BEFORE_PV_ON = 2 * 60  # secs. We want to wait at least for x secs before switch off->on (PV charge related)


# Must have Features
# minimale Ladedauer (zB 5min)
#  min Dauer zwischen Ladevorgängen
# Umschalten PV/Sofort-Laden??


# check if we have to activate standby
def do_we_need_to_standby(wallbox: WBSystemState):
    if wallbox.charge_state == WBDef.CHARGE_NOPLUG1 or wallbox.charge_state == WBDef.CHARGE_NOPLUG2:
        if wallbox.standby_active == WBDef.DISABLE_STANDBY:
            wb_heidelberg.set_standby_control(wallbox.slave_id, WBDef.ENABLE_STANDBY)


def is_plug_connected_and_charge_ready(wallbox: WBSystemState) -> bool:
    return wallbox.charge_state == WBDef.CHARGE_REQUEST1 or wallbox.charge_state == WBDef.CHARGE_REQUEST2


# wrapper so we can filter and work on min time
def set_current_for_wallbox(wallbox: WBSystemState, current):
    wb_heidelberg.set_max_current(wallbox.slave_id, current)


# wrapper so we can filter and work on min time
def set_pv_current_for_wallbox(wallbox: WBSystemState, current):
    current_allowed = False

    if wallbox.pv_charge_active is False and current > 0:  # === switch it on ===
        # check if allowed (was off for long enough)
        if wallbox.last_charge_deactivation == 0:
            # was never deactivated, so go ahead with charge and set timestamps for activation
            current_allowed = True
            wallbox.last_charge_activation = datetime.datetime.now()
        else:
            # check last time it was switched off, so we can keep minimum time off
            time_diff = datetime.datetime.now() - wallbox.last_charge_deactivation
            if time_diff.total_seconds() > MIN_WAIT_BEFORE_PV_ON:
                current_allowed = True
                wallbox.last_charge_activation = datetime.datetime.now()
            else:
                current_allowed = False  # will be tried again later in another cycle
    elif wallbox.pv_charge_active is False and current == 0:  # === keep it off ===
        current_allowed = False  # is off anyway, don´t change
    elif wallbox.pv_charge_active is True and current == 0:  # === switch it off ===
        # check last time it was switched on, so we can keep minimum time on
        time_diff = datetime.datetime.now() - wallbox.last_charge_activation
        if time_diff.total_seconds() > MIN_TIME_PV_CHARGE:
            current_allowed = True
            wallbox.last_charge_deactivation = datetime.datetime.now()
        else:
            current_allowed = False  # will be tried again later in another cycle
    elif wallbox.pv_charge_active is True and current > 0:  # === keep it on ===
        current_allowed = True

    if current_allowed:
        wb_heidelberg.set_max_current(wallbox.slave_id, current)
        if current > 0:
            wallbox.pv_charge_active = True
        else:
            wallbox.pv_charge_active = False


def watt_to_amp(val_watt: int) -> float:
    val_amp = val_watt / (230*3)  # 3 Phases, 230V
    return val_amp


def watt_to_amp_rounded(val_watt: int) -> float:
    val_amp = val_watt / (230*3)  # 3 Phases, 230V
    val_amp *= 10
    val_amp = int(val_amp)
    val_amp /= 10
    return val_amp


# main
wallbox1 = WBSystemState(WB1_SLAVEID)
wallbox2 = WBSystemState(WB2_SLAVEID)

# SolarLog
config_solar_log = pv_modbus_solarlog.ModbusTCPConfig('192.168.178.103', 502, slave_id=0x01)
solar_log = pv_modbus_solarlog.ModbusTCPSolarLog(config_solar_log, pv_modbus_solarlog.SolarLogReadInputs())

# ToDo: Remove this
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
# loop from here


while True:

    try:
        # if we lose communication to the WB, assume we lose it to both; and split max current of 16A evenly
        wb_heidelberg.set_failsafe_max_current(slave_id=wallbox1.slave_id, val=8)
        wb_heidelberg.set_failsafe_max_current(slave_id=wallbox2.slave_id, val=8)
    except pymodbus.exceptions.ConnectionException:
        print('Connection error. Could not connect to WB. Trying again.')
        time.sleep(5)
        continue

    print(' ')
    print('Next Calculation cycle starts')
    print(datetime.datetime.now())

    # ToDo: Read out all; to update our WB1+2 states

    try:
        # check both WB for charge plug and charge request
        charge_state_WB1 = wb_heidelberg.get_charging_state(wallbox1.slave_id)
        charge_state_WB2 = wb_heidelberg.get_charging_state(wallbox2.slave_id)

        # check for standby activation (.. saves 4 Watt if no Car is plugged in)
        wallbox1.charge_state = charge_state_WB1
        do_we_need_to_standby(wallbox1)

        wallbox2.charge_state = charge_state_WB2
        do_we_need_to_standby(wallbox2)

        # ===================
        # check Switch Position: Charge all or only PV
        # ===================
        # ToDo later. Have the switch static now
        pv_charge_only = False

        # ===================
        # charge max (11 kW overall)
        # ===================
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
                    set_current_for_wallbox(wallbox1, WB_SYSTEM_MAX_CURRENT // connected)
                    print('Wallbox 1 current set to ' + str(WB_SYSTEM_MAX_CURRENT // connected) + ' A')
                if is_plug_connected_and_charge_ready(wallbox2):
                    set_current_for_wallbox(wallbox2, WB_SYSTEM_MAX_CURRENT // connected)
                    print('Wallbox 2 current set to ' + str(WB_SYSTEM_MAX_CURRENT // connected) + ' A')
        else:
            # ===================
            # Charge only via PV
            # ===================
            print('== PV-Charge only active ==')

            # Get the PV data (all in Watt)
            pv_actual_output = solar_log.get_actual_output_sync_ac()
            actual_consumption = solar_log.get_actual_consumption_sync_ac()

            # for testing only
            if WBDef.FAKE_WB_CONNECTION:
                pv_actual_output = 6000

            # check at Wallboxes how much we currently use for charging
            already_used_charging_power_for_car = 0
            if is_plug_connected_and_charge_ready(wallbox1):
                val = wb_heidelberg.get_actual_charge_power(wallbox1.slave_id)
                already_used_charging_power_for_car += val
            if is_plug_connected_and_charge_ready(wallbox2):
                val = wb_heidelberg.get_actual_charge_power(wallbox2.slave_id)
                already_used_charging_power_for_car += val
            print('Currently used power for charging: ' + str(already_used_charging_power_for_car) + ' Watt')

            # calculate how much power we have to set
            # e.g. PV produces 6000 Watt, House consumes 4500 Watt (incl. Car charging!), Car charges with 4000 Watt
            # 6000 - 4500 + 4000 -> 5500 Watt we can use for charging the car

            # calc house consumption
            house_consumption = actual_consumption - already_used_charging_power_for_car
            if house_consumption < 0:  # could happen as measurement is from different devices and times
                house_consumption = 0

            # calc how much we could assign to the cars
            available_power = pv_actual_output - house_consumption

            # sanity check, can´t be more than PV output
            if available_power > pv_actual_output:
                available_power = pv_actual_output
            print('Available power for PV charge: ' + str(available_power) + ' Watt')

            # check for enough power to use PV
            if watt_to_amp(available_power) >= (WB_MIN_CURRENT - PV_CHARGE_AMP_TOLERANCE):
                # Charge galore
                if is_plug_connected_and_charge_ready(wallbox1):  # this makes WB1 our preferred wallbox for PV charge
                    set_pv_current_for_wallbox(wallbox1, watt_to_amp_rounded(available_power))
                    set_pv_current_for_wallbox(wallbox2, 0)
                    print('Wallbox1 PV current set to: ' + str(watt_to_amp_rounded(available_power)) + ' A')
                elif is_plug_connected_and_charge_ready(wallbox2):
                    set_pv_current_for_wallbox(wallbox1, 0)
                    set_pv_current_for_wallbox(wallbox2, watt_to_amp_rounded(available_power))
                    print('Wallbox2 PV current set to: ' + str(watt_to_amp_rounded(available_power)) + ' A')
            else:
                # stop PV charging
                set_pv_current_for_wallbox(wallbox1, 0)
                set_pv_current_for_wallbox(wallbox2, 0)
                print('===  PV Charge off. Not enough power: ' + str(watt_to_amp_rounded(available_power)) + ' A  ===')

        # chill for some secs
        print('Calculation cycle ends')
        print('')
    except:
        print('Unknown error occured with communication to WB. Trying again after some seconds.')
    time.sleep(5)
# end loop
