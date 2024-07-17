#!/usr/bin/env python3

import time
import pigpio
import argparse
import atexit

class DaliTransmitter:
    """
    A class to transmit DALI frames.
    """
    def __init__(self, pi, tx_pin, te=417):
        self.pi = pi
        self.tx_pin = tx_pin
        self.te = te
        self.tstop = 2 * te  # Typically stop bit time should be 2 * TE

        self._make_waves()

        self.pi.set_mode(tx_pin, pigpio.OUTPUT)
        self.pi.write(tx_pin, 0)  # Ensure the pin starts high (idle state for DALI)

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
        Transmits a DALI frame.
        """
        print(f"Sending DALI frame: {hex(code)}")
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

        start_time = time.time()
        self.pi.wave_chain(chain)

        while self.pi.wave_tx_busy():
            time.sleep(0.001)

        self.pi.write(self.tx_pin, 0)  # Set the bus high after the transmission
        end_time = time.time()
        print("Transmission complete")
        print(f"Total transmission time: {(end_time - start_time) * 1e6:.2f} µs")

    def cancel(self):
        """
        Cancels the DALI transmitter.
        """
        self.pi.wave_delete(self._start)
        self.pi.wave_delete(self._stop)
        self.pi.wave_delete(self._wid0)
        self.pi.wave_delete(self._wid1)

def print_menu():
    """
    Prints the command menu.
    """
    print("\nSelect a command to broadcast to the DALI bus:")
    print("1. OFF (0xFE00)")
    print("2. MAX Brightness (0xFEFE)")
    print("3. Set Brightness to 117/254 (0xFE75)")
    print("4. Set Brightness to 37/254 (0xFE25)")
    print("5. TOGGLE (0xFEFF)")
    print("6. Set Color Temperature (Enter Value)")
    print("7. EXIT")

def get_command_choice():
    """
    Prompts the user for a command choice.
    """
    choice = input("Enter your choice (1-7): ")
    return choice

def set_color_temperature(transmitter):
    try:
        temp = int(input("Enter color temperature value (in Kelvin): "))
        mirek = int(1000000 / temp)  # Convert Kelvin to Mirek

        # Break down Mirek into MSB and LSB
        msb = (mirek >> 8) & 0xFF
        lsb = mirek & 0xFF

        # Send commands to set color temperature following the switch sequence
        commands = [
            0xfefe,  # Initial frame (broadcast)
            0xa300 | lsb,  # Set LSB of Mirek
            0xc300,  # Intermediate command
            0xc108,  # Intermediate command
            0xffe7,  # Intermediate command
            0xc108,  # Intermediate command
            0xffe2  # Finalize command
        ]

        for cmd in commands:
            transmitter.send(cmd)
            time.sleep(0.1)  # Small delay between commands

        print(f"Set color temperature to {temp}K (Mirek: {mirek})")
    except ValueError:
        print("Invalid input. Please enter a valid integer.")

def main():
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
            print_menu()
            choice = get_command_choice()

            if choice == '1':
                transmitter.send(0xFE00)
                print("Broadcasted OFF command")
            elif choice == '2':
                transmitter.send(0xFEFE)
                print("Broadcasted MAX Brightness command")
            elif choice == '3':
                transmitter.send(0xFE75)
                print("Broadcasted Brightness 117/254")
            elif choice == '4':
                transmitter.send(0xFE25)
                print("Broadcasted Brightness 37/254")
            elif choice == '5':
                transmitter.send(0xFEFF)
                print("Broadcasted TOGGLE command")
            elif choice == '6':
                set_color_temperature(transmitter)
            elif choice == '7':
                print("Exiting...")
                break
            else:
                print("Invalid choice. Please try again.")

            time.sleep(1)  # Optional: wait 1 second before showing the menu again

    except KeyboardInterrupt:
        print("Exiting...")

    cleanup()

if __name__ == '__main__':
    main()
