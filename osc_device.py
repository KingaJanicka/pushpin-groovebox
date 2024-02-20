from osc_controls import OSCControl, OSCMacroControl, SpacerControl

class OSCDevice(object):
    id = None
    label = ""
    definition = {}
    controls = []
    client = None
    osc = {'client': {}, 'server': {}, 'dispatcher': {}}
    
    def __init__(self, filename, config, osc, **kwargs):
        self.id = filename
        self.definition = config
        self.osc = osc
        self.label = config.get("device_name", "Device")
        self.dispatcher = osc.get('dispatcher', None)
        # Uncomment for debugging
        # self.dispatcher.map('*', print)
        client = osc.get('client', None)
        init = config.get('init', [])
        get_color = kwargs.get('get_color')
        control_definitions = config.get('osc', {}).get('controls', [])

        if client and len(init) > 0:
            for cmd in init:
                reversed = list(cmd)
                reversed.reverse()
                val, address, *rest = reversed
                client.send_message(address, val)
                
        # Configure controls
        if len(control_definitions) > 0:
            for control_def in control_definitions:

                if isinstance(control_def, list):
                    if len(control_def) == 0: # spacer
                        control = SpacerControl()
                        self.controls.append(control)

                    elif len(control_def) == 2: # macro
                        item_label, params = control_def
                        control = OSCMacroControl(item_label, params, get_color, client.send_message if client else None)

                        for param in params:
                            address, min, max = param
                            osc['dispatcher'].map(address, control.set_state)
                        
                        self.controls.append(control)   
                        
                    else: # individual (normal) control
                        item_label, address, min, max = control_def
                        control = OSCControl(item_label, address, min, max, get_color,  client.send_message if client else None)    
                        osc['dispatcher'].map(address, control.set_state)
                        self.controls.append(control)        

                elif isinstance(control_def, dict): # control group
                    # TODO
                    pass
                else:
                    Exception('Invalid parameter: ', control_def)
                    
    def draw(self, ctx):
        active_controls = [control for control in filter(lambda x: x.active, self.controls)][0:8]
        offset = 0
        for control in active_controls:
            control.draw(ctx, offset)
            offset += control.size