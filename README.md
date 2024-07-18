This repository aims at using the MikroE Dali 2 Click board on a Raspberry Pi for interacting with the Dali bus.

https://www.mikroe.com/dali-2-click


Lots of credits to https://github.com/sjalloq/dali-pigpio for having already figured out lots of things around interacting with a Dali board through GPIO.

This code is far from finished. The dali_monitor seems to work. It consistently picks up telegrams from the bus, and they seem to be formed well.
test_waves allows to broadcast some basic commands to the dali bus. 

The end goal is to allow control the Dali bus for setting the light temperature following the circadian rhythm using Home Assistant. 
