
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
