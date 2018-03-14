
# coding: utf-8

# The methods to send input to the target emulator (PPSSPP) are somewhat convoluted
# due to the odd restrictions we have (only seems to respond to XInput).
# We use a personally modified version of the pyvjoy module
# (https://github.com/dkhachatrian/pyvjoy/commit/55a9c56550aa9ab7bc202a653a303ee68b5b4138 definitely works)
# to create a virtual gamepad that can handle synchronous update. 
# Then we wrap it as an XInput device using XOutput (https://github.com/csutorasa/XOutput)
# 
# Now, if we want to record human controller input so that it could be fed into our VJoyDevice (i.e. record human-made macros), 
# we need to wrap VJoy input to look like XInput (since VJoy itself cannot).
# Specifically, we use PYXInput (https://github.com/bayangan1991/PYXInput)
# to record a list of states of the human-controlled gamepad 
# We then map the recorded XInput values to the VJoy values that correspond with the mapping in our XOutput config.
#
# The current playback implementation seems to be fairly reliable (~90%+) assuming reasonably consistent machine/emulator performance

# In[1]:


import pyxinput

from enum import Enum
import pyvjoy
import time

import pickle # to save macros

import re

from time import perf_counter as _time



#############
### Variables
#############

# for binary states (i.e. buttons and discrete POVs)
ON = 1
OFF = 0

# from xinput specification
xinput_buttons = {
    'DPAD_UP': 0x0001,
    'DPAD_DOWN': 0x0002,
    'DPAD_LEFT': 0x0004,
    'DPAD_RIGHT': 0x0008,
    'START': 0x0010,
    'BACK': 0x0020,
    'LEFT_THUMB': 0x0040,
    'RIGHT_THUMB': 0x0080,
    'LEFT_SHOULDER': 0x0100,
    'RIGHT_SHOULDER': 0x0200,
    'A': 0x1000,
    'B': 0x2000,
    'X': 0x4000,
    'Y': 0x8000
}



def build_vjoy_button_mapping(xinput_buttons):
    '''Depends on location of on bit of xinput_buttons.'''
    d = {}
    for (k,v) in xinput_buttons.items():
        counter = 0
        while v != 0:
            v >>= 1
            counter += 1
        d[k] = counter
    return d


vjoy_buttons = build_vjoy_button_mapping(xinput_buttons)
vjoy_id_to_button = {v:k for (k,v) in vjoy_buttons.items()}

vjoy_axisid_to_axislabel = {
    pyvjoy.HID_USAGE_X: 'wAxisX',
    pyvjoy.HID_USAGE_Y: 'wAxisY',
    pyvjoy.HID_USAGE_Z: 'wAxisZ',
    pyvjoy.HID_USAGE_RX: 'wAxisXRot',
    pyvjoy.HID_USAGE_RY: 'wAxisYRot',
    pyvjoy.HID_USAGE_RZ: 'wAxisZRot'
}

# keys based on pyxinput labels
axis_mapping = {
    'thumb_lx': pyvjoy.HID_USAGE_X,
    'thumb_ly': pyvjoy.HID_USAGE_Y,
    'left_trigger': pyvjoy.HID_USAGE_Z,
    'thumb_rx': pyvjoy.HID_USAGE_RX,
    'thumb_ry': pyvjoy.HID_USAGE_RY,
    'right_trigger': pyvjoy.HID_USAGE_RZ
}



# from vjoy SDK

axis_to_int = """
X HID_USAGE_X 0x30
Y HID_USAGE_Y 0x31
Z HID_USAGE_Z 0x32
Rx HID_USAGE_RX 0x33
Ry HID_USAGE_RY 0x34
Rz HID_USAGE_RZ 0x35
Slider0 HID_USAGE_SL0 0x36
Slider1 HID_USAGE_SL1 0x37
Wheel HID_USAGE_WHL 0x38
POV HID_USAGE_POV 0x39
"""





# xinput goes from -32567 to 32567, while vjoy goes from 0 to 32767
AXIS_OFFSET = 0x4000
# xinput triggers go from 0 to 0xff
TRIGGER_SCALE_FACTOR = 0x7fff / 0xff









#########
## FUNCTIONS
#########



def convert_to_vjoy_axis_range(label, value):
    """Convert axis values from xinput to vjoy ranges."""
    if 'trigger' in label:
        return int(TRIGGER_SCALE_FACTOR * value)
    elif 'thumb' in label:
        return ((value//2) + AXIS_OFFSET)

def convert_to_vjoy_buttons(xinput_num, vjoy_mapping = vjoy_buttons, xinput_mapping = xinput_buttons):
    """Given xinput_num and xinput_mapping, return a num representing the corresponding vjoy buttons."""
    
    # first get buttons as list
    unconverted_buttons_list = []
    for (k,v) in xinput_mapping.items():
        if xinput_num & v:
            unconverted_buttons_list.append(k)
            
    # now convert list to vjoy num
    converted_buttons = 0
    for button in unconverted_buttons_list:
        converted_buttons |= (1 << (vjoy_mapping[button]-1))
    
    return converted_buttons
    
    
def xinput_macro_to_vjoy_macro(macro, button_converter = convert_to_vjoy_buttons, axis_converter = convert_to_vjoy_axis_range):
    """Convert states in macro (list of dicts with 'buttons' and 'axes' as keys) into (list of vjoy-compatible data structs).
    
    Does conversion based on passed-in mappings. (Some ID->label mappings outside the function are used.)
    """
    converted = []
    vjoy_struct = None
    
    for state in macro:
        vjoy_struct = pyvjoy._sdk._JOYSTICK_POSITION_V2()
        unconverted_buttons = state.pop('wButtons')
        unconverted_axes = state # rest of the items are axes

        
        # buttons
        converted_buttons = button_converter(unconverted_buttons)
        vjoy_struct.__setattr__('lButtons', converted_buttons)
            
        # axes
        converted_axes = {}
        for (k,v) in unconverted_axes.items():
            converted_axes[vjoy_axisid_to_axislabel[axis_mapping[k]]] = convert_to_vjoy_axis_range(k,v)     
        for (k,v) in converted_axes.items():
            vjoy_struct.__setattr__(k, v)
        
        converted.append(vjoy_struct)
    
    return converted


def record_gamepad_reader(reader, refresh_rate, converter = xinput_macro_to_vjoy_macro):
    """
    Record pyxinput_states from controller refresh_rate times a second until a KeyboardInterrupt is received.
    Returns a dictionary with keys:
    'macro': list of states
    'times': list of timestamps since the recording start corresponding with the list of states
    'Hz': the desired frequency, in Hz, of recording (i.e., refresh_rate)
    
    If converter evaluates to True, the passed-in function is used to convert the states before returning.
    
    Note: Playback conditions must be very close to recording conditions to ensure accuracy.
    That means inconsistent framerates can cause playback desync.
    """
    states = []
    times = []
    wait_time = 1/refresh_rate
    start = _time()
    try:
        while True:
            cur_time = _time()
                # wait until it's time to update
            try:
                time.sleep(target_time + cur_time - _time())
            except ValueError:
                pass

            # now add (processing occurs after the end of recording)
                # takes ~5 us for the following line to complete
            states.append(reader.gamepad), times.append(_time())
    except KeyboardInterrupt:
        pass
    
    # fix times
    times = [(t - start) for t in times]
    
    if converter:
        states = converter(states)
    
    
    return {'states': states, 'times': times, 'Hz': refresh_rate}



def write_gamepad_values(j, state):
    """Given a gamepad (j) and a state, update gamepad."""
    
    j.Data.set_data(state)
    j.update()





def run_macro(j, macro_dict):
    """Run specified macro. Resets controller when done.

    There can be slight variation in repeated playback iterations, 
    but it is unclear whether this is due to imperfections in recording/playback
    or fluctuations in the state of the target program (or its host machine).
    """
    states, times = macro_dict['states'], macro_dict['times']
    
    try:
        start = _time()
        # loop through the states
        for i,target_time in enumerate(times):
                # do all work besides update
            j.Data.set_data(states[i])

                # wait until it's time to update
                # using time.sleep() prevents intense and unnecessary CPU burn (compared to a while-loop wait)
                # but sometimes the argument of time.sleep() is slightly negative (-10E-4 or so)
                # so we have to catch the ValueError
                # thankfully, just ignoring it is generally fine given the time-resolution of what we're doing
                # (it's not like gamepad input is handled at >1kHz)
            try:
                time.sleep(target_time + start - _time())
            except ValueError:
                pass
                # now actually update controller
            j.update()
    except KeyboardInterrupt:
        pass
    finally:
        j.reset()
        return
    

    