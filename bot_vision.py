
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




from enum import Enum
    # list out the states our bot should recognize
import cv2 
    # used for template matching (gonna save more intense methods for more serious applications)
from desktopmagic import screengrab_win32
    # take screenshots, to compare with template.
    # have to do so externally since emulator window does not seem to take kindly to keypresses
    # (so emulator's built-in and un-button-mappable Screenshot hotkey can't be used)
    #
    # limit screengrab to only relevant region, as template matching will be costly enough as it is
    # desktopmagic (Win32 only) works to screengrab specific regions on a multi-monitor setup
    # IMPORTANT! Must have monitor scaled at 100% (no zoom) for it
    # (or any other screengrab module?) to work as expected
from PIL import Image
    # helps debugging potential screenshot/template issues
import win32gui
    # get bounding box for screengrab
import win32api
    # for alert window popup when a potential seed is found
import os
    # import template files
import sys
    # make printed text more timely by flushing buffer
import numpy as np
    # to flip RGB capture to BGR, for cv2
import re
    # filtering templates by name
import pickle
    # import macro_dd
import pyvjoy
    # give bot a controller (need to wrap with XOutput!)
import macro_handler
    # access to run_macro() method (and all its dependencies)
# import time
#     # to buffer between actions
    


#############
## vars used in bot_vision
#############

window_class_title = "PPSSPPWnd" # class title won't change unlike e. window title
asset_dir = 'assets'


# for popup
alert_str = "The bot might have found a good seed! \nPress RETRY if it was wrong to have it keep searching or CANCEL if it was right to stop the bot."
SIG_RETRY = 4
SIG_STOP = 2



State = Enum("State", "OUTSIDE_MISSION IN_BRIEFING MISSION_START AREA_1 AREA_2 AREA_3 AREA_4 AREA_5 MACRO_MISTAKE")
state_indicator = "marker" # if filename starts with state_indicator, used by bot to determine current state
contraindicator = "bad"
    # if filename contains contraindicator, a match will change bot's state
    # such that BotView.should_start_new_attempt = True

    # if contained in fname, corresponds to matching state
str_to_state = {
    "outside_mission": State.OUTSIDE_MISSION,
    "in_briefing": State.IN_BRIEFING,
    "mission_start": State.MISSION_START,
    "area_1": State.AREA_1,
    "area_2": State.AREA_2,
    "area_3": State.AREA_3,
    "area_4": State.AREA_4,
    "area_5": State.AREA_5,
    "mission_failed": State.MACRO_MISTAKE,
    "macro_mistake": State.MACRO_MISTAKE
    }

state_to_str = {v:k for (k,v) in str_to_state.items()}

max_index = 1 # index of max_value for tuple returned by cv2.minMaxLoc()
current_check_str = "check_{0}" # for logical OR
threshold = 0.90 # these are well-behaved flat images and well-defined matches, so a high threshold works

    # when bot's checked area matches keys, potentially good seed
checked_areas_target = set([State.AREA_3, State.AREA_4, State.AREA_5, State.AREA_2])


debug = False



# macros
macro_dd = pickle.load(open(os.path.join(asset_dir, "macro_dd.p"), mode = 'rb'))






######
## Functions/Classes
######






def make_alert():
    resp = win32api.MessageBox(0, alert_str, 'Script Update', 0x00010005)
    return resp



def get_screenshot(class_title = window_class_title):
    """Given window's class title, return a PIL Image of the window."""
    hwndMain = win32gui.FindWindow(class_title, None)
        # args are className, windowName. Returns int identifier for win32gui
    rect = win32gui.GetWindowRect(hwndMain)
    return screengrab_win32.getRectAsImage(rect)






class BotView:
    # TODO: include a bunch of Get&Set methods if this class will be exposed
    def __init__(self, vjoy_device_num = 1, asset_dir = 'assets', window = window_class_title):
        self.window = window
        self.static_templates = self._generate_static_template_dict(asset_dir)
        self.templates = {k: cv2.imread(v) for (k,v) in self.static_templates.items()}
        self.view = self.update_view()
        self.current_state = State.OUTSIDE_MISSION
#         self.should_act = True
        self.should_pause = False
        self.should_start_new_attempt = False
        self.controller = pyvjoy.VJoyDevice(vjoy_device_num)
        self.macros = macro_dd
#         self.macro_queue = [] # add dicts from macro_dd accordingly
        self.checked_states = []
        self.num_tries = 0
    
    def update_view(self):
        """Update the bot's current view of the game."""
        im = get_screenshot(self.window) # currently RGB PIL Image
#         if debug:
#             im.show()
        # convert to cv2 standard -- i.e., np.ndarray in BGR order
        self.view = np.array(im)[:,:,::-1] # keep x and y coords same, step through the third dimension backward (RGB -> BGR)
            

    
    def update_current_state(self):
        """Figure out current state as enumerated in State."""
        results = {}
        candidates = {k:self.templates[k] for k in self.static_templates if k.startswith(state_indicator)}
            # only looking to determine state right now
        for (k,v) in candidates.items():
            temp_res = cv2.matchTemplate(self.view, v, cv2.TM_CCOEFF_NORMED)
            results[cv2.minMaxLoc(temp_res)[max_index]] = k # maxval -> fname

        most_probable_state_fname = results[max(results.keys())]

        for k in str_to_state.keys():
            if k in most_probable_state_fname:
                if debug:
                    Image.open(self.static_templates[most_probable_state_fname]).show()
                self.current_state = str_to_state[k]
                print("Now in {0}.".format(self.current_state))
                return
        else: # shouldn't ever happen
            raise ValueError("Did not find a matching state!\n \
                k = {0}, most_probable_state_fname = {1}".format(k, most_probable_state_fname))
    
    
    def evaluate_screen(self, threshold = threshold):
        '''
        Inspect screen based on bot's current state.
        Updates attributes with whether to start a new attempt based on scans.
        '''

        # if we're in a weird screen, can just retry
        if self.current_state == State.MACRO_MISTAKE:
            self.should_start_new_attempt = True
            return


        # first look only at templates of interests
        templates = {k:self.templates[k] for k in self.static_templates if state_to_str[self.current_state] in k and state_indicator not in k}
        contraindicators = {}
        # separate contraindicators from positive examples
        for k in list(templates.keys()):
            if contraindicator in k:
                contraindicators[k] = templates.pop(k)
        
        # first check to see if there's an immediate dealbreaker
        for (k,v) in contraindicators.items():
            temp_res = cv2.matchTemplate(self.view, v, cv2.TM_CCOEFF_NORMED)
            if cv2.minMaxLoc(temp_res)[max_index] >= threshold:
                self.should_start_new_attempt = True
                print("Found the following contraindicator: {0}.".format(k))
                return
        
        # now ensure we have the positive matches we need
        check_num = 0
        while True:
            check_num += 1
            current_template_keys = [k for k in templates.keys() if current_check_str.format(check_num) in k]
            if len(current_template_keys) == 0:
                break # gone through all checks for given area
            for k in current_template_keys:
                temp_res = cv2.matchTemplate(self.view, templates.pop(k), cv2.TM_CCOEFF_NORMED)
                if cv2.minMaxLoc(temp_res)[max_index] >= threshold:
                    break # at least one of the mutually exclusive options is satisfied for this check_num
            else: # python --> no need for separate loop flags
                print("Couldn't find a positive instance of Check #{0} in {1}.".format(check_num, self.current_state))
                self.should_start_new_attempt = True # none of the mutually exclusive options were found
                return
        
        # if we've made it here, then nothing about this screen implies a new attempt
        # leave unchanged
        print("{0} looks OK to me.".format(self.current_state))
        return
        

    def act_on_current_state(self):
        """Based on self.current_state, evaluate screen (as good or bad), and/or perform relevant macros."""
        
        # evaluate and determine whether to retry

        # states requiring extra care
        if self.current_state == State.AREA_2 \
                or self.current_state == State.AREA_3:
                # need to scroll up before evaluating screen
            self.run_macro('command_mode_scroll_up')
        

        self.evaluate_screen() # updates should_start_new_attempt flag



        # should reset?
        if self.should_start_new_attempt:
            self.checked_states = []
            self.should_start_new_attempt = False
            self.run_macro('advance_rng_seed')
            return


        if self.current_state == State.OUTSIDE_MISSION:
            self.run_macro('enter_mission_and_explore_(3x_speed)')
            return






        self.checked_states.append(self.current_state)

        # have we checked all the target areas? Change flag if so
        if set(self.checked_states).issuperset(checked_areas_target):
            self.should_pause = True
            return
        
        # if still here, need to go to the next screen
        self.run_macro('command_mode_next_area')
    

    def run_macro(self, macro_label):
        """ Run specified macro dictionary. """
        print("Now performing macro: {0} ... ".format(macro_label), end = '')
        sys.stdout.flush() # make sure it prints before the macro starts running
        macro_handler.run_macro(self.controller, self.macros[macro_label])
        print("Done!")
        # for fun
        if macro_label == 'advance_rng_seed':
            self.num_tries += 1
            print("\nStarting Attempt #{0}...".format(self.num_tries))

    
    def run(self):
        """Contains AI's routine. Can exit early with a SIG_INTERRUPT (^C)."""
        while True:
            # first start a new seed
            self.run_macro('advance_rng_seed')

            try: # core loop
                while not self.should_pause:
                    self.update_view()
                    self.update_current_state()
                    self.act_on_current_state()
                # if out of loop, should pause and notify user
                sig = make_alert()
                if sig == SIG_RETRY:
                    self.should_pause = False
                    print("Continuing search...")
                    continue
                elif sig == SIG_STOP:
                    RESP_OK = 'y'
                    while True:
                        print("Alright, let me try to reproduce the seed...")
                        self.run_macro('enter_mission_(3x_speed)')
                        resp = input("Is it the same seed? Type '{0}' if so; otherwise I'll try again.\n".format(RESP_OK))
                        if resp.lower() == RESP_OK:
                            print("Great, glad I could help!")
                            break
                    break
            except KeyboardInterrupt: #SIGINT, ^C
                resp = input("{0}{1}".format("Type anything and press Enter to recontinue.\n",
                    "Otherwise, type nothing and press Enter to exit the program.\n"))
                if resp == '':
                    break



        
    def _generate_static_template_dict(self, asset_dir):
        """filename -> relative path. Does not look in any subdirectories."""
        d = {}
#         for root, dirs, files in os.walk(asset_dir):
        for f in os.listdir(asset_dir):
            d[f] = os.path.join(asset_dir, f)
        return d

    def _arr_to_im(self, arr):
        '''Flip BGR to RGB, return as PIL Image.'''
        return Image.fromarray(arr[:,:,::-1])

    def __del__(self):
        del self.controller

