import bot_vision as bv # SeedFinder will inherit from BotView
import os
import pickle

import cv2 # template matching



asset_dir = 'finder'
target_fn = 'good_seed_indicator-min.png'
macro_fn = 'macro_dd-min.p'

with open(os.path.join(asset_dir, macro_fn), mode = 'rb') as f:
	macros_dd = pickle.load(f)

window_class_title = 'PPSSPPWnd'
threshold = 0.99 # 0.95 works for the lvet variant
max_index = 1


class SeedFinder(bv.BotView):
	'''Incredibly simple bot meant to look for one indicator.'''
	def __init__(self, window, macros, threshold = threshold, vjoydevice_num = 1):
		self.num_iter = 0
		self.threshold = threshold
		self.target_template = cv2.imread(os.path.join(asset_dir, target_fn)) # just one template
		super().__init__(window, macros, vjoydevice_num)


	def run_macro(self, macro_label):
		super().run_macro(macro_label)
		if macro_label == 'enter_briefing':
			self.num_iter += 1
			print("\nStarting Iteration #{0}...".format(self.num_iter))

	def find_target(self):
		temp_res = cv2.matchTemplate(self.view, self.target_template, cv2.TM_CCOEFF_NORMED)
		max_val = cv2.minMaxLoc(temp_res)[max_index]
		print("Current view matches target_template with max_val = {0}".format(max_val))
		return cv2.minMaxLoc(temp_res)[max_index] >= threshold

	def run(self):
			while True:
				self.run_macro('advance_rng_seed')
				self.run_macro('enter_briefing')
				self.run_macro('save_state_in_briefing')
				self.run_macro('enter_mission')
				self.update_view()
				if self.find_target():
					resp = input("{0}{1}{2}".format("Desired template found! Confirm that the seed is desirable.\n",
									"If the seed is desirable, type 'y' and I'll try to re-enter on the same seed.\n",
									"Otherwise, type nothing and I'll keep trying other RNG seeds."))
					if resp.lower() == 'y':
						confirmation = ''
						while confirmation != 'y':
							print("Attempting to replicate seed...")
							self.run_macro('enter_briefing')
							confirmation = input("Type 'y' if the seed is still good. Otherwise, I'll try again.\n")
						# good seed, reached briefing
						print("Glad I could help!")
						break
					else:
						print("Continuing to search seeds...")
				else:
					print("Didn't find target template in view. Trying another seed...")
