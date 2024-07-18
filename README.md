This repository aims at using the MikroE Dali 2 Click board on a Raspberry Pi for interacting with the Dali bus.

https://www.mikroe.com/dali-2-click


Lots of credits to https://github.com/sjalloq/dali-pigpio for having already figured out lots of things around interacting with a Dali board through GPIO.

This code is far from finished. The dali_monitor seems to work. It consistently picks up telegrams from the bus, and they seem to be formed well.
test_waves allows to broadcast some basic commands to the dali bus. 

hass_dali.py connects to an mqtt broker, and allows Home Assistant to send instructions. 
This is currently limited to ON/OFF/Brightness/Color Temperature.
Please be aware, as my dali lights seem to respond reversed to the color temperature, this is reversed in the code.

Overall, most important, this is primarily a proof of concept. It shows that both reading messages and transmitting messages to the bus is possible through a Raspberry Pi and the Mikroe Dali 2 Click.

