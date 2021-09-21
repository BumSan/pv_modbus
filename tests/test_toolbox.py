from toolbox import Toolbox


def test_amp_rounded_to_wb_format():
    assert Toolbox.amp_rounded_to_wb_format(8.999999) == 89
    assert Toolbox.amp_rounded_to_wb_format(8.9) == 89
    assert Toolbox.amp_rounded_to_wb_format(9.1) == 91
    assert Toolbox.amp_rounded_to_wb_format(9.00001) == 90
    assert Toolbox.amp_rounded_to_wb_format(9.0) == 90
