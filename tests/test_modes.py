from definitions import PyshaMode
from modes.instrument_selection_mode import InstrumentSelectionMode

def test_PyshaMode(mocker):
    app = {}
    mode = PyshaMode(app)
    
    assert mode.name == ""
    assert mode.app == app
    
class TestInstrumentSelectionMode:
    def test_contructor(self):
        app={}
        mode = InstrumentSelectionMode(app)
        assert mode.name == ""