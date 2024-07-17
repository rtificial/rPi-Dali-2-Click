#!/usr/bin/env python3

import time
import pigpio
import argparse
import atexit

class rx():
    """
    A class to read a Dali frame.
    """

    TE      = 834 / 2  # half bit time = 417 usec
    MIN_TE  = 350
    MAX_TE  = 490
    MIN_2TE = 760
    MAX_2TE = 900
    STP_2TE = 1800

    def __init__(self, pi, gpio, callback=None, glitch=150):
        """
        User must pass in the pigpio.pi object, the gpio number to use as the receive pin
        and a callback method to be called on every received frame.
        """
        self.pi     = pi
        self.gpio   = gpio
        self.cb     = callback
        self.glitch = glitch

        self._in_code       = 0
        self._edges         = 0
        self._code          = 0
        self._prev_edge_len = 0
        self._timestamps    = []
        
        pi.set_mode(gpio, pigpio.INPUT)
        pi.set_glitch_filter(gpio, glitch)

        self._last_edge_tick = pi.get_current_tick()
        self._cb = pi.callback(gpio, pigpio.EITHER_EDGE, self._cbe)

    def cancel(self):
        """
        Called on program exit to cleanup.
        """
        if self._cb is not None:
            self.pi.set_glitch_filter(self.gpio, 0)  # Remove glitch filter.
            self.pi.set_watchdog(self.gpio, 0)  # Cancel the watchdog
            self._cb.cancel()
            self._cb = None

    def _wdog(self, milliseconds):
        """
        Starts a watchdog timer on the RX pin that fires after waiting for
        the defined number of microseconds.

        The watchdog can be cancelled before it has fired by calling this
        method with a value of 0.
        """
        self.pi.set_watchdog(self.gpio, milliseconds)

    def stop(self):
        """
        Called at the end of a received frame after the stop bits have been
        detected. The user callback is called with the received frame as a
        parameter.
        """
        frame = self._code
        timestamps = self._timestamps
        self._edges = 0
        self._code = 0
        self._in_code = 0
        if self.cb is not None:
            self.cb(frame, timestamps)

    def _decode(self, high_time, low_time):
        """
        Called on every rising edge of the Dali bus, this method decodes
        the bits received since the last call.
        """
        action = self._prev << 2
        
        if high_time > self.MIN_2TE and high_time < self.MAX_2TE:
            action = action | 1
        elif not (high_time > self.MIN_TE and high_time < self.MAX_TE):
            self._in_code = 0
            pass

        if low_time > self.MIN_2TE and low_time < self.MAX_2TE:
            action = action | 2
        elif not (low_time > self.MIN_TE and low_time < self.MAX_TE):
            self._in_code = 0
            pass

        self._code = self._code << 1
                
        if action in [1, 3, 6]:
            self._in_code = 0
            pass
        else:
            if action in [2, 7]:
                self._code = self._code << 1
                self._code += 1
                self._prev = 1
            else:
                if action == 4:
                    self._code += 1
                    self._prev = 1
                else:
                    self._prev = 0

    def _cbe(self, gpio, level, tick):
        """
        Called on either rising or falling edge of the gpio, the time
        since the last edge is recorded and a pair of values are passed
        to the decode method on each rising edge. A 2 millisecond 
        watchdog is used to signal the end of the frame.
        """
        # Disable the watchdog
        self._wdog(0)
            
        if level < 2:
            # Received an edge interrupt
            
            # Calculate the edge length
            edge_len = pigpio.tickDiff(self._last_edge_tick, tick)
            self._last_edge_tick = tick
        
            if self._in_code == 0:
                self._timestamps = []

            if self._edges < 2:
                # Start bit
                self._prev = 1
            else:
                if self._edges % 2:
                    # Rising edge; decode the low/high time
                    self._decode(self._prev_edge_len, edge_len)
                else:
                    # Falling edge; capture the high time
                    self._prev_edge_len = edge_len
            self._edges += 1

            # Capture the tick times for debug
            self._timestamps.append({'level': level, 
                                     'tick': tick,
                                     'len': edge_len,
                                     'bits': self._edges})

            # Set the watchdog to a time equivalent to 2 stop bits
            self._wdog(2)
        else:
            # Received watchdog timeout so end of frame
            self.stop()


if __name__ == '__main__':

    import argparse

    def callback(frame, timestamps):
        print('Dali frame = %s' % hex(frame))
        print('Timestamps:', timestamps)
        for ts in timestamps:
            print(f"Level: {ts['level']}, Tick: {ts['tick']}, Length: {ts['len']}, Bits: {ts['bits']}")

    parser = argparse.ArgumentParser()
    parser.add_argument('--host', help='specify the hostname', default='localhost')
    args = parser.parse_args()

    RX_PIN = 6

    pi = pigpio.pi(args.host)
    rx = rx(pi, RX_PIN, callback)

    def cleanup():
        rx.cancel()
        pi.stop()

    atexit.register(cleanup)

    print("DALI Monitor is running. Press Ctrl+C to exit.")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("Exiting...")

    cleanup()
