from pymodbus.client.sync import ModbusTcpClient
from pv_register_config import SolarLogReadInputs


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
            print('No Connection possible to Solar Log')

    def get_actual_output_sync_ac(self):
        # connect to SolarLog
        read = self.solar_log_handle.read_input_registers(self.solar_log_register.P_AC.register
                                                          , self.solar_log_register.P_AC.length
                                                          , unit=self.solar_log_cfg.slave_id)
        val = (read.registers[1] << 16) + read.registers[0]
        print('Actual AC Output: ' + str(val) + ' W')
        return val  # in Watt

    def get_actual_consumption_sync_ac(self):
        # connect to SolarLog
        read = self.solar_log_handle.read_input_registers(self.solar_log_register.P_AC_Consumption.register
                                                          , self.solar_log_register.P_AC_Consumption.length
                                                          , unit=self.solar_log_cfg.slave_id)
        val = (read.registers[1] << 16) + read.registers[0]
        print('Actual AC consumption: ' + str(val) + ' W')
        return val  # in Watt
