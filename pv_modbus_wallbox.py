from pymodbus.client.sync import ModbusSerialClient
from pv_register_config import ModbusRegisters
from pv_register_config import HeidelbergWBReadInputs
from pv_register_config import HeidelbergWBReadHolding, HeidelbergWBWriteHolding

import logging


class WBDef:
    ENABLE_STANDBY = 0
    DISABLE_STANDBY = 4
    CHARGE_NOPLUG1 = 2
    CHARGE_NOPLUG2 = 3
    CHARGE_PLUG_NO_REQUEST1 = 4
    CHARGE_PLUG_NO_REQUEST2 = 5
    CHARGE_REQUEST1 = 6
    CHARGE_REQUEST2 = 7

    # for testing
    FAKE_WB_CONNECTION = False


class ModbusRTUConfig:
    def __init__(self, method: str, port: str, timeout: int, baudrate: int, bytesize: int, parity: str, stopbits: int, strict: bool):
        self.method = method
        self.port = port
        self.timeout = timeout
        self.baudrate = baudrate
        self.bytesize = bytesize
        self.parity = parity
        self.stopbits = stopbits
        self.strict = strict


class ModbusRTUHeidelbergWB:
    def __init__(self, wb_config: ModbusRTUConfig
                 , wb_read_input: HeidelbergWBReadInputs
                 , wb_read_holding: HeidelbergWBReadHolding
                 , wb_write_holding: HeidelbergWBWriteHolding):
        self.wb_config = wb_config
        self.wb_read_input = wb_read_input
        self.wb_read_holding = wb_read_holding
        self.wb_write_holding = wb_write_holding
        self.wb_handle = ModbusSerialClient(method=wb_config.method
                                            , port=wb_config.port
                                            , timeout=wb_config.timeout
                                            , baudrate=wb_config.baudrate
                                            , bytesize=wb_config.bytesize
                                            , parity=wb_config.parity
                                            , stopbits=wb_config.stopbits
                                            , strict=wb_config.strict)
        self.wb_handle.inter_char_timeout = 0.05  # https://github.com/riptideio/pymodbus/issues/353

    def connect_wb_heidelberg(self):
        if WBDef.FAKE_WB_CONNECTION:
            return True

        result = self.wb_handle.connect()
        if not result:
            logging.fatal('No Connection possible to WB Heidelberg')
        return result

    def close_wb_heidelberg(self):
        self.wb_handle.close()
        logging.fatal('Closing connection to WB Heidelberg')

    # do all the Read Input Registers
    def _call_remote_input_registers(self, slave_id: int, register_set: ModbusRegisters):
        read = self.wb_handle.read_input_registers(register_set.register
                                                   , register_set.length
                                                   , unit=slave_id)
        return read.registers

    def get_charging_state(self, slave_id: int):
        if not WBDef.FAKE_WB_CONNECTION:
            read = self._call_remote_input_registers(slave_id, self.wb_read_input.chargingState)
            logging.info('Charge state for WB %s: %s', slave_id, read)
            return read
        else:
            logging.warning('Testmode active')
            return WBDef.CHARGE_REQUEST1

    def get_actual_charge_power(self, slave_id: int):  # returns in Watt
        if not WBDef.FAKE_WB_CONNECTION:
            read = self._call_remote_input_registers(slave_id, self.wb_read_input.actualChargePower)
            logging.info('Charge power for WB %s: %s', slave_id, read)
            return read
        else:
            logging.warning('Testmode active')
            return 100

    def get_pcb_temperature(self, slave_id: int):
        return self._call_remote_input_registers(slave_id, self.wb_read_input.PCB_Temperature)

    # do all the Read Holding Registers
    def _call_remote_read_holding_registers(self, slave_id: int, register_set: ModbusRegisters):
        read = self.wb_handle.read_holding_registers(register_set.register
                                                     , register_set.length
                                                     , unit=slave_id)
        logging.info('%s', read.registers)
        return read.registers

    def get_max_current(self, slave_id: int):
        return self._call_remote_read_holding_registers(slave_id, self.wb_read_holding.maxCurrent)

    def get_failsafe_max_current(self, slave_id: int):
        return self._call_remote_read_holding_registers(slave_id, self.wb_read_holding.failsafeMaxCurrent)

    # do all the write holding registers
    def _call_remote_write_holding_registers(self, register_set: ModbusRegisters, val, slave_id: int):
        if not WBDef.FAKE_WB_CONNECTION:
            response = self.wb_handle.write_registers(register_set.register
                                                      , values=val
                                                      , unit=slave_id)
            if response.isError():
                logging.fatal('Could not write Register %s', register_set.register)
                return False
            return response
        else:
            logging.warning('Testmode active')
            return True

    def set_standby_control(self, slave_id: int, val):
        return self._call_remote_write_holding_registers(self.wb_write_holding.standByControl, val, slave_id)

    def set_max_current(self, slave_id: int, val: int):
        # convert Ampere to WB values
        val = val*10
        return self._call_remote_write_holding_registers(self.wb_write_holding.maxCurrent, val, slave_id)

    def set_failsafe_max_current(self, slave_id: int, val: int):
        # convert Ampere to WB values
        val = val*10
        return self._call_remote_write_holding_registers(self.wb_write_holding.failsafeMaxCurrent, val, slave_id)


