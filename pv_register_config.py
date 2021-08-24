
# basic structure to describe the register config
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
