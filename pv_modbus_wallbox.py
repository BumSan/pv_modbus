from pymodbus.client.sync import ModbusSerialClient
from pv_register_config import ModbusRegisters
from pv_register_config import HeidelbergWBReadInputs
from pv_register_config import HeidelbergWBReadHolding, HeidelbergWBWriteHolding


class ModbusRTUConfig:
    def __init__(self, mode: str, port: str, timeout: int, baudrate: int, bytesize: int, parity: str, stopbits: int):
        self.mode = mode
        self.port = port
        self.timeout = timeout
        self.baudrate = baudrate
        self.bytesize = bytesize
        self.parity = parity
        self.stopbits = stopbits


class ModbusRTUHeidelbergWB:
    def __init__(self, wb_config: ModbusRTUConfig
                 , wb_read_input: HeidelbergWBReadInputs
                 , wb_read_holding: HeidelbergWBReadHolding
                 , wb_write_holding: HeidelbergWBWriteHolding):
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

    # do all the Read Input Registers
    def _call_remote_input_registers(self, slave_id: int, register_set: ModbusRegisters) -> int:
        read = self.wb_handle.read_input_registers(register_set.register
                                                   , register_set.length
                                                   , unit=slave_id)
        print(read.registers)
        return read.registers

    def get_charging_state(self, slave_id: int) -> int:
        return self._call_remote_input_registers(slave_id, self.wb_read_input.chargingState)

    def get_actual_charge_power(self, slave_id: int) -> int:
        return self._call_remote_input_registers(slave_id, self.wb_read_input.actualChargePower)

    def get_pcb_temperature(self, slave_id: int) -> int:
        return self._call_remote_input_registers(slave_id, self.wb_read_input.PCB_Temperature)

    # do all the Read Holding Registers
    def _call_remote_read_holding_registers(self, slave_id: int, register_set: ModbusRegisters) -> int:
        read = self.wb_handle.read_holding_registers(register_set.register
                                                     , register_set.length
                                                     , unit=slave_id)
        print(read.registers)
        return read.registers

    def get_max_current(self, slave_id: int) -> int:
        return self._call_remote_read_holding_registers(slave_id, self.wb_read_holding.maxCurrent)

    def get_failsafe_max_current(self, slave_id: int) -> int:
        return self._call_remote_read_holding_registers(slave_id, self.wb_read_holding.failsafeMaxCurrent)

    # do all the write holding registers
    def _call_remote_write_holding_registers(self, slave_id: int, register_set: ModbusRegisters) -> int:
        response = self.wb_handle.write_registers(register_set.register
                                                  , register_set.length
                                                  , unit=slave_id)
        if response.isError():
            print('Could not write Register' + str(register_set.register))
        return response

    def set_standby_control(self, slave_id: int):
        return self._call_remote_write_holding_registers(slave_id, self.wb_write_holding.standByControl)

    def set_max_current(self, slave_id: int):
        return self._call_remote_write_holding_registers(slave_id, self.wb_write_holding.maxCurrent)

    def set_failsafe_max_current(self, slave_id: int):
        return self._call_remote_write_holding_registers(slave_id, self.wb_write_holding.failsafeMaxCurrent)
