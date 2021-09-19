import copy
import datetime
from typing import List
from influxdb import InfluxDBClient
from pv_modbus_solarlog import SolarLogData
from wallbox_system_state import WBSystemState
import logging
import configparser


config = configparser.ConfigParser()
config.read('pv_modbus_config.ini')

INFLUX_HOST = config['LOGGING']['INFLUX_HOST']
INFLUX_PORT = int(config['LOGGING']['INFLUX_PORT'])
INFLUX_USER = config['LOGGING']['INFLUX_USER']
INFLUX_PWD = config['LOGGING']['INFLUX_PWD']
INFLUX_DB_NAME = config['LOGGING']['INFLUX_DB_NAME']

# every x seconds, at least (earlier if data has changed)
WALLBOX_MIN_WRITE_CYCLE = float(config['LOGGING']['WALLBOX_MIN_WRITE_CYCLE'])
# every x seconds, at least (earlier if data has changed)
SOLARLOG_MIN_WRITE_CYCLE = float(config['LOGGING']['SOLARLOG_MIN_WRITE_CYCLE'])


class PVDatabase:
    solarlog_data: SolarLogData = None
    solarlog_lastwrite = None
    wallbox_data: List[WBSystemState] = None
    wallbox_lastwrite = None

    def __init__(self):
        self.solarlog_lastwrite = datetime.datetime.now()
        self.wallbox_lastwrite = datetime.datetime.now()

    def write_solarlog_data(self, solar_log_data: SolarLogData):
        self.solarlog_data = copy.deepcopy(solar_log_data)
        self.solarlog_lastwrite = datetime.datetime.now()

        try:
            # Influx
            influx = InfluxDBClient(host=INFLUX_HOST
                                    , port=INFLUX_PORT
                                    , username=INFLUX_USER
                                    , password=INFLUX_PWD)

            line_solar = 'solarlog,sensor=solarlog1 pv_output=' + str(solar_log_data.actual_output) \
                         + ',consumption=' + str(solar_log_data.actual_consumption)

            if not influx.write([line_solar], params={'epoch': 's', 'db': INFLUX_DB_NAME}, expected_response_code=204, protocol='line'):
                logging.error('SolarLog Data write failed')

            influx.close()
        except:
            logging.fatal('DB Connection is gone')

    def write_solarlog_data_only_if_changed(self, solar_log_data: SolarLogData):
        time_diff = datetime.datetime.now() - self.solarlog_lastwrite
        if self.solarlog_data is not None:
            if self.solarlog_data != solar_log_data:
                self.write_solarlog_data(solar_log_data)
            elif time_diff.total_seconds() > SOLARLOG_MIN_WRITE_CYCLE:
                self.write_solarlog_data(solar_log_data)
                logging.debug('SolarLog Data written due to min cycle time')
            else:
                logging.debug('SolarLog Data not changed. Not written to DB')
        else:
            self.write_solarlog_data(solar_log_data)

    def write_wallbox_data(self, wallboxes: List[WBSystemState]):
        self.wallbox_data = copy.deepcopy(wallboxes)
        self.wallbox_lastwrite = datetime.datetime.now()

        try:
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

                if not influx.write([line_wallbox], params={'epoch': 's', 'db': INFLUX_DB_NAME}, expected_response_code=204, protocol='line'):
                    logging.error('Wallbox Data write failed')

            influx.close()
        except:
            logging.fatal('DB Connection is gone')

    def write_wallbox_data_only_if_changed(self, wallboxes: List[WBSystemState]):
        time_diff = datetime.datetime.now() - self.wallbox_lastwrite
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

        if time_diff.total_seconds() > WALLBOX_MIN_WRITE_CYCLE:
            data_changed = True
            logging.debug('Wallbox Data written due to min cycle time')

        if data_changed:
            self.write_wallbox_data(wallboxes)
        else:
            logging.debug('Wallbox Data not changed. Not written to DB')


