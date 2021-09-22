from pv_modbus_solarlog import ModbusTCPSolarLog, ModbusTCPConfig, SolarLogReadInputs, SolarLogData
from pv_modbus_wallbox import ModbusRTUConfig, ModbusRTUHeidelbergWB
from pv_modbus_wallbox import HeidelbergWBReadInputs, HeidelbergWBReadHolding, HeidelbergWBWriteHolding
from wallbox_system_state import WBSystemState
from pv_database import PVDatabase
from wallbox_proxy import WallboxProxy
from toolbox import Toolbox, TimeTools
from config_file import ConfigFile
import logging
import time
import datetime
import configparser

# log level
logging.basicConfig(level=logging.INFO)


def main():
    config = configparser.ConfigParser()
    config.read('pv_modbus_config.ini')

    cfg = ConfigFile(config)

    if cfg.HAVE_SWITCH:
        from switch_position import PV_Switch

    wallbox = [WBSystemState(cfg.WB1_SLAVEID), WBSystemState(cfg.WB2_SLAVEID)]
    wallbox.sort(key=lambda x: x.slave_id)  # make the Slave ID also the priority of the WB

    wb_prox = WallboxProxy(cfg)
    time_tools = TimeTools()

    # SolarLog
    config_solar_log = ModbusTCPConfig(cfg.SOLARLOG_IP, cfg.SOLARLOG_PORT, slave_id=cfg.SOLARLOG_SLAVEID)
    solarlog_connection = ModbusTCPSolarLog(config_solar_log, SolarLogReadInputs())

    # RTU
    config_wb_heidelberg = ModbusRTUConfig(method='rtu', port=cfg.WB_RTU_DEVICE, timeout=3, baudrate=19200, bytesize=8,
                                           parity='E',
                                           stopbits=1,
                                           strict=False)
    wallbox_connection = ModbusRTUHeidelbergWB(wb_config=config_wb_heidelberg
                                               , wb_read_input=HeidelbergWBReadInputs()
                                               , wb_read_holding=HeidelbergWBReadHolding()
                                               , wb_write_holding=HeidelbergWBWriteHolding())

    # set up switch
    if cfg.HAVE_SWITCH:
        pv_switch = PV_Switch(cfg.GPIO_SWITCH)

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
    db_write_enable = 0
    database = PVDatabase(cfg)

    # make sure that failsafe Current is always set
    while True:
        try:
            # if we lose communication to the WB, assume we lose it to all; and split max current of 16A evenly
            if wallbox_connection.connect_wb_heidelberg():
                for wb in wallbox:
                    wallbox_connection.set_failsafe_max_current(wb.slave_id, (int(cfg.WB_SYSTEM_MAX_CURRENT / len(wallbox))*10))
                break
            else:
                logging.fatal('connect_wb_heidelberg failed. Trying again.')
                time.sleep(5)
        except Exception as e:
            logging.fatal(str(e))
            logging.fatal('Connection error. Could not connect to WB. Trying again.')
            time.sleep(5)

    # cowboy lucky (main) loop/luke
    while True:
        logging.info(' ')
        logging.info('Next Calculation cycle starts')
        logging.debug('%s', datetime.datetime.now())

        try:
            # check all WB for charge plug and charge request
            # check for standby activation (.. saves 4 Watt if no Car is plugged in)
            for wb in wallbox:
                result = wallbox_connection.get_charging_state(wb.slave_id)
                if result is not False:
                    wb.charge_state = result
                #set_standby_if_required(wallbox_connection, wb)
                wb_prox.deactivate_standby(wallbox_connection, wb)

            # get data for logger
            # Get the PV data (all in Watt)
            solar_log_data.actual_output = solarlog_connection.get_actual_output_sync_ac()
            logging.warning('Actual AC Output (PV): %s W', solar_log_data.actual_output)
            solar_log_data.actual_consumption = solarlog_connection.get_actual_consumption_sync_ac()
            logging.warning('Actual AC consumption: %s W', solar_log_data.actual_consumption)

            # check at Wallboxes how much we currently use for charging
            already_used_charging_power_for_car = 0
            for wb in wallbox:
                if wb_prox.is_plug_connected_and_charge_ready(wb):
                    val = wallbox_connection.get_actual_charge_power(wb.slave_id)
                    wb.actual_current_active = Toolbox.watt_to_amp(val)
                    already_used_charging_power_for_car += val
            logging.warning('Currently used power for charging: %s W', already_used_charging_power_for_car)

            # ===================
            # check Switch Position: Charge all or only PV
            # ===================
            if cfg.HAVE_SWITCH:
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
                wb_prox.activate_grid_charge(wallbox_connection, wallbox)
            else:
                # ===================
                # Charge only via PV
                # ===================
                logging.warning('== PV-Charge only active ==')

                # make sure that all active WBs get deactivated first when switching to PV
                # this could be more intelligent, just brute force make sure that we have a clean state to start from
                wb_prox.deactivate_grid_charge(wallbox_connection, wallbox)

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
                if Toolbox.watt_to_amp_rounded(available_power) >= (cfg.WB_MIN_CURRENT - cfg.PV_CHARGE_AMP_TOLERANCE):
                    # Charge galore
                    wb_prox.activate_pv_charge(wallbox_connection, wallbox, Toolbox.watt_to_amp_rounded(available_power))


            logging.debug('Calculation cycle ends')
            logging.debug('')
        except Exception as e:
            logging.fatal(str(e))
            logging.fatal('Unknown error occured with communication to WB. Trying again after some seconds.')

        # write PV into DB
        # while charging, write any changed log. Otherwise only after x min
        logging.info('DB write section')

        charging = False
        for wb in wallbox:
            if wb.pv_charge_active or wb.grid_charge_active:
                charging = True

        if charging:
            database.write_solarlog_data_only_if_changed(solar_log_data)
            database.write_wallbox_data_only_if_changed(wallbox)
        else:
            # save every x seconds
            if time_tools.seconds_have_passed_since_trigger() >= cfg.SOLARLOG_WRITE_EVERY:
                database.write_solarlog_data_only_if_changed(solar_log_data)
                database.write_wallbox_data_only_if_changed(wallbox)
                time_tools.trigger_time()  # written

        # chill for some secs
        time.sleep(5)
    # end loop


if __name__ == "__main__":
    main()
