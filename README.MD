# XInput PyBot
A bot that can perform simple visual pattern matching and play back gamepad macros, split into:
- `bot_vision`, which implements a `BotView` class, containing some potentially useful functions for more complicated bots.
- `macro_handler`, which contains functionality to record macros from an XInput gamepad, convert them to VJoy-readable states, and play these converted macros back on a VJoy device.
- two instances of bot classes inheriting from the `BotView` class, named `evaluator_bot` (which implements `EvaluatorBot`) and `level_logger` (which implements `LevelLogger`).

And a trivial run script.

[//]: # (I had expected the "computer vision" part would be the most difficult to get going. Turns out my vision problem was fairly trivial to handle with simple template matching using OpenCV. What ended up being the *huge* pain was [1] getting a virtual gamepad's inputs to be read by an emulator.)

## Dependencies
- VJoy 2.1.8 (and perhaps later) (http://vjoystick.sourceforge.net)
- OpenCV (https://opencv.org/)
- For macro recording and playback:
  * PYXInput (used to record manual XInput macros) (https://github.com/bayangan1991/PYXInput)
  * my fork of pyvjoy (allows for synchronous vjoy device update) (https://github.com/dkhachatrian/pyvjoy)
  * XOutput (wraps vjoy device as XInput device) (https://github.com/csutorasa/XOutput) 
