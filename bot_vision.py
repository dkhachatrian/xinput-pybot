
# coding: utf-8

# Implementation of BotView() with helper functions
# Currently there's a lot of logic hardcoded into BotView() and variables used that are
# specific to the use-case I originally built this for
# It seems difficult task to  generalize this simple bot's logic,
# so I suppose this is more of a "virtual class" defaulting to a particular implementation
#
# As it stands, applying the bot to a new task would involve
# - preparing new templates for state indicators, RNG seed contraindicators, and RNG-seed necessary requirements
# - preparing new macros to load into the bot
# - repurposing BotView.update_current_state(), BotView.evaluate_screen(), BotView.act_on_current_state(),
#       and also BotView.run_macro() and BotView.run() (slightly) to perform the desired macros and update flags properly
#
# It can perform brute-force RNG checks pretty well once set up though!



import win32gui
import win32ui
from ctypes import windll
from PIL import Image
    # take screenshots (even if the window is minimized)
    # and handle them as PIL.Image objects


import sys
    # make printed text more timely by flushing buffer
import numpy as np
    # to flip RGB capture to BGR, for cv2
import pyvjoy
    # give bot a controller (need to wrap with XOutput!)
import macro_handler
    # access to run_macro() method (and all its dependencies)







######
## Functions/Classes
######








def get_screenshot(class_title, just_display = True):
    """
    Take screenshot of a window, even if it's obscured by other windows or is off-screen.
    NOTE: Target window must *not* be minimized.
    Inputs:
        - class_title: the name of the window's class title (*not* the window title).
        - just_display: whether to grab the client window (True); or also grab the menu, window title, etc (False).
    Returns:
        a PIL.Image of the screenshot.
    
    Adapted from https://stackoverflow.com/questions/19695214/python-screenshot-of-inactive-window-printwindow-win32gui

    """
    # Windows spends less resources on the window, making "screenshots" impossible.
    # Potential workaround is explicitly restore a window with zero opacity,
    # but I don't believe this saves much on GPU resources
    # (and dealing with win32 DLLs in Python is kind of a pain -- 
    # the SystemParametersInfo enums seem nonexistent to be able to change the registry values
    # in order to restore/minimize the window "quietly".
    # It appears pywin32 would have access to these enums
    # but we'll go with this for now)



    # class titles (first argument) don't usually change, unlike window titles (the second argument)
    hwnd = win32gui.FindWindow(class_title, None) 

    # get coords
    if just_display:
        left,top,right,bot = win32gui.GetClientRect(hwnd)
    else:
        left, top, right, bot = win32gui.GetWindowRect(hwnd)
    # (without check, we'd have extra black space in our screenshots if we wanted just the display)
    
    # get lengths
    w = right - left
    h = bot - top

    hwndDC = win32gui.GetWindowDC(hwnd) # get the device context ("DC") for window
        # the window device context we get from win32gui is just an int used to pass into WinDLLs
        # (the handle)
        # we need to create our own handle that we can work with
        # using win32ui
    mfcDC = win32ui.CreateDCFromHandle(hwndDC) # type(mfcDC) -> <class 'PyCDC'>
    saveDC = mfcDC.CreateCompatibleDC()
        # making a new context to be a bitmap container
        # should be compatible with the source of the bitmap (hence mfcDC)

    saveBitMap = win32ui.CreateBitmap()
    saveBitMap.CreateCompatibleBitmap(mfcDC, w, h) # take the screenshot, dump into saveBitMap

    saveDC.SelectObject(saveBitMap) # attach context to screenshot


    # Change the line below depending on whether you want the whole window (0)
    # or just the client area, i.e. no top menu, title bar, etc. (1) 
    result = windll.user32.PrintWindow(hwnd, saveDC.GetSafeHdc(), just_display)
    # result = windll.user32.PrintWindow(hwnd, saveDC.GetSafeHdc(), 0)
    # print(result)

    bmpinfo = saveBitMap.GetInfo()
    bmpstr = saveBitMap.GetBitmapBits(True)
        # dump bitmap DC into a str to save into an Image module

    im = Image.frombuffer(
        'RGB',
        (bmpinfo['bmWidth'], bmpinfo['bmHeight']),
        bmpstr, 'raw', 'BGRX', 0, 1)
        # can now edit im (to e.g. crop to only save certain part of image)

    # remove our temporary objects to avoid a memory leak
    win32gui.DeleteObject(saveBitMap.GetHandle())
    # declutter the device contexts (before we lose the information and they stick around for no reason)
    saveDC.DeleteDC()
    mfcDC.DeleteDC()
        # we needed to hold onto the original window in order to perform operations on it (through mfcDC)
        # but now we can let it go
    win32gui.ReleaseDC(hwnd, hwndDC)
    return im





class BotView:
    """Bot that can look at a window, has a vjoy device bound to it, and can perform macros.
    No built-in AI -- need to implement BotView.run() (adding methods, attributes, etc.) in derived classes."""
    def __init__(self, window, macros, vjoy_device_num = 1):
        self.window = window
        self.view = self.update_view()
        self.controller = pyvjoy.VJoyDevice(vjoy_device_num)
        self.macros = macros
    
    def update_view(self):
        """Update the bot's current view of the game."""
        # im = get_screenshot(self.window) # currently RGB PIL Image
#         if debug:
#             im.show()
        # convert to cv2 standard -- i.e., np.ndarray in BGR order
        self.view = np.array(get_screenshot(self.window))[:,:,::-1] # keep x and y coords same, step through the third dimension backward (RGB -> BGR)
            
    def save_view_as_image(self, fpath):
        """Save the bot's current view as a file at fpath.""" 
        im = self._arr_to_im(self.view) # flip from BGR -> RGB
        im.save(fpath)



    def run_macro(self, macro_label):
        """ Run specified macro dictionary. """
        print("Now performing macro: {0} ... ".format(macro_label), end = '')
        sys.stdout.flush() # make sure it prints before the macro starts running
        macro_handler.run_macro(self.controller, self.macros[macro_label])
        print("Done!")
        sys.stdout.flush()


    
    def run(self):
        """Contains AI's routine. Can exit early with a SIG_INTERRUPT (^C)."""
        print("But I don't know what to do! run() still needs to be implemented.")




    def _arr_to_im(self, arr):
        '''Flip BGR to RGB, return as PIL Image.'''
        return Image.fromarray(arr[:,:,::-1])

    def __del__(self):
        del self.controller

