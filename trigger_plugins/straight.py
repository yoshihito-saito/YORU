import time

import serial
import serial.tools.list_ports


class trigger_condition:
    def __init__(self, m_dict, rate=9600):
        print("trigger_command")

        self.quit = False
        comport = m_dict.get("arduino_com")
        self.ser = serial.Serial(comport, rate,
                                 timeout=0.1,
                                 parity=serial.PARITY_NONE)
        self.last_sent = None
        self.trigger_class = m_dict.get("trigger_class", "")
        print(f"Opened serial port {comport} at {rate} baud")

    def trigger(self, tri_cl, in_cl, arduino, results, now):
        if tri_cl in in_cl:
            if self.last_sent != "1":
                print(f"{self.trigger_class} detected")
                print("Sending serial command: 1")
            self.ser.write(b"1")
            self.last_sent = "1"
        else:
            if self.last_sent != "0":
                print(f"No {self.trigger_class} detected")
                print("Sending serial command: 0")
            self.ser.write(b"0")
            self.last_sent = "0"

    def close(self):
        if self.ser and self.ser.is_open:
            self.ser.close()
            print("Closed serial port")
