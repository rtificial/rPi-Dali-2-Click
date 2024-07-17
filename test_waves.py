#!/usr/bin/env python3

import time
import pigpio
import argparse
import atexit

class DaliTransmitter:
    """
    A class to transmit Dali frames.
    """
    def __init__(self, pi, tx_pin, te=417):
        self.pi = pi
        self.tx_pin = tx_pin
        self.te = te
        self.tstop = 2 * te  # Typically stop bit time should be 2 * TE

        self._make_waves()

        self.pi.set_mode(tx_pin, pigpio.OUTPUT)
        self.pi.write(tx_pin, 0)  # Ensure the pin starts high
        self.pi.set_pull_up_down(tx_pin, pigpio.PUD_OFF)

    def _make_waves(self):
        """
        Generate the basic '1' and '0' Manchester encoded waveforms.
        """
        wf = []
        wf.append(pigpio.pulse(1<<self.tx_pin, 0, self.te))
        wf.append(pigpio.pulse(0, 1<<self.tx_pin, self.te))
        self.pi.wave_add_generic(wf)
        self._start = self.pi.wave_create()

        wf = []
        wf.append(pigpio.pulse(0, 1<<self.tx_pin, self.tstop))
        self.pi.wave_add_generic(wf)
        self._stop = self.pi.wave_create()

        wf = []
        wf.append(pigpio.pulse(0, 1<<self.tx_pin, self.te))
        wf.append(pigpio.pulse(1<<self.tx_pin, 0, self.te))
        self.pi.wave_add_generic(wf)
        self._wid0 = self.pi.wave_create()

        wf = []
        wf.append(pigpio.pulse(1<<self.tx_pin, 0, self.te))
        wf.append(pigpio.pulse(0, 1<<self.tx_pin, self.te))
        self.pi.wave_add_generic(wf)
        self._wid1 = self.pi.wave_create()

    def send(self, code, bits=16, repeats=1):
        """
        Transmits a Dali frame.
        """
        print(f"Sending DALI frame: {hex(code)}")

        self.pi.write(self.tx_pin, 1)  # Bring the bus low before starting the transmission
        time.sleep(self.te / 1e6)  # Wait for a half bit time

        chain = [255, 0, self._start]

        bit = (1 << (bits - 1))
        for i in range(bits):
            if code & bit:
                chain += [self._wid1]
                print(f"Sending bit 1 at position {i}")
            else:
                chain += [self._wid0]
                print(f"Sending bit 0 at position {i}")
            bit = bit >> 1

        chain += [self._stop, 255, 1, repeats, 0]

        self.pi.wave_chain(chain)

        while self.pi.wave_tx_busy():
            time.sleep(0.001)

        self.pi.write(self.tx_pin, 0)  # Set the bus high after the transmission
        print("Transmission complete")

    def cancel(self):
        """
        Cancels the Dali transmitter.
        """
        self.pi.wave_delete(self._start)
        self.pi.wave_delete(self._stop)
        self.pi.wave_delete(self._wid0)
        self.pi.wave_delete(self._wid1)

if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument('--host', help='specify the hostname', default='localhost')
    args = parser.parse_args()

    TX_PIN = 5

    pi = pigpio.pi(args.host)
    transmitter = DaliTransmitter(pi, TX_PIN)

    def cleanup():
        transmitter.cancel()
        pi.stop()

    atexit.register(cleanup)

    print("DALI Transmitter is running. Press Ctrl+C to exit.")

    try:
        while True:
            # Send OFF broadcast (0xFE00)
            transmitter.send(0xFE00)
            print("Broadcasted OFF command")

            time.sleep(1)

            # Send MAX brightness broadcast (0xFEFE)
            transmitter.send(0xFEFE)
            print("Broadcasted MAX brightness command")

            time.sleep(1)
    except KeyboardInterrupt:
        print("Exiting...")

    cleanup()
