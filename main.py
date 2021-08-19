import pv_modbus_solarlog
import pv_modbus_wallbox
import logging

# log level
logging.basicConfig()
log = logging.getLogger()
log.setLevel(logging.DEBUG)


# Must have Features
# minimale Ladedauer (zB 5min)
#  min Dauer zwischen Ladevorgängen
# Umschalten PV/Sofort-Laden??




# main
# SolarLog
config_solar_log = pv_modbus_solarlog.ModbusTCPConfig('192.168.178.103', 502, slave_id=0x01)
solar_log = pv_modbus_solarlog.ModbusTCPSolarLog(config_solar_log, pv_modbus_solarlog.SolarLogReadInputs())
solar_log.get_actual_output_sync_ac()
solar_log.get_actual_consumption_sync_ac()

# RTU
config_wb_heidelberg = pv_modbus_wallbox.ModbusRTUConfig('rtu', '/dev/serial0', timeout=3, baudrate=19200, bytesize=8, parity='E',
                                                         stopbits=1)
wb_heidelberg = pv_modbus_wallbox.ModbusRTUHeidelbergWB(wb_config=config_wb_heidelberg
                                                        , wb_read_input=pv_modbus_wallbox.HeidelbergWBReadInputs()
                                                        , wb_read_holding=pv_modbus_wallbox.HeidelbergWBReadHolding()
                                                        , wb_write_holding=pv_modbus_wallbox.HeidelbergWBWriteHolding())
wb_heidelberg.connect_wb_heidelberg()
