import datetime
from typing import List
from wallbox_system_state import WBSystemState
from pv_modbus_wallbox import WBDef
from pv_modbus_wallbox import ModbusRTUHeidelbergWB
import pv_modbus_wallbox
from toolbox import Toolbox
from config_file import ConfigFile
import logging


class WallboxProxy:

    def __init__(self, cfg: ConfigFile):
        self.cfg = cfg

    # check if we have to activate standby
    def set_standby_if_required(self, wallbox_connection: ModbusRTUHeidelbergWB, wallbox: WBSystemState):
        if self.is_plug_connected_and_charge_ready(wallbox):
            if wallbox.standby_active == WBDef.DISABLE_STANDBY:
                if wallbox_connection.set_standby_control(wallbox.slave_id, WBDef.ENABLE_STANDBY):
                    wallbox.standby_active = WBDef.ENABLE_STANDBY

    # deactivate standby
    def deactivate_standby(self, wallbox_connection: ModbusRTUHeidelbergWB, wallbox: WBSystemState):
        if wallbox.standby_active != WBDef.DISABLE_STANDBY:
            if wallbox_connection.set_standby_control(wallbox.slave_id, WBDef.DISABLE_STANDBY):
                wallbox.standby_active = WBDef.DISABLE_STANDBY
                logging.warning('WB %s StandBy Disabled', wallbox.slave_id)
            else:
                logging.fatal('WB %s StandBy _not_ Disabled', wallbox.slave_id)

    def is_plug_connected_and_charge_ready(self, wallbox: WBSystemState) -> bool:
        return wallbox.charge_state == WBDef.CHARGE_PLUG_NO_REQUEST1 \
                or wallbox.charge_state == WBDef.CHARGE_PLUG_NO_REQUEST2 \
                or wallbox.charge_state == WBDef.CHARGE_REQUEST1 \
                or wallbox.charge_state == WBDef.CHARGE_REQUEST2

    # wrapper so we can filter and work on min time
    def set_current_for_wallbox(self, wallbox_connection: ModbusRTUHeidelbergWB, wallbox: WBSystemState, current: float):
        if wallbox_connection.set_max_current(wallbox.slave_id, Toolbox.amp_rounded_to_wb_format(current)):
            wallbox.max_current_active = current

    def activate_grid_charge(self, wallbox_connection: ModbusRTUHeidelbergWB, wallbox: List[WBSystemState]):
        # check how many Plugs are connected in correct state
        connected = 0
        for wb in wallbox:
            if self.is_plug_connected_and_charge_ready(wb):
                connected += 1
        # assign respective power to the wallboxes, evenly
        if connected > 0:
            for wb in wallbox:
                if self.is_plug_connected_and_charge_ready(wb):  # connected
                    self.set_current_for_wallbox(wallbox_connection, wb, self.cfg.WB_SYSTEM_MAX_CURRENT // connected)
                    logging.warning('Wallbox ID %s, current set to %s A', wb.slave_id, self.cfg.WB_SYSTEM_MAX_CURRENT // connected)
                    if not wb.grid_charge_active:
                        wb.grid_charge_active = True
                        wb.last_charge_activation = datetime.datetime.now()
                else:  # disconnected
                    self.set_current_for_wallbox(wallbox_connection, wb, 0)
                    if wb.grid_charge_active:
                        wb.grid_charge_active = False
                        wb.last_charge_deactivation = datetime.datetime.now()
        else:
            logging.info('No Connector connected')

    def deactivate_pv_charge_for_wallbox(self, wallbox: WBSystemState):
        wallbox.pv_charge_active = False
        wallbox.max_current_active = 0
        wallbox.last_charge_deactivation = datetime.datetime.now()

    def activate_pv_charge_for_wallbox(self, wallbox: WBSystemState, current):
        wallbox.pv_charge_active = True
        wallbox.max_current_active = current
        wallbox.last_charge_activation = datetime.datetime.now()

    def activate_pv_charge(self, wallbox_connection: ModbusRTUHeidelbergWB, wallbox: List[WBSystemState], available_current):
        used_current = 0.0

        # are any of the Wallboxes already charging with PV? then we update these first
        logging.info('Working on already active WBs first')
        for wb in wallbox:
            if wb.pv_charge_active:
                # WBs without charge request get nothing:
                if self.is_plug_connected_and_charge_ready(wb):
                    # limit the current to max value per WB
                    if available_current > self.cfg.WB_SYSTEM_MAX_CURRENT:
                        used_current = self.cfg.WB_SYSTEM_MAX_CURRENT
                    else:
                        used_current = available_current

                    # check if we have enough power for this WB. If not we try to switch it off
                    if used_current >= (self.cfg.WB_MIN_CURRENT - self.cfg.PV_CHARGE_AMP_TOLERANCE):
                        # enough power. we already charge so no check required
                        if used_current < self.cfg.WB_MIN_CURRENT:  # cant charge less than the min current
                            used_current = self.cfg.WB_MIN_CURRENT
                            logging.warning('Current adapted to WB_MIN_CURRENT %s', self.cfg.WB_MIN_CURRENT)
                        self.set_current_for_wallbox(wallbox_connection, wb, used_current)

                    else:  # we do not have enough power. Check if we can deactivate this WB
                        if self.is_pv_charge_deactivation_allowed(wb):
                            used_current = 0
                            # not 0 but stay below min to keep car charge ready (not accounted to current budget)
                            self.set_current_for_wallbox(wallbox_connection, wb, self.cfg.WB_MIN_CURRENT-1)
                            self.deactivate_pv_charge_for_wallbox(wb)
                            logging.warning('Charge deactivation for Wallbox ID %s', wb.slave_id)
                        else:  # not allowed, so reduce it to min value for now and try again later
                            used_current = self.cfg.WB_MIN_CURRENT
                            self.set_current_for_wallbox(wallbox_connection, wb, used_current)
                            logging.error('Charge deactivation for Wallbox ID %s not allowed due to time constraints',
                                          wb.slave_id)

                else:  # no charge request (anymore)
                    used_current = 0
                    self.set_current_for_wallbox(wallbox_connection, wb, used_current)
                    self.deactivate_pv_charge_for_wallbox(wb)
                    logging.info('No charge request anymore for Wallbox ID %s. Deactivating', wb.slave_id)

                logging.warning('Setting Wallbox ID %s to %s A', wb.slave_id, used_current)

                # keep track of the the current contingent
                available_current -= used_current
                logging.info('Still Available current: %s A', available_current)

        # 2nd step: if we have enough power left, we can check to activate WBs that do not charge yet
        logging.info('Check for further Wallboxes to be activated')
        for wb in wallbox:
            # WBs without charge request get nothing:
            if self.is_plug_connected_and_charge_ready(wb):
                if available_current >= (self.cfg.WB_MIN_CURRENT - self.cfg.PV_CHARGE_AMP_TOLERANCE):
                    if not wb.pv_charge_active:
                        # limit the current to max value per WB
                        if available_current > self.cfg.WB_SYSTEM_MAX_CURRENT:
                            used_current = self.cfg.WB_SYSTEM_MAX_CURRENT
                        else:
                            if available_current < self.cfg.WB_MIN_CURRENT:  # cant charge less than the min current
                                used_current = self.cfg.WB_MIN_CURRENT
                            else:
                                used_current = available_current

                        # check if we can activate this WB. If not we just try the next one
                        if self.is_pv_charge_activation_allowed(wb):
                            self.set_current_for_wallbox(wallbox_connection, wb, used_current)
                            logging.info('Setting Wallbox ID %s to %s A', wb.slave_id, used_current)
                            self.activate_pv_charge_for_wallbox(wb, used_current)
                            # keep track of the the current contingent
                            available_current -= used_current
                            logging.debug('Still Available current: %s A', available_current)
                        else:
                            logging.error('Charge activation for Wallbox ID %s not allowed due to time constraints',
                                          wb.slave_id)
                else:  # not enough power left
                    logging.info('Not enough power for charging any further Wallboxes')
                    break
            else:
                logging.info('This WB has no charge request')

    # check if WB was inactive for long enough (to avoid fast switch on/off)
    def is_pv_charge_activation_allowed(self, wallbox) -> bool:
        time_diff = datetime.datetime.now() - wallbox.last_charge_deactivation
        return time_diff.total_seconds() > self.cfg.MIN_WAIT_BEFORE_PV_ON

    # check if WB was active for long enough (to avoid fast switch on/off)
    def is_pv_charge_deactivation_allowed(self, wallbox) -> bool:
        time_diff = datetime.datetime.now() - wallbox.last_charge_activation
        return time_diff.total_seconds() > self.cfg.MIN_TIME_PV_CHARGE

    def deactivate_grid_charge(self, wallbox_connection: ModbusRTUHeidelbergWB, wallbox: List[WBSystemState]):
        for wb in wallbox:
            if wb.grid_charge_active:
                wallbox_connection.set_max_current(wb.slave_id, 0)
                wb.grid_charge_active = False
                wb.last_charge_deactivation = datetime.datetime.now()

    def deactivate_pv_charge(self, wallbox_connection: ModbusRTUHeidelbergWB, wallbox: List[WBSystemState]):
        for wb in wallbox:
            if wb.pv_charge_active:
                wallbox_connection.set_max_current(wb.slave_id, 0)
                wb.pv_charge_active = False
                wb.last_charge_deactivation = datetime.datetime.now()
