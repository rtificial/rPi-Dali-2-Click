This repository aims at using the MikroE Dali 2 Click board on a Raspberry Pi for interacting with the Dali bus.

Lots of credits to https://github.com/sjalloq/dali-pigpio for having already figured out lots of things around interacting with a Dali board through GPIO.

This code is far from finished. The dali_monitor seems to work. It consistently picks up telegrams from the bus, and they seem to be formed well.
test_waves is designed to broadcast a simple OFF and MAX_LEVEL command in a telegram, however, these don't seem to be properly shaped as yet.