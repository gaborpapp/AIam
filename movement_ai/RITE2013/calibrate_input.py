import wx
from states import state_machine
from config_manager import load_config, save_config
from argparse import ArgumentParser
from simple_osc_receiver import OscReceiver
from vector import *

class Calibrator(wx.Frame):
    def __init__(self):
        wx.Frame.__init__(self, None, wx.ID_ANY, "Input calibrator")
        self.Bind(wx.EVT_KEY_DOWN, self.OnKeyDown)
        self.SetFocus()

        menubar = wx.MenuBar()
        file_menu = wx.Menu()
        save_item = file_menu.Append(-1, 'Save')
        quit_item = file_menu.Append(-1, 'Quit')
        menubar.Append(file_menu, '&File')
        self.SetMenuBar(menubar)
        self.Bind(wx.EVT_MENU, lambda event: save_config(config, args.config), save_item)
        self.Bind(wx.EVT_MENU, lambda event: self.Close(), quit_item)

        sizer = wx.GridSizer(len(config.states), 4, 5, 5)
        self.SetSizer(sizer)

        state_id = 1
        self._position_text = {}
        self._state_id_to_name = {}
        for state_name in list(state_machine.states.keys()):
            self._state_id_to_name[state_id] = state_name
            button = wx.Button(self, state_id, state_name)
            button.Bind(wx.EVT_LEFT_DOWN, self._on_button_down)
            button.Bind(wx.EVT_LEFT_UP, self._on_button_up)
            sizer.Add(button)
            state_position_texts = []
            for i in range(3):
                text = wx.TextCtrl(self, -1, "")
                state_position_texts.append(text)
                sizer.Add(text)
            self._position_text[state_name] = state_position_texts
            self._update_position_text(state_name)
            state_id += 1

        self._calibrated_state_name = None
        self._timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self._refresh, self._timer)
        self._timer.Start(refresh_interval * 1000)

        self.Show()

    def _refresh(self, event):
        osc_receiver.serve()

    def _update_position_text(self, state_name):
        position = config.states[state_name]
        if position:
            for i in range(3):
                text = self._position_text[state_name][i]
                text.SetValue(str(position[i]))
        else:
            for i in range(3):
                text = self._position_text[state_name][i]
                text.SetValue("")
            
    def _on_button_down(self, event):
        self._calibrated_state_name = self._state_id_to_name[event.GetId()]
        self._calibrated_positions = []
        config.states[self._calibrated_state_name] = None
        self._update_position_text(self._calibrated_state_name)

    def _on_button_up(self, event):
        if len(self._calibrated_positions) > 0:
            calibrated_position = sum(self._calibrated_positions) / \
                                  len(self._calibrated_positions)
            config.states[self._calibrated_state_name] = calibrated_position.v
            self._update_position_text(self._calibrated_state_name)
        self._calibrated_state_name = None

    def update_input_position(self, input_position):
        if self._calibrated_state_name:
            self._calibrated_positions.append(input_position)

    def OnKeyDown(self, event):
        keycode = event.GetKeyCode()
        if keycode == wx.WXK_ESCAPE:
            self.Close()
        event.Skip()

parser = ArgumentParser()
parser.add_argument("-config", type=str)
parser.add_argument("-refresh-rate", type=float, default=60.0)
args = parser.parse_args()
config = load_config(args.config)
refresh_interval = 1.0 / args.refresh_rate

def receive_input_position(path, args, types, src, user_data):
    global input_position
    position_tuple = args
    input_position = Vector3d(*position_tuple)
    calibrator.update_input_position(input_position)

input_position = None
osc_receiver = OscReceiver(7892, listen="localhost")
osc_receiver.add_method("/input_position", "fff", receive_input_position)
osc_receiver.start()

if __name__ == "__main__":
    app = wx.App(redirect=False)
    calibrator = Calibrator()
    app.MainLoop()
