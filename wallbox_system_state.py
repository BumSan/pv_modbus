import datetime


class WBSystemState:
    def __init__(self, slave_id):
        self.slave_id = slave_id

    charge_state = 0

    pcb_temperature = 0

    standby_requested = False
    standby_active = False

    max_current_requested = 0
    max_current_active = 0

    max_failsafe_current_requested = 0
    max_failsafe_current_active = 0

    pv_charge_active = False

    last_tick = 0

    # time constraints
    min_time_pv_charge = 5*60  # secs. We want to charge at least for x secs before switch on->off (PV charge related)
    min_wait_before_pv_on = 2*60  # secs. We want to wait at least for x secs before switch off->on (PV charge related)

    # take care of min time activations
    def calc_update(self):
        if self.last_tick == 0:
            self.last_tick = datetime.datetime

        # how much time between last tick and now
        time_diff = datetime.datetime - self.last_tick
        # ToDo: take care of the model. Also needs to be synced between both WBs, so we never use more than 11 kW

        self.last_tick = datetime.datetime


