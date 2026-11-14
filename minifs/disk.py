"""Disco virtual: arquivo binário do hospedeiro acessado em blocos de tamanho fixo.

É a única camada que lê ou escreve o arquivo da imagem.
"""

from __future__ import annotations

import os
from typing import Optional

from .errors import (
    BlockOutOfRangeError,
    DiskClosedError,
    DiskNotFoundError,
    InvalidDiskError,
    InvalidParameterError,
)

_ZERO_CHUNK = 1 << 20


class VirtualDisk:
    """Arquivo hospedeiro visto como um vetor de total_blocks blocos."""

    def __init__(self, path: str, block_size: int, total_blocks: int, handle) -> None:
        self.path = path
        self.block_size = block_size
        self.total_blocks = total_blocks
        self._fh = handle
        self.reads = 0
        self.writes = 0

    @classmethod
    def create(cls, path: str, total_blocks: int, block_size: int) -> "VirtualDisk":
        """Cria ou recria o arquivo do disco com todos os bytes zerados."""
        if total_blocks <= 0 or block_size <= 0:
            raise InvalidParameterError("total_blocks e block_size devem ser positivos")
        size = total_blocks * block_size
        fh = open(path, "w+b")
        try:
            remaining = size
            zeros = bytes(min(_ZERO_CHUNK, size))
            while remaining > 0:
                n = min(remaining, len(zeros))
                fh.write(zeros[:n])
                remaining -= n
            fh.flush()
            os.fsync(fh.fileno())
        except BaseException:
            fh.close()
            raise
        return cls(path, block_size, total_blocks, fh)

    @classmethod
    def open(cls, path: str, block_size: int, total_blocks: int) -> "VirtualDisk":
        """Abre um disco existente e confere se o tamanho do arquivo é o esperado."""
        if not os.path.isfile(path):
            raise DiskNotFoundError(f"disco '{path}' não encontrado; execute 'format'")
        expected = total_blocks * block_size
        actual = os.path.getsize(path)
        if actual != expected:
            raise InvalidDiskError(
                f"tamanho do arquivo ({actual} B) difere do registrado no "
                f"superblock ({total_blocks} x {block_size} = {expected} B)"
            )
        return cls(path, block_size, total_blocks, open(path, "r+b"))

    @staticmethod
    def read_header(path: str, size: int) -> bytes:
        """Lê os primeiros bytes do arquivo, antes de o tamanho de bloco ser conhecido."""
        if not os.path.isfile(path):
            raise DiskNotFoundError(f"disco '{path}' não encontrado; execute 'format'")
        with open(path, "rb") as fh:
            return fh.read(size)

    def read_block(self, block: int) -> bytes:
        """Retorna exatamente block_size bytes do bloco informado."""
        fh = self._handle()
        self._check(block)
        fh.seek(block * self.block_size)
        data = fh.read(self.block_size)
        if len(data) != self.block_size:
            raise InvalidDiskError(f"leitura incompleta do bloco {block}")
        self.reads += 1
        return data

    def write_block(self, block: int, data: bytes) -> None:
        """Grava data no bloco, completando com zeros se for menor que o bloco."""
        fh = self._handle()
        self._check(block)
        if len(data) > self.block_size:
            raise InvalidParameterError(
                f"{len(data)} bytes não cabem em um bloco de {self.block_size} B"
            )
        if len(data) < self.block_size:
            data = bytes(data) + bytes(self.block_size - len(data))
        fh.seek(block * self.block_size)
        fh.write(data)
        fh.flush()
        self.writes += 1

    def read_blocks(self, start: int, count: int) -> bytes:
        return b"".join(self.read_block(start + i) for i in range(count))

    def write_blocks(self, start: int, data: bytes) -> None:
        bs = self.block_size
        for i in range(0, max(len(data), 1), bs):
            self.write_block(start + i // bs, data[i:i + bs])

    @property
    def closed(self) -> bool:
        return self._fh is None

    def sync(self) -> None:
        """Força a gravação física de tudo o que foi escrito."""
        fh = self._handle()
        fh.flush()
        os.fsync(fh.fileno())

    def close(self) -> None:
        if self._fh is not None:
            try:
                self.sync()
            finally:
                self._fh.close()
                self._fh = None

    def __enter__(self) -> "VirtualDisk":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    def _handle(self):
        if self._fh is None:
            raise DiskClosedError("o disco virtual já foi fechado")
        return self._fh

    def _check(self, block: Optional[int]) -> None:
        if isinstance(block, bool) or not isinstance(block, int) \
                or not 0 <= block < self.total_blocks:
            raise BlockOutOfRangeError(
                f"bloco {block} fora do disco (válidos: 0..{self.total_blocks - 1})"
            )
