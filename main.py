from pymodbus.client.sync import ModbusTcpClient
from pymodbus.client.sync import ModbusSerialClient
import logging

# log level
logging.basicConfig()
log = logging.getLogger()
log.setLevel(logging.DEBUG)


# Must have Features
# minimale Ladedauer (zB 5min)
# Umschalten PV/Sofort-Laden

#  Wallbox Energy Control uses 19.200 bit/sec, 8 data bit, 1 parity bit (even), 1 stop bit

# ToDo: Put this extra to a config file
class ModbusTCPConfig:
    def __init__(self, ip: str, port: int, slave_id):
        self.IP = ip
        self.Port = port
        self.slave_id = slave_id


class ModbusRTUConfig:
    def __init__(self, mode: str, port: str, timeout: int, baudrate: int, bytesize: int, parity: str, stopbits: int):
        self.mode = mode
        self.port = port
        self.timeout = timeout
        self.baudrate = baudrate
        self.bytesize = bytesize
        self.parity = parity
        self.stopbits = stopbits


# data structure
class ModbusRegisters:
    def __init__(self, register, length: int):
        self.register = register
        self.length = length


class HeidelbergWBReadInputs:
    chargingState = ModbusRegisters(5, 1)  # uint16: A1, 3=A2, 4=B1, 5=B2, 6=C1, 7=C2, 8=derating, 9=E, 10=F, 11=ERR
    # A No vehicle plugged
    # B Vehicle plugged without charging request
    # C Vehicle plugged with charging request
    # x1 Wallbox doesn't allow charging
    # x2 Wallbox allows charging
    PCB_Temperature = ModbusRegisters(9, 1)  # PCB-Temperatur in 0.1 °C. int16: 325 = +32.5 °C / -145 = -14.5 °C
    actualChargePower = ModbusRegisters(14, 1)  # Power (L1+L2+L3) in VA uint16: 1000 --> 1kW
    P_AC_Consumption = ModbusRegisters(3518, 2)  # Momentaner Gesamtverbrauch AC


class HeidelbergWBReadHolding:
    maxCurrent = ModbusRegisters(261, 1)  # Maximal current command uint16  [0; 60 to 160] 100 = 10A
    failsafeMaxCurrent = ModbusRegisters(262, 1)  # FailSafe Current configuration


class HeidelbergWBWriteHolding:
    standByControl = ModbusRegisters(258, 1)  # Standby Function Control uint16
    # 0 -> enable StandBy Funktion
    # 4-> disable StandBy Funktion
    maxCurrent = ModbusRegisters(261, 1)  # Maximal current command uint16  [0; 60 to 160] 100 = 10A
    failsafeMaxCurrent = ModbusRegisters(262, 1)  # FailSafe Current configuration
    # (in case loss of Modbus communication) uint16  [0; 60 to 160] 100 = 10A. Default = 0


class SolarLogReadInputs:
    lastUpdateTime = ModbusRegisters(3500, 2)  # Unixtime, wann das letzte Registerupdate erfolgt ist.
    P_AC = ModbusRegisters(3502, 2)  # Gesamte AC Leistung
    P_DC = ModbusRegisters(3504, 2)  # Gesamte DC Leistung
    P_AC_Consumption = ModbusRegisters(3518, 2)  # Momentaner Gesamtverbrauch AC


class ModbusRTUHeidelbergWB:
    def __init__(self, wb_config: ModbusRTUConfig
                 , wb_read_input: HeidelbergWBReadInputs
                 , wb_read_holding: HeidelbergWBReadHolding
                 , wb_write_holding: HeidelbergWBWriteHolding) -> object:
        self.wb_config = wb_config
        self.wb_read_input = wb_read_input
        self.wb_read_holding = wb_read_holding
        self.wb_write_holding = wb_write_holding
        self.wb_handle = ModbusSerialClient(mode=wb_config.mode
                                            , port=wb_config.port
                                            , timeout=wb_config.timeout
                                            , baudrate=wb_config.baudrate
                                            , bytesize=wb_config.bytesize
                                            , parity=wb_config.parity
                                            , stopbits=wb_config.stopbits)

    def connect_wb_heidelberg(self):
        if not self.wb_handle.connect():
            print('No Connection possible to WB Heidelberg')


class ModbusTCPSolarLog:
    def __init__(self, solar_log_cfg: ModbusTCPConfig, solar_log_register: SolarLogReadInputs):
        self.solarLogCfg = solar_log_cfg
        self.solarLogReg = solar_log_register
        self.solarLogHandle = ModbusTcpClient(solar_log_cfg.IP, solar_log_cfg.Port, auto_open=True)

    def connect_solar_log(self):
        if not self.solarLogHandle.connect():
            print('No Connection possible to Solar Log')

    def get_actual_output_sync_ac(self):
        # connect to SolarLog
        read = self.solarLogHandle.read_input_registers(self.solarLogReg.P_AC.register
                                                        , self.solarLogReg.P_AC.length
                                                        , unit=self.solarLogCfg.slave_id)
        val = (read.registers[1] << 16) + read.registers[0]
        print('Actual AC Output: ' + str(val) + ' W')
        return val  # in Watt

    def get_actual_consumption_sync_ac(self):
        # connect to SolarLog
        read = self.solarLogHandle.read_input_registers(self.solarLogReg.P_AC_Consumption.register
                                                        , self.solarLogReg.P_AC_Consumption.length
                                                        , unit=self.solarLogCfg.slave_id)
        val = (read.registers[1] << 16) + read.registers[0]
        print('Actual AC consumption: ' + str(val) + ' W')
        return val  # in Watt


# main
# SolarLog
config_solar_log = ModbusTCPConfig('192.168.178.103', 502, slave_id=0x01)
solar_log = ModbusTCPSolarLog(config_solar_log, SolarLogReadInputs())
solar_log.get_actual_output_sync_ac()
solar_log.get_actual_consumption_sync_ac()


# RTU
config_wb_heidelberg = ModbusRTUConfig('rtu', '/dev/uart0', timeout=3, baudrate=19200, bytesize=8, parity='E', stopbits=1)
wb_heidelberg = ModbusRTUHeidelbergWB(config_wb_heidelberg
                                      , wb_read_input=HeidelbergWBReadInputs
                                      , wb_read_holding=HeidelbergWBReadHolding
                                      , wb_write_holding=HeidelbergWBWriteHolding)
wb_heidelberg.connect_wb_heidelberg()

