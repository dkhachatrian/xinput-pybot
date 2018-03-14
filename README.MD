# XInput PyBot
A bot that can perform simple visual pattern matching and play back XInput gamepad macros, split into:
- `bot_vision`, which (alongside an assets directory) specifies the bot itself, a `BotView` class.
- `macro_handler`, which contains functionality to record macros from an XInput gamepad, convert them to VJoy-readable states, and play them back on a VJoy device.

And a trivial run script.

[//]: # (I had expected the "computer vision" part would be the most difficult to get going. Turns out my vision problem was fairly trivial to handle with simple template matching using OpenCV. What ended up being the *huge* pain was [1] getting a virtual gamepad's inputs to be read by an emulator.)

## Dependencies
- OpenCV (https://opencv.org/)
- my fork of pyvjoy (for macro playback) (https://github.com/dkhachatrian/pyvjoy)
- Desktopmagic (https://pypi.python.org/pypi/Desktopmagic)
- XOutput (https://github.com/csutorasa/XOutput)
- PYXInput (https://github.com/bayangan1991/PYXInput)
