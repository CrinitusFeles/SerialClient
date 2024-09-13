# Copyright 2020 Henry Chang
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import array
import asyncio
import concurrent.futures
from typing import Callable, List, Optional, Union
import time
import serial


class AioSerial(serial.Serial):

    def __init__(
            self,
            port: Optional[str] = None,
            baudrate: int = 9600,
            bytesize: int = serial.EIGHTBITS,
            parity: str = serial.PARITY_NONE,
            stopbits: Union[float, int] = serial.STOPBITS_ONE,
            timeout: Optional[Union[float, int]] = None,
            xonxoff: bool = False,
            rtscts: bool = False,
            write_timeout: Optional[Union[float, int]] = None,
            dsrdtr: bool = False,
            inter_byte_timeout: Optional[Union[float, int]] = None,
            exclusive: Optional[bool] = None,
            loop: Optional[asyncio.AbstractEventLoop] = None,
            cancel_read_timeout: int = 1,
            cancel_write_timeout: int = 1,
            **kwargs) -> None:
        super().__init__(
            port=port,
            baudrate=baudrate,
            bytesize=bytesize,
            parity=parity,
            stopbits=stopbits,
            timeout=timeout,
            xonxoff=xonxoff,
            rtscts=rtscts,
            write_timeout=write_timeout,
            dsrdtr=dsrdtr,
            inter_byte_timeout=inter_byte_timeout,
            exclusive=exclusive,
            **kwargs)
        self._loop: Optional[asyncio.AbstractEventLoop] = loop

        self._cancel_read_executor: concurrent.futures.ThreadPoolExecutor = \
            concurrent.futures.ThreadPoolExecutor(max_workers=1)
        self._cancel_read_timeout: int = cancel_read_timeout
        self._read_executor: concurrent.futures.ThreadPoolExecutor = \
            concurrent.futures.ThreadPoolExecutor(max_workers=1)
        self._read_lock: asyncio.Lock = asyncio.Lock()

        self._cancel_write_executor: concurrent.futures.ThreadPoolExecutor = \
            concurrent.futures.ThreadPoolExecutor(max_workers=1)
        self._cancel_write_timeout: int = cancel_write_timeout
        self._write_executor: concurrent.futures.ThreadPoolExecutor = \
            concurrent.futures.ThreadPoolExecutor(max_workers=1)
        self._write_lock: asyncio.Lock = asyncio.Lock()

    @property
    def loop(self) -> Optional[asyncio.AbstractEventLoop]:
        return self._loop if self._loop else asyncio.get_running_loop()

    @loop.setter
    def loop(self, value: Optional[asyncio.AbstractEventLoop]):
        self._loop = value

    async def _cancel_read_async(self):
        if not hasattr(self, 'cancel_read'):
            return
        await asyncio.wait_for(
            asyncio.get_running_loop().run_in_executor(
                self._cancel_read_executor, self.cancel_read),
            self._cancel_read_timeout)

    async def _cancel_write_async(self):
        if not hasattr(self, 'cancel_write'):
            return
        await asyncio.wait_for(
            asyncio.get_running_loop().run_in_executor(
                self._cancel_write_executor, self.cancel_write),
            self._cancel_write_timeout)

    async def read_async(self, size: int = 1) -> bytes:
        async with self._read_lock:
            try:
                return await asyncio.get_running_loop().run_in_executor(
                    self._read_executor, self.read, size)
            except asyncio.CancelledError:
                await asyncio.shield(self._cancel_read_async())
                raise

    async def read_until_async(
            self,
            expected: bytes = serial.LF,
            size: Optional[int] = None) -> bytes:
        async with self._read_lock:
            try:
                return await asyncio.get_running_loop().run_in_executor(
                    self._read_executor, self.read_until, expected, size)
            except asyncio.CancelledError:
                await asyncio.shield(self._cancel_read_async())
                raise

    async def readinto_async(self, b: Union[array.array, bytearray]):
        async with self._read_lock:
            try:
                return await asyncio.get_running_loop().run_in_executor(
                    self._read_executor, self.readinto, b)
            except asyncio.CancelledError:
                await asyncio.shield(self._cancel_read_async())
                raise

    async def readline_async(self, size: int = -1) -> bytes:
        async with self._read_lock:
            try:
                return await asyncio.get_running_loop().run_in_executor(
                    self._read_executor, self.readline, size)
            except asyncio.CancelledError:
                await asyncio.shield(self._cancel_read_async())
                raise

    async def readlines_async(self, hint: int = -1) -> List[bytes]:
        async with self._read_lock:
            try:
                return await asyncio.get_running_loop().run_in_executor(
                    self._read_executor, self.readlines, hint)
            except asyncio.CancelledError:
                await asyncio.shield(self._cancel_read_async())
                raise

    async def write_async(
            self, data: Union[bytearray, bytes, memoryview]) -> int | None:
        async with self._write_lock:
            try:
                return await asyncio.get_running_loop().run_in_executor(
                    self._write_executor, self.write, data)
            except asyncio.CancelledError:
                await asyncio.shield(self._cancel_write_async())
                raise

    async def writelines_async(
            self, lines: List[Union[bytearray, bytes, memoryview]]):
        async with self._write_lock:
            try:
                return await asyncio.get_running_loop().run_in_executor(
                    self._write_executor, self.writelines, lines)
            except asyncio.CancelledError:
                await asyncio.shield(self._cancel_write_async())
                raise

    async def transaction(
            self, data: Union[bytearray, bytes, memoryview],
            validator: Callable[..., bool] | int,
            timeout: float = 0.2) -> bytes:
        async with self._write_lock, self._read_lock:
            try:
                return await asyncio.get_running_loop().run_in_executor(
                    self._write_executor, self._transaction, data, validator,
                    timeout)
            except asyncio.CancelledError:
                await asyncio.shield(self._cancel_write_async())
                raise

    def _wait_timeout(self, timeout: float) -> None:
        start: float = time.time()
        while self.in_waiting == 0:
            if time.time() - start > timeout:
                break

    def _wait_validator(self, validator: Callable[..., bool], rx_data: bytes,
                        timeout: float) -> bytes:
        start: float = time.time()
        while not validator(rx_data):
            self._wait_timeout(timeout)
            rx_data += self.read(self.in_waiting)
            if time.time() - start > timeout:
                raise TimeoutError
        return rx_data

    def _transaction(self, data: Union[bytearray, bytes, memoryview],
                    validator: Callable[..., bool] | int,
                    timeout: float = 0.2) -> bytes:
        self.write(data)
        if isinstance(validator, int):
            return self.read(validator)
        self._wait_timeout(timeout)
        rx_data: bytes = self.read(self.in_waiting)
        result: bytes = self._wait_validator(validator, rx_data, timeout)
        return result
