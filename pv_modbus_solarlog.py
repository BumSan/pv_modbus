from pymodbus.client.sync import ModbusTcpClient
from pv_register_config import SolarLogReadInputs

import logging


class ModbusTCPConfig:
    def __init__(self, ip: str, port: int, slave_id):
        self.IP = ip
        self.Port = port
        self.slave_id = slave_id


class ModbusTCPSolarLog:
    def __init__(self, solar_log_cfg: ModbusTCPConfig, solar_log_register: SolarLogReadInputs):
        self.solar_log_cfg = solar_log_cfg
        self.solar_log_register = solar_log_register
        self.solar_log_handle = ModbusTcpClient(solar_log_cfg.IP, solar_log_cfg.Port, auto_open=True)

    def connect_solar_log(self):
        if not self.solar_log_handle.connect():
            logging.fatal('No Connection possible to Solar Log')

    def get_actual_output_sync_ac(self):
        # connect to SolarLog
        read = self.solar_log_handle.read_input_registers(self.solar_log_register.P_AC.register
                                                          , self.solar_log_register.P_AC.length
                                                          , unit=self.solar_log_cfg.slave_id)
        val = (read.registers[1] << 16) + read.registers[0]
        return val  # in Watt

    def get_actual_consumption_sync_ac(self):
        # connect to SolarLog
        read = self.solar_log_handle.read_input_registers(self.solar_log_register.P_AC_Consumption.register
                                                          , self.solar_log_register.P_AC_Consumption.length
                                                          , unit=self.solar_log_cfg.slave_id)
        val = (read.registers[1] << 16) + read.registers[0]
        return val  # in Watt


class SolarLogData:
    actual_output = 0
    actual_consumption = 0

    def __init__(self):
        pass

    def __eq__(self, other):
        if not isinstance(other, SolarLogData):
            return NotImplemented

        return self.actual_output == other.actual_output and self.actual_consumption == other.actual_consumption
