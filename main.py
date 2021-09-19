from typing import List
from pv_modbus_solarlog import ModbusTCPSolarLog, ModbusTCPConfig, ModbusTcpClient, SolarLogReadInputs, SolarLogData
from pv_modbus_wallbox import ModbusRegisters, ModbusRTUConfig, ModbusRTUHeidelbergWB, ModbusSerialClient
from pv_modbus_wallbox import HeidelbergWBReadInputs, HeidelbergWBReadHolding, HeidelbergWBWriteHolding
from pv_modbus_wallbox import WBDef
from wallbox_system_state import WBSystemState
from pv_database import PVDatabase
import logging
import time
import datetime
import configparser

import pymodbus.exceptions

# log level
logging.basicConfig(level=logging.INFO)

config = configparser.ConfigParser()
config.read('pv_modbus_config.ini')

HAVE_SWITCH = config['SWITCH'].getboolean('HAVE_SWITCH')
if HAVE_SWITCH:
    from switch_position import PV_Switch

SOLARLOG_IP = config['SOLARLOG']['SOLARLOG_IP']
SOLARLOG_PORT = int(config['SOLARLOG']['SOLARLOG_PORT'])
SOLARLOG_SLAVEID = int(config['SOLARLOG']['SOLARLOG_SLAVEID'])

WB1_SLAVEID = int(config['WALLBOX']['WB1_SLAVEID'])  # Slave ID is also Priority (e.g. for new(!) PV Charge requests)
WB2_SLAVEID = int(config['WALLBOX']['WB2_SLAVEID'])  # smaller numbers mean higher priority
WB_RTU_DEVICE = config['WALLBOX']['WB_RTU_DEVICE']

WB_SYSTEM_MAX_CURRENT = float(config['WALLBOX']['WB_SYSTEM_MAX_CURRENT'])  # Ampere
WB_MIN_CURRENT = float(config['WALLBOX']['WB_MIN_CURRENT'])  # Ampere
# Amp -> if we do not have enough PV power to reach the WB min, use this threshold value
PV_CHARGE_AMP_TOLERANCE = float(config['WALLBOX']['PV_CHARGE_AMP_TOLERANCE'])
# and take up to x Amp from grid

# time constraints
# secs. We want to charge at least for x secs before switch on->off (PV charge related)
MIN_TIME_PV_CHARGE = int(config['TIME']['MIN_TIME_PV_CHARGE'])
# this is "Min time on"
# secs. We want to wait at least for x secs before switch off->on (PV charge related)
MIN_WAIT_BEFORE_PV_ON = int(config['TIME']['MIN_TIME_PV_CHARGE'])
# this is "Min time off"

SOLARLOG_WRITE_EVERY = int(config['LOGGING']['SOLARLOG_WRITE_EVERY'])  # *5s

GPIO_SWITCH = int(config['SWITCH']['GPIO_SWITCH'])


# check if we have to activate standby
def set_standby_if_required(wallbox_connection, wallbox: WBSystemState):
    if is_plug_connected_and_charge_ready(wallbox):
        if wallbox.standby_active == WBDef.DISABLE_STANDBY:
            if wallbox_connection.set_standby_control(wallbox.slave_id, WBDef.ENABLE_STANDBY):
                wallbox.standby_active = WBDef.ENABLE_STANDBY


# deactivate standby
def deactivate_standby(wallbox_connection, wallbox: WBSystemState):
    if wallbox_connection.set_standby_control(wallbox.slave_id, WBDef.DISABLE_STANDBY):
        wallbox.standby_active = WBDef.DISABLE_STANDBY


def is_plug_connected_and_charge_ready(wallbox: WBSystemState) -> bool:
    return wallbox.charge_state == WBDef.CHARGE_PLUG_NO_REQUEST1 \
            or wallbox.charge_state == WBDef.CHARGE_PLUG_NO_REQUEST2 \
            or wallbox.charge_state == WBDef.CHARGE_REQUEST1 \
            or wallbox.charge_state == WBDef.CHARGE_REQUEST2


# wrapper so we can filter and work on min time
def set_current_for_wallbox(wallbox_connection, wallbox: WBSystemState, current):
    if wallbox_connection.set_max_current(wallbox.slave_id, current):
        wallbox.max_current_active = current


def activate_grid_charge(wallbox_connection, wallbox: List[WBSystemState]):
    # check how many Plugs are connected in correct state
    connected = 0
    for wb in wallbox:
        if is_plug_connected_and_charge_ready(wb):
            connected += 1
    # assign respective power to the wallboxes, evenly
    if connected > 0:
        for wb in wallbox:
            if is_plug_connected_and_charge_ready(wb):  # connected
                set_current_for_wallbox(wallbox_connection, wb, WB_SYSTEM_MAX_CURRENT // connected)
                logging.warning('Wallbox ID %s, current set to %s A', wb.slave_id, WB_SYSTEM_MAX_CURRENT // connected)
                if not wb.grid_charge_active:
                    wb.grid_charge_active = True
                    wb.last_charge_activation = datetime.datetime.now()
            else:  # disconnected
                set_current_for_wallbox(wallbox_connection, wb, 0)
                if wb.grid_charge_active:
                    wb.grid_charge_active = False
                    wb.last_charge_deactivation = datetime.datetime.now()
    else:
        logging.info('No Connector connected')


def deactivate_pv_charge_for_wallbox(wallbox: WBSystemState):
    wallbox.pv_charge_active = False
    wallbox.max_current_active = 0
    wallbox.last_charge_deactivation = datetime.datetime.now()


def activate_pv_charge_for_wallbox(wallbox: WBSystemState, current):
    wallbox.pv_charge_active = True
    wallbox.max_current_active = current
    wallbox.last_charge_activation = datetime.datetime.now()


def activate_pv_charge(wallbox_connection, wallbox: List[WBSystemState], available_current):
    used_current = 0.0

    # are any of the Wallboxes already charging with PV? then we update these first
    logging.info('Working on already active WBs first')
    for wb in wallbox:
        if wb.pv_charge_active:
            # WBs without charge request get nothing:
            if is_plug_connected_and_charge_ready(wb):
                # limit the current to max value per WB
                if available_current > WB_SYSTEM_MAX_CURRENT:
                    used_current = WB_SYSTEM_MAX_CURRENT
                else:
                    used_current = available_current

                # check if we have enough power for this WB. If not we try to switch it off
                if used_current >= (WB_MIN_CURRENT - PV_CHARGE_AMP_TOLERANCE):
                    # enough power. we already charge so no check required
                    set_current_for_wallbox(wallbox_connection, wb, used_current)
                    logging.warning('Setting Wallbox ID %s to %s A', wb.slave_id, used_current)
                else:  # we do not have enough power. Check if we can deactivate this WB
                    if is_pv_charge_deactivation_allowed(wb):
                        used_current = 0
                        set_current_for_wallbox(wallbox_connection, wb, used_current)
                        deactivate_pv_charge_for_wallbox(wb)
                        logging.warning('Charge deactivation for Wallbox ID %s', wb.slave_id)
                    else:  # not allowed, so reduce it to min value for now and try again later
                        used_current = WB_MIN_CURRENT
                        set_current_for_wallbox(wallbox_connection, wb, used_current)
                        logging.error('Charge deactivation for Wallbox ID %s not allowed due to time constraints',
                                      wb.slave_id)
            else:  # no charge request (anymore)
                used_current = 0
                set_current_for_wallbox(wallbox_connection, wb, used_current)
                deactivate_pv_charge_for_wallbox(wb)
                logging.info('No charge request anymore for Wallbox ID %s. Deactivating', wb.slave_id)

            # keep track of the the current contingent
            available_current -= used_current
            logging.info('Still Available current: %s A', available_current)

    # 2nd step: if we have enough power left, we can check to activate WBs that do not charge yet
    logging.info('Check for further Wallboxes to be activated')
    for wb in wallbox:
        # WBs without charge request get nothing:
        if is_plug_connected_and_charge_ready(wb):
            if available_current >= (WB_MIN_CURRENT - PV_CHARGE_AMP_TOLERANCE):
                if not wb.pv_charge_active:
                    # limit the current to max value per WB
                    if available_current > WB_SYSTEM_MAX_CURRENT:
                        used_current = WB_SYSTEM_MAX_CURRENT
                    else:
                        used_current = available_current

                    # check if we can activate this WB. If not we just try the next one
                    if is_pv_charge_activation_allowed(wb):
                        set_current_for_wallbox(wallbox_connection, wb, used_current)
                        logging.info('Setting Wallbox ID %s to %s A', wb.slave_id, used_current)
                        activate_pv_charge_for_wallbox(wb, used_current)
                        # keep track of the the current contingent
                        available_current -= used_current
                        logging.debug('Still Available current: %s A', available_current)
                    else:
                        logging.error('Charge activation for Wallbox ID %s not allowed due to time constraints',
                                      wb.slave_id)
            else:  # not enough power left
                logging.info('Not enough power for charging any further Wallboxes')
                break
        else:
            logging.info('This WB has no charge request')


# check if WB was inactive for long enough (to avoid fast switch on/off)
def is_pv_charge_activation_allowed(wallbox) -> bool:
    time_diff = datetime.datetime.now() - wallbox.last_charge_deactivation
    return time_diff.total_seconds() > MIN_WAIT_BEFORE_PV_ON


# check if WB was active for long enough (to avoid fast switch on/off)
def is_pv_charge_deactivation_allowed(wallbox) -> bool:
    time_diff = datetime.datetime.now() - wallbox.last_charge_activation
    return time_diff.total_seconds() > MIN_TIME_PV_CHARGE


def deactivate_grid_charge(wallbox_connection, wallbox: List[WBSystemState]):
    for wb in wallbox:
        if wb.grid_charge_active:
            wallbox_connection.set_max_current(wb.slave_id, 0)
            wb.grid_charge_active = False
            wb.last_charge_deactivation = datetime.datetime.now()


def deactivate_pv_charge(wallbox_connection, wallbox: List[WBSystemState]):
    for wb in wallbox:
        if wb.pv_charge_active:
            wallbox_connection.set_max_current(wb.slave_id, 0)
            wb.pv_charge_active = False
            wb.last_charge_deactivation = datetime.datetime.now()


def watt_to_amp(val_watt: int) -> float:
    return val_watt / (230 * 3)  # 3 Phases, 230V


def watt_to_amp_rounded(val_watt: int) -> float:
    val_amp = val_watt / (230 * 3)  # 3 Phases, 230V
    val_amp *= 10
    val_amp = int(val_amp)
    val_amp /= 10
    return val_amp


def main():
    wallbox = [WBSystemState(WB1_SLAVEID), WBSystemState(WB2_SLAVEID)]
    wallbox.sort(key=lambda x: x.slave_id)  # make the Slave ID also the priority of the WB

    # SolarLog
    config_solar_log = ModbusTCPConfig(SOLARLOG_IP, SOLARLOG_PORT, slave_id=SOLARLOG_SLAVEID)
    solarlog_connection = ModbusTCPSolarLog(config_solar_log, SolarLogReadInputs())

    # RTU
    config_wb_heidelberg = ModbusRTUConfig(method='rtu', port=WB_RTU_DEVICE, timeout=3, baudrate=19200, bytesize=8,
                                           parity='E',
                                           stopbits=1)
    wallbox_connection = ModbusRTUHeidelbergWB(wb_config=config_wb_heidelberg
                                               , wb_read_input=HeidelbergWBReadInputs()
                                               , wb_read_holding=HeidelbergWBReadHolding()
                                               , wb_write_holding=HeidelbergWBWriteHolding())

    # set up switch
    if HAVE_SWITCH:
        pv_switch = PV_Switch(GPIO_SWITCH)

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

    # init last charge
    for wb in wallbox:
        wb.last_charge_activation = datetime.datetime.now()
        wb.last_charge_deactivation = datetime.datetime.now()

    solar_log_data = SolarLogData()
    solar_log_data_write_enable = 0
    database = PVDatabase()

    # cowboy lucky loop
    while True:

        try:
            # if we lose communication to the WB, assume we lose it to all; and split max current of 16A evenly
            if wallbox_connection.connect_wb_heidelberg():
                for wb in wallbox:
                    wallbox_connection.set_failsafe_max_current(wb.slave_id, int(WB_SYSTEM_MAX_CURRENT / len(wallbox)))
            else:
                logging.fatal('connect_wb_heidelberg failed. Trying again.')
                time.sleep(5)
                continue
        except Exception as e:
            logging.fatal(str(e))
            logging.fatal('Connection error. Could not connect to WB. Trying again.')
            time.sleep(5)
            continue

        logging.info(' ')
        logging.info('Next Calculation cycle starts')
        logging.debug('%s', datetime.datetime.now())

        try:
            # check all WB for charge plug and charge request
            # check for standby activation (.. saves 4 Watt if no Car is plugged in)
            for wb in wallbox:
                wb.charge_state = wallbox_connection.get_charging_state(wb.slave_id)
                #set_standby_if_required(wallbox_connection, wb)
                deactivate_standby(wallbox_connection, wb)

            # get data for logger
            # Get the PV data (all in Watt)
            solar_log_data.actual_output = solarlog_connection.get_actual_output_sync_ac()
            logging.warning('Actual AC Output (PV): %s W', solar_log_data.actual_output)
            solar_log_data.actual_consumption = solarlog_connection.get_actual_consumption_sync_ac()
            logging.warning('Actual AC consumption: %s W', solar_log_data.actual_consumption)

            # check at Wallboxes how much we currently use for charging
            already_used_charging_power_for_car = 0
            for wb in wallbox:
                if is_plug_connected_and_charge_ready(wb):
                    val = wallbox_connection.get_actual_charge_power(wb.slave_id)
                    wb.actual_current_active = watt_to_amp(val)
                    already_used_charging_power_for_car += val
            logging.warning('Currently used power for charging: %s W', already_used_charging_power_for_car)

            # ===================
            # check Switch Position: Charge all or only PV
            # ===================
            if HAVE_SWITCH:
                pv_charge_only = pv_switch.is_switch_set_to_pv_only()
            else:
                pv_charge_only = True


            # For later: Would be cool to have it defined per Wallbox. e.g. one car can always charge fully,
            # the other one only when sun shines

            # ===================
            # charge max (11 kW overall)
            # ===================
            if not pv_charge_only:
                # ===================
                # Charge only from grid (implicitly includes PV when available)
                # ===================
                logging.warning('== Grid-Charge only active ==')
                activate_grid_charge(wallbox_connection, wallbox)
            else:
                # ===================
                # Charge only via PV
                # ===================
                logging.warning('== PV-Charge only active ==')

                # make sure that all active WBs get deactivated first when switching to PV
                # this could be more intelligent, just brute force make sure that we have a clean state to start from
                deactivate_grid_charge(wallbox_connection, wallbox)

                # for testing only
                #if WBDef.FAKE_WB_CONNECTION:
                #    solar_log_data.actual_output = 6000

                # calculate how much power we have to set
                # e.g. PV produces 6000 Watt, House consumes 4500 Watt (incl. Car charging!), Car charges with 4000 Watt
                # 6000 - 4500 + 4000 -> 5500 Watt we can use for charging the car

                # calc house consumption
                house_consumption = solar_log_data.actual_consumption - already_used_charging_power_for_car
                if house_consumption < 0:  # could happen as measurement is from different devices and times
                    house_consumption = 0

                # calc how much we could assign to the cars
                available_power = solar_log_data.actual_output - house_consumption

                # sanity check, can´t be more than PV output
                if available_power > solar_log_data.actual_output:
                    available_power = solar_log_data.actual_output
                logging.warning('Available power for PV charge: %s W', available_power)

                # check for enough power to use PV
                if watt_to_amp_rounded(available_power) >= (WB_MIN_CURRENT - PV_CHARGE_AMP_TOLERANCE):
                    # Charge galore
                    activate_pv_charge(wallbox_connection, wallbox, watt_to_amp_rounded(available_power))

            # chill for some secs
            logging.debug('Calculation cycle ends')
            logging.debug('')
        except Exception as e:
            logging.fatal(str(e))
            logging.fatal('Unknown error occured with communication to WB. Trying again after some seconds.')

        # write PV into DB
        if not solar_log_data_write_enable % SOLARLOG_WRITE_EVERY:
            database.write_solarlog_data_only_if_changed(solar_log_data)
            solar_log_data_write_enable = 0

        solar_log_data_write_enable += 1

        # write wallbox into DB
        database.write_wallbox_data_only_if_changed(wallbox)

        time.sleep(5)
    # end loop


if __name__ == "__main__":
    main()
