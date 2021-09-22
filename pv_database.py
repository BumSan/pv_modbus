from influxdb import InfluxDBClient
from pv_modbus_solarlog import SolarLogData
from wallbox_system_state import WBSystemState
from config_file import ConfigFile
import logging
import copy
import datetime
from typing import List


class PVDatabase:
    solarlog_data: SolarLogData = None
    solarlog_lastwrite = None
    wallbox_data: List[WBSystemState] = None
    wallbox_lastwrite = None

    def __init__(self, cfg: ConfigFile):
        self.cfg = cfg
        self.solarlog_lastwrite = datetime.datetime.now()
        self.wallbox_lastwrite = datetime.datetime.now()

    def write_solarlog_data(self, solar_log_data: SolarLogData):
        self.solarlog_data = copy.deepcopy(solar_log_data)
        self.solarlog_lastwrite = datetime.datetime.now()

        try:
            # Influx
            influx = InfluxDBClient(host=self.cfg.INFLUX_HOST
                                    , port=self.cfg.INFLUX_PORT
                                    , username=self.cfg.INFLUX_USER
                                    , password=self.cfg.INFLUX_PWD)

            line_solar = 'solarlog,sensor=solarlog1 pv_output=' + str(solar_log_data.actual_output) \
                         + ',consumption=' + str(solar_log_data.actual_consumption)

            if not influx.write([line_solar], params={'epoch': 's', 'db': self.cfg.INFLUX_DB_NAME}, expected_response_code=204, protocol='line'):
                logging.error('SolarLog Data write failed')

            influx.close()
        except:
            logging.fatal('DB Connection is gone')

    def write_solarlog_data_only_if_changed(self, solar_log_data: SolarLogData):
        if self.solarlog_data is not None:
            if self.solarlog_data != solar_log_data:
                self.write_solarlog_data(solar_log_data)
                logging.info('Solarlog Data written to DB')
            else:
                logging.debug('SolarLog Data not changed. Not written to DB')
        else:
            self.write_solarlog_data(solar_log_data)  # first time writing. cant compare and just write

    def write_wallbox_data(self, wallboxes: List[WBSystemState]):
        self.wallbox_data = copy.deepcopy(wallboxes)
        self.wallbox_lastwrite = datetime.datetime.now()

        try:
            # Influx
            influx = InfluxDBClient(host=self.cfg.INFLUX_HOST
                                    , port=self.cfg.INFLUX_PORT
                                    , username=self.cfg.INFLUX_USER
                                    , password=self.cfg.INFLUX_PWD)
            for wb in wallboxes:
                line_wallbox = 'wallbox,sensor=wallbox' + str(wb.slave_id)\
                               + ' charge_state=' + str(wb.charge_state) \
                               + ',pv_charge_active=' + str(wb.pv_charge_active) \
                               + ',grid_charge_active=' + str(wb.grid_charge_active) \
                               + ',max_current_active=' + str(wb.max_current_active) \
                               + ',actual_current_active=' + str(wb.actual_current_active)

                if not influx.write([line_wallbox], params={'epoch': 's', 'db': self.cfg.INFLUX_DB_NAME}, expected_response_code=204, protocol='line'):
                    logging.error('Wallbox Data write failed')

            influx.close()
        except:
            logging.fatal('DB Connection is gone')

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
            data_changed = True  # first time writing. cant compare and just write

        if data_changed:
            self.write_wallbox_data(wallboxes)
            logging.info('Wallbox Data written to DB')
        else:
            logging.debug('Wallbox Data not changed. Not written to DB')


