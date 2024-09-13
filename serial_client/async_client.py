from dataclasses import dataclass
from typing import Callable, Literal
from serial_client.aioserial import AioSerial
import serial.tools.list_ports
from serial import serialutil
from serial.tools.list_ports_common import ListPortInfo
from loguru import logger


class AioSerialClient:
    def __init__(self, port: str = '', baudrate: int = 115200,
                 parity: Literal['N', 'E', 'O'] = 'N') -> None:
        self._ser: AioSerial
        self.connection_status: bool = False
        self._port: str = port
        self.baudrate: int = baudrate
        self.parity: Literal['N', 'E', 'O'] = parity

    def connect(self, port: str = '') -> bool:
        if hasattr(self, '_ser') and self._ser.is_open:
            return True
        if port:
            self._port = port
        elif not self._port:
            raise RuntimeError('You need to set serial port!')
        try:
            self._ser = AioSerial(self._port, self.baudrate,
                                parity=self.parity,
                                write_timeout=2,
                                timeout=0.1)
            self._ser.flush()
            self.connection_status = self._ser.is_open
        except serialutil.SerialException as err:
            logger.error(err)
            return False
        return self.connection_status

    def disconnect(self) -> None:
        if hasattr(self, '_ser') and not self._ser.is_open:
            return None
        self.connection_status = False
        self._ser.close()

    async def read(self, size: int) -> bytes:
        rx_data: bytes = await self._ser.read_async(size)
        return rx_data

    async def read_all(self) -> bytes:
        self._ser._wait_timeout(0.1)
        rx_data: bytes = await self._ser.read_async(self._ser.in_waiting)
        return rx_data

    async def transaction(self, data: bytes,
                          validator: Callable[..., bool] | int,
                          timeout: float = 0.2) -> bytes:
        return await self._ser.transaction(data, validator, timeout)


    async def send(self, data: bytes) -> None:
        await self._ser.write_async(data)


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
