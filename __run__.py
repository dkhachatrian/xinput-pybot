#! /usr/local/bin/python

# def parse_args(argv):
# 	"""Get arguments in a dictionary."""
# 	opts = {}
# 	while argv:
# 		if argv[0][:2] == '--':
# 			opts[]

if __name__ == '__main__':
	from sys import argv

	if '--evaluator' in argv:
		import evaluator_bot as eb
		bot = eb.EvaluatorBot(window = eb.window_class_title, macros = eb.macros_dd)
		bot.run()

	elif '--logger' in argv:
		import level_logger as lb
		bot = lb.LevelLogger(window = lb.window_class_title, macros = lb.macros_dd)
		bot.run()

	else:
		print("No valid arguments!")