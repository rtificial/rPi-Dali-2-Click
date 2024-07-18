import time
import pigpio
import paho.mqtt.client as mqtt
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

def on_connect(client, userdata, flags, rc, properties=None):
    print("Connected to MQTT broker with result code " + str(rc))
    client.subscribe("homeassistant/light/dali_light/set")
    client.subscribe("homeassistant/light/dali_light/brightness/set")
    client.subscribe("homeassistant/light/dali_light/color_temperature/set")

def on_message(client, userdata, msg):
    print(f"Received message on topic {msg.topic} with payload {msg.payload}")
    payload = msg.payload.decode()

    if msg.topic == "homeassistant/light/dali_light/set":
        if payload == "ON":
            if userdata["state"] == "OFF":
                userdata["transmitter"].send(0xFEFE)
                userdata["state"] = "ON"
                client.publish("homeassistant/light/dali_light/state", "ON", retain=True)
        elif payload == "OFF":
            userdata["transmitter"].send(0xFE00)
            userdata["state"] = "OFF"
            client.publish("homeassistant/light/dali_light/state", "OFF", retain=True)

    elif msg.topic == "homeassistant/light/dali_light/brightness/set":
        target_brightness = int(payload)
        current_brightness = userdata.get("current_brightness", 0)
        step_delay = 0.01  # Faster delay between each step in seconds
        step_size = 1 if target_brightness > current_brightness else -1

        for brightness in range(current_brightness, target_brightness, step_size):
            command = 0xFE00 | brightness
            userdata["transmitter"].send(command)
            time.sleep(step_delay)

        userdata["current_brightness"] = target_brightness
        # Send the final brightness value
        command = 0xFE00 | target_brightness
        userdata["transmitter"].send(command)
        client.publish("homeassistant/light/dali_light/brightness", payload, retain=True)

    elif msg.topic == "homeassistant/light/dali_light/color_temperature/set":
        mired = int(payload)
        mired = max(154, min(500, mired))  # Ensure Mired is within DALI range
        reversed_mired = 500 - (mired - 154)  # Reverse the Mired value
        msb = reversed_mired // 256
        lsb = reversed_mired % 256
        commands = [
            0xfefe,  # Initial frame (broadcast)
            0xa300 | lsb,  # Set LSB of Mired
            0xc300 | msb,  # Set MSB of Mired
            0xc108,  # Intermediate command
            0xffe7,  # Intermediate command
            0xc108,  # Intermediate command
            0xffe2  # Finalize command
        ]
        for cmd in commands:
            userdata["transmitter"].send(cmd)
            time.sleep(0.1)
        client.publish("homeassistant/light/dali_light/color_temperature", payload, retain=True)

def main():
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

    mqtt_client = mqtt.Client(client_id="dali_controller", userdata={"transmitter": transmitter, "current_brightness": 0, "state": "OFF"}, protocol=mqtt.MQTTv5)
    mqtt_client.on_connect = on_connect
    mqtt_client.on_message = on_message

    mqtt_broker_address = "localhost"  # Replace with your MQTT broker address
    mqtt_client.connect(mqtt_broker_address, 1883, 60)

    mqtt_client.loop_start()

    print("DALI Transmitter with MQTT is running. Press Ctrl+C to exit.")
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("Exiting...")

    mqtt_client.loop_stop()
    cleanup()

if __name__ == '__main__':
    main()
