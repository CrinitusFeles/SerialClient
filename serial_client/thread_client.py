from dataclasses import dataclass
from queue import Empty, Queue
from threading import Thread
import time
from event import Event
from serial import Serial
import serial.tools.list_ports
from serial.tools.list_ports_common import ListPortInfo


class ThreadSerialClient:
    def __init__(self, port: str = '') -> None:
        self._ser: Serial
        self.connection_status: bool = False
        self._queue: Queue[bytes] = Queue()
        self._working_flag: bool = True
        self._thread: Thread
        self.received = Event(bytes)
        self._port: str = port

    def connect(self, port: str = '') -> bool:
        if hasattr(self, '_ser') and self._ser.is_open:
            return True
        if port:
            self._port = port
        elif not self._port:
            raise RuntimeError('You need to set serial port!')
        self._ser = Serial(self._port, 921600, parity='E', write_timeout=2)
        self.connection_status = self._ser.is_open
        self._thread = Thread(name='Serial_thread', target=self._routine,
                              daemon=True)
        # self._thread.start()
        return self.connection_status

    def disconnect(self) -> None:
        if hasattr(self, '_ser') and not self._ser.is_open:
            return None
        self._working_flag = False
        self._thread.join(2)
        self.connection_status = False
        self._ser.close()

    def _routine(self):
        self._working_flag = True
        while self._working_flag:
            try:
                tx_data: bytes = self._queue.get_nowait()
                self._ser.write(tx_data)
                # logger.debug(f'TX > {tx_data.hex(" ").upper()}')
                # time.sleep(0.002)
                while self._ser.in_waiting == 0:
                    time.sleep(0.001)
                rx_data: bytes | None = self._ser.read_all()
                if rx_data:
                    self.received.emit(rx_data)
            except Empty:
                # rx_data = self._ser.read_all()
                # if rx_data:
                #     self.received.emit(rx_data)
                ...
                # time.sleep(0.0005)

    def send(self, data: bytes) -> None:
        if self.connection_status:
            self._queue.put_nowait(data)
        else:
            raise ConnectionError('Device is not connected')

    def read_all(self):
        timeout: float = time.time()
        while self._ser.in_waiting == 0:
            time.sleep(0.00001)
            if time.time() - timeout > 0.5:
                print('timeout')
                break
        rx_data: bytes = self._ser.read(self._ser.in_waiting)
        return rx_data


@dataclass
class SerialInfo:
    port: str
    serial_num: str


def get_connected_devices() -> list[SerialInfo]:
    """
    Returns all connected devices with the following format:
    [("PORT", "SERIAL_NUM"), ... ]
    """
    devices_list: list[ListPortInfo] = serial.tools.list_ports.comports()
    if len(devices_list) == 0:  # There is no connected devices
        return []
    return [SerialInfo(device_info.device, device_info.serial_number or '')
            for device_info in devices_list]

if __name__ == '__main__':
    print(get_connected_devices())
