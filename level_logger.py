import bot_vision as bv # build LevelLogger of BotView
import os # open/save files
import re # filtering files by name
import pickle # import macro_dd
import numpy as np
from PIL import Image

import csv # log results to file

import cv2 # template matching (can't just compare directly because of a few animated elements)


threshold = 0.99 # should differentiate separate instances?
hist_dir = 'history'
out_dir = 'outputs'

max_index = 1 # index of max_value for tuple returned by cv2.minMaxLoc()

window_class_title = 'PPSSPPWnd'

key_fmt = 'area_{0}' # to be used in logging
history_file_fmt = '{0}-{1}.bmp' # {0} = key_fmt, {1} = index_num of screenshot

index_finder = re.compile(r'-(\d+)\.')

mistake_indicator = 'macro_mistake'

csv_fp = os.path.join(hist_dir, 'results.csv')

macros_dd = pickle.load(open(os.path.join(hist_dir, "macro_dd.p"), mode = 'rb'))

class LevelLogger(bv.BotView):
	"""
	A bit "dumber" than EvaluatorBot
	Will continually enter the level on different seeds and
	explore the level in order to expose all enemy locations.
	It will compare the current screens with screen it's seen before
	(and will assign the screen a new index if it's new).
	It will log the combinations of screens it sees into a CSV.
	Will keep going until it receives a KeyboardInterrupt.
	"""
	def __init__(self, window, macros, threshold = threshold, vjoy_device_num = 1, hist_dir = hist_dir):
		self.threshold = threshold
		# self.output_dir = output_dir
		self.hist_dir = hist_dir
		self.num_iter = 0
		self.area_keys = [key_fmt.format(n) for n in range(2,6)] #areas 2-5
		self.valid_keyset = set(self.area_keys)
		self.next_area_values = self.init_next_area_values() # "Area X" : (what would be the next unseen area's index)
		self.seen_areas = {}
		self.templates = self.init_templates()
		self.mistake_templates = self.init_mistake_templates()
		self.made_mistake = False
		super().__init__(window, macros, vjoy_device_num)

	def refresh(self):
		""" Prepare for next iteration. """
		self.seen_areas = {} # forget what we've seen
		self.made_mistake = False


	def run_macro(self, macro_label):
		""" Run specified macro dictionary. """
		super().run_macro(macro_label)
		# for fun
		if macro_label == 'advance_rng_seed':
			self.num_iter += 1
			print("\nStarting Iteration #{0}...".format(self.num_iter))



	def init_templates(self):
		"""Load in templates for bot to use."""
		templates = {}
			# get list of filepaths to open with cv2
		hist_files = [os.path.join(self.hist_dir, fn) for fn in os.listdir(self.hist_dir)]
			# load files into memory
		for key in self.valid_keyset:
			cur_fns = [fn for fn in hist_files if key in fn]
			templates[key] = {fn: cv2.imread(fn) for fn in cur_fns}
				# can use key to get to dict of just the relevant templates
				# within each dict, have fn -> cv2 template
		return templates


	def init_mistake_templates(self):
		mistake_files = [os.path.join(self.hist_dir, fn) for fn in os.listdir(self.hist_dir) if mistake_indicator in fn]
		return {fn: cv2.imread(fn) for fn in mistake_files}

	def log_to_csv(self):
		""" Log what the bot has seen into the filepath indicated by csv_fp. """
		while True:
			try:
				with open(csv_fp, mode = 'x', newline = '') as f:
					writer = csv.DictWriter(f, fieldnames = self.area_keys)
					writer.writeheader()
					writer.writerow(self.seen_areas)
				break
			except FileExistsError: # don't (re)write header
				with open(csv_fp, mode = 'a', newline = '') as f:
					writer = csv.DictWriter(f, fieldnames = self.area_keys)
					writer.writerow(self.seen_areas)
				break
			except PermissionError: # CSV is currently open
				input("Output CSV currently open! Close and press Enter to retry.\n")
				continue


	def init_next_area_values(self):
		""" Based on the filenames in hist_dir, determine the next available open index for each key. """
		# count how many contain the keyname; that's the next index
		d = {}
		for key in self.valid_keyset:
			d[key] = len([fn for fn in os.listdir(self.hist_dir) if key in fn])
		return d


	def evaluate_screen(self, key_str):
		"""
		Looks at screen and updates values accordingly.

		If the screen hasn't been seen before (i.e. it doesn't match any templates in hist_dir),
		it adds the screenshot to the directory with a new index and adds it as a new template.
		In any case, self.seen_areas is updated with key_str:index_of_image
		"""
		# first see if our macro messed up
		# (a bit ugly having two nearly identical loops...)
		for (fn, mistake_template) in self.mistake_templates.items():
			temp_res = cv2.matchTemplate(self.view, mistake_template, cv2.TM_CCOEFF_NORMED)
			max_val = cv2.minMaxLoc(temp_res)[max_index]
			if max_val >= self.threshold: # match...
				self.made_mistake = True
				return
		for (fn, template) in self.templates[key_str].items():
			temp_res = cv2.matchTemplate(self.view, template, cv2.TM_CCOEFF_NORMED)
			max_val = cv2.minMaxLoc(temp_res)[max_index]
			if temp_res >= self.threshold: # match!
				index = index_finder.findall(fn)[0] # get index from filename
				self.seen_areas[key_str] = index
				return
		else: # new instance
			cur_max_index = self.next_area_values[key_str]
			fp_newimg = os.path.join(self.hist_dir, history_file_fmt.format(key_str, cur_max_index))
			self.save_view_as_image(fp_newimg) # save image to history for future runs (and visual inspection)
				# save current view as new template directly (without opening newly saved image)
			self.templates[key_str][fp_newimg] = self.view # already in BGR order
			self.seen_areas[key_str] = cur_max_index
			self.next_area_values[key_str] += 1 # update index





	def run(self):
		while True:
			try:
				while True:
					self.run_macro('advance_rng_seed')
					self.run_macro('enter_briefing')
					self.run_macro('enter_mission')

					# explore each area and evaluate area before exploring next
					for x in [5,4,2,3]: # order dependent on how macros were recorded
						key_str = key_fmt.format(x)
						if key_str not in self.valid_keyset:
							raise ValueError("Invalid key_str made! key_str = {0}, \
								self.valid_keyset = {1}".format(key_str, self.valid_keyset))
						self.run_macro('explore_{0}'.format(key_str))
						self.update_view()
						self.evaluate_screen(key_str)
						if self.made_mistake:
							print("Whoops! Macro didn't execute properly. Retrying from start...")
							break
					# out of exploration loop
					if not self.made_mistake:
						self.log_to_csv() # log to file if there wasn't a mistake
					self.refresh() # initialize values for next run (including reseting mistake flag)
					# ...and on we go!
			except KeyboardInterrupt:
				input("{0}{1}".format("Send another KeyboardInterrupt to exit the program.\n",
					"Otherwise, press Enter to continue.\n"))
				continue