import datetime
from pv_modbus_wallbox import WBDef


class WBSystemState:
    def __init__(self, slave_id):
        self.slave_id = slave_id

    charge_state: WBDef = 0

    pcb_temperature = 0

    standby_requested: WBDef = WBDef.DISABLE_STANDBY
    standby_active: WBDef = WBDef.DISABLE_STANDBY

    max_current_requested = 0
    max_current_active = 0

    max_failsafe_current_requested = 0
    max_failsafe_current_active = 0

    pv_charge_active: bool = False

    # datetime when the WB started charging
    last_charge_activation: datetime.datetime = 0
    # datetime when the WB stopped charging
    last_charge_deactivation: datetime.datetime = 0

