import copy
from typing import List
from influxdb import InfluxDBClient
from pv_modbus_solarlog import SolarLogData
from wallbox_system_state import WBSystemState
import logging

INFLUX_HOST = '192.168.178.106'
INFLUX_PORT = 8086
INFLUX_USER = 'pv_modbus'
INFLUX_PWD = '#'


class PVDatabase:
    solarlog_data: SolarLogData = None
    wallbox_data: List[WBSystemState] = None

    def __init__(self):
        pass

    def write_solarlog_data(self, solar_log_data: SolarLogData):
        self.solarlog_data = copy.deepcopy(solar_log_data)
        # Influx
        influx = InfluxDBClient(host=INFLUX_HOST
                                , port=INFLUX_PORT
                                , username=INFLUX_USER
                                , password=INFLUX_PWD)

        line_solar = 'solarlog,sensor=solarlog1 pv_output=' + str(solar_log_data.actual_output) \
                     + ',consumption=' + str(solar_log_data.actual_consumption)
        if not influx.write([line_solar], {'db': 'pv_modbus'}, 204, 'line'):
            logging.error('SolarLog Data write failed')

        influx.close()

    def write_solarlog_data_only_if_changed(self, solar_log_data: SolarLogData):
        if self.solarlog_data is not None:
            if self.solarlog_data != solar_log_data:
                self.write_solarlog_data(solar_log_data)
            else:
                logging.debug('SolarLog Data not changed. Not written to DB')
        else:
            self.write_solarlog_data(solar_log_data)

    def write_wallbox_data(self, wallboxes: List[WBSystemState]):
        self.wallbox_data = copy.deepcopy(wallboxes)
        # Influx
        influx = InfluxDBClient(host=INFLUX_HOST
                                , port=INFLUX_PORT
                                , username=INFLUX_USER
                                , password=INFLUX_PWD)
        for wb in wallboxes:
            line_wallbox = 'wallbox,sensor=wallbox' + str(wb.slave_id)\
                           + ' charge_state=' + str(wb.charge_state) \
                           + ',pv_charge_active=' + str(wb.pv_charge_active) \
                           + ',grid_charge_active=' + str(wb.grid_charge_active) \
                           + ',max_current_active=' + str(wb.max_current_active) \
                           + ',actual_current_active=' + str(wb.actual_current_active)

            if not influx.write([line_wallbox], {'db': 'pv_modbus'}, 204, 'line'):
                logging.error('Wallbox Data write failed')

        influx.close()

    def write_wallbox_data_only_if_changed(self, wallboxes: List[WBSystemState]):
        data_changed = False
        ctr = 0
        if self.wallbox_data is not None:
            for wb in wallboxes:
                if self.wallbox_data[ctr] != wb:
                    data_changed = True
                    break
                ctr += 1
        else:
            data_changed = True

        if data_changed:
            self.write_wallbox_data(wallboxes)
        else:
            logging.debug('Wallbox Data not changed. Not written to DB')


