
class ConfigFile:

    def __init__(self, config):
        self.HAVE_SWITCH = config['SWITCH'].getboolean('HAVE_SWITCH')

        self.SOLARLOG_IP = config['SOLARLOG']['SOLARLOG_IP']
        self.SOLARLOG_PORT = int(config['SOLARLOG']['SOLARLOG_PORT'])
        self.SOLARLOG_SLAVEID = int(config['SOLARLOG']['SOLARLOG_SLAVEID'])

        self.WB1_SLAVEID = int(
            config['WALLBOX']['WB1_SLAVEID'])  # Slave ID is also Priority (e.g. for new(!) PV Charge requests)
        self.WB2_SLAVEID = int(config['WALLBOX']['WB2_SLAVEID'])  # smaller numbers mean higher priority
        self.WB_RTU_DEVICE = config['WALLBOX']['WB_RTU_DEVICE']

        self.WB_SYSTEM_MAX_CURRENT = float(config['WALLBOX']['WB_SYSTEM_MAX_CURRENT'])  # Ampere
        self.WB_MIN_CURRENT = float(config['WALLBOX']['WB_MIN_CURRENT'])  # Ampere
        # Amp -> if we do not have enough PV power to reach the WB min, use this threshold value
        self.PV_CHARGE_AMP_TOLERANCE = float(config['WALLBOX']['PV_CHARGE_AMP_TOLERANCE'])
        # and take up to x Amp from grid

        # time constraints
        # secs. We want to charge at least for x secs before switch on->off (PV charge related)
        self.MIN_TIME_PV_CHARGE = int(config['TIME']['MIN_TIME_PV_CHARGE'])
        # this is "Min time on"
        # secs. We want to wait at least for x secs before switch off->on (PV charge related)
        self.MIN_WAIT_BEFORE_PV_ON = int(config['TIME']['MIN_TIME_PV_CHARGE'])
        # this is "Min time off"

        self.SOLARLOG_WRITE_EVERY = int(config['LOGGING']['SOLARLOG_WRITE_EVERY'])  # *5s

        self.GPIO_SWITCH = int(config['SWITCH']['GPIO_SWITCH'])

        self.INFLUX_HOST = config['LOGGING']['INFLUX_HOST']
        self.INFLUX_PORT = int(config['LOGGING']['INFLUX_PORT'])
        self.INFLUX_USER = config['LOGGING']['INFLUX_USER']
        self.INFLUX_PWD = config['LOGGING']['INFLUX_PWD']
        self.INFLUX_DB_NAME = config['LOGGING']['INFLUX_DB_NAME']

        # every x seconds, at least (earlier if data has changed)
        self.WALLBOX_MIN_WRITE_CYCLE = float(config['LOGGING']['WALLBOX_MIN_WRITE_CYCLE'])
        # every x seconds, at least (earlier if data has changed)
        self.SOLARLOG_MIN_WRITE_CYCLE = float(config['LOGGING']['SOLARLOG_MIN_WRITE_CYCLE'])