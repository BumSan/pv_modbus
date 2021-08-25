import datetime
from pv_modbus_wallbox import WBDef

class WBSystemState:
    def __init__(self, slave_id):
        self.slave_id = slave_id

    charge_state: WBDef = 0

    pcb_temperature = 0

    standby_requested: bool = False
    standby_active: bool = False

    max_current_requested = 0
    max_current_active = 0

    max_failsafe_current_requested = 0
    max_failsafe_current_active = 0

    pv_charge_active: bool = False

    # datetime when the WB started charging
    last_charge_activation: datetime.datetime = 0
    # datetime when the WB stopped charging
    last_charge_deactivation: datetime.datetime = 0

    last_tick = 0



    # take care of min time activations
    def calc_update(self):
        if self.last_tick == 0:
            self.last_tick = datetime.datetime

        # how much time between last tick and now
        time_diff = datetime.datetime - self.last_tick
        # ToDo: take care of the model. Also needs to be synced between both WBs, so we never use more than 11 kW

        self.last_tick = datetime.datetime


