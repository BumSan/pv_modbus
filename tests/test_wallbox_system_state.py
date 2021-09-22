from wallbox_system_state import WBSystemState
from pv_modbus_wallbox import WBDef
import pytest


@pytest.mark.activate
def test_wbsystem_state_equality():
    wb1 = WBSystemState(2)
    wb2 = WBSystemState(3)
    assert wb1 == wb2

    wb1.charge_state = WBDef.CHARGE_REQUEST1
    wb1.pv_charge_active = True
    wb1.grid_charge_active = False
    wb1.max_current_active = 8
    wb1.actual_current_active = 8
    assert not wb1 == wb2

    wb2.charge_state = WBDef.CHARGE_REQUEST1
    wb2.pv_charge_active = True
    wb2.grid_charge_active = False
    wb2.max_current_active = 8
    wb2.actual_current_active = 8
    wb2.standby_active = True
    assert wb1 == wb2

    wb1.standby_active = False
    assert wb1 == wb2



