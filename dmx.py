import socket
import struct
import sys
from threading import Thread
from time import sleep
from typing import Union

from animation import Animation, Off, RandomSingle, Steady, FadeTo, RotatingRainbow, Chase, TwoColor, Caramelldansen


def ledlog(value):
    return int(pow(float(value) / 255.0, 2) * 64)


class RGB:
    def __init__(self, dmx, slot, offset=0):
        self.dmx = dmx
        self.slot = slot
        self.offset = offset

    def rgb(self, color):
        (r, g, b) = color
        self.dmx.set(self.slot + self.offset + 0, ledlog(r))
        self.dmx.set(self.slot + self.offset + 1, ledlog(g))
        self.dmx.set(self.slot + self.offset + 2, ledlog(b))


class Bar252(RGB):
    def __init__(self, dmx, slot=1):
        super(Bar252, self).__init__(dmx, slot, 2)
        dmx.set(self.slot + 0, 81)
        dmx.set(self.slot + 1, 0)


class REDSpot18RGB(RGB):
    def __init__(self, dmx, slot=1):
        super(REDSpot18RGB, self).__init__(dmx, slot, 1)
        dmx.set(self.slot + 0, 0)


class StairvilleLedPar56(RGB):
    def __init__(self, dmx, slot=1):
        super(StairvilleLedPar56, self).__init__(dmx, slot, 0)
        dmx.set(self.slot + 3, 0)
        dmx.set(self.slot + 4, 0)
        dmx.set(self.slot + 5, 0)
        dmx.set(self.slot + 6, 255)


class DMX:
    def __init__(self, host, port=0x1936, universe=1, maxchan=512, refresh_rate=30):
        self._host = host
        self._port = port
        self._universe = universe
        self._socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)  # UDP
        self._socket.setblocking(False)
        self._data = bytearray(maxchan)
        packet = bytearray()
        packet.extend(map(ord, "Art-Net"))
        packet.append(0x00)  # Null terminate Art-Net
        packet.extend([0x00, 0x50])  # Opcode ArtDMX 0x5000 (Little endian)
        packet.extend([0x00, 0x0e])  # Protocol version 14
        self._header = packet
        self._sequence = 1
        self._color = (0, 0, 0)
        self._animation = FadeTo((255, 255, 255))
        self._rgbs = []
        self._thread = None
        self._updating = False
        self.refresh_rate = refresh_rate

    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self._thread = Thread(daemon=True, target=self.background)
        self._updating = True
        self._thread.start()

    def background(self):
        while self._updating:
            self.update()
            # print("updating")
            # print(self.data)
            # break
            sleep(1.0 / self.refresh_rate)

    def update(self):
        if not self._animation:
            return

        for i in range(0, len(self._rgbs)):
            self._rgbs[i].rgb(self._animation.update(i, len(self._rgbs)))

        packet = self._header[:]
        packet.append(self._sequence)  # Sequence,
        packet.append(0x00)  # Physical
        packet.append(self._universe & 0xFF)  # Universe LowByte
        packet.append(self._universe >> 8 & 0xFF)  # Universe HighByte

        packet.extend(struct.pack('>h', len(self._data)))  # Pack the number of channels Big endian
        packet.extend(self._data)
        self._socket.sendto(packet, (self._host, self._port))
        # print(f"sent {len(packet)} bytes, {threading.get_native_id()}")

        self._sequence += 1
        if self._sequence > 255:
            self._sequence = 1

    def set(self, slot, value):
        self._data[slot - 1] = value

    @property
    def animation(self) -> str:
        return self._animation.name()

    @animation.setter
    def animation(self, animation: Union[Animation, str]):
        if isinstance(animation, str):
            if animation == "off":
                animation = Off()
            elif animation == "chase":
                animation = Chase(self._color)
            elif animation == "fade":
                animation = FadeTo(self._color)
            elif animation == "rainbow":
                animation = RotatingRainbow()
            elif animation == "steady":
                animation = Steady(self._color)
            elif animation == "twocolor":
                animation = TwoColor(self._color)
            elif animation == "caramelldansen":
                animation = Caramelldansen(self._color)
            elif animation == "randomsingle":
                animation = RandomSingle(self._color)
            else:
                raise ValueError(f"No such animation {animation}")
        self._animation = animation
        if  isinstance(animation, Off):
            self._updating = False
            if self._thread and self._thread.is_alive():
                self._thread.join()
            # one frame black
            self._animation = Steady((0, 0, 0))
            self.update()
            self._animation = Off()
        else:
            self.start()
        print(f"Animation: {animation}", file=sys.stderr)

    @property
    def color(self):
        return self._color

    @color.setter
    def color(self, color):
        if self._color != color:
            self._color = color
            self.animation = self.animation
