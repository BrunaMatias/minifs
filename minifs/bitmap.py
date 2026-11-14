"""Bitmap de blocos: 1 bit por bloco do disco, 1 = ocupado e 0 = livre.

Alocação first-fit a partir de data_start; toda alteração é gravada imediatamente.
"""

from __future__ import annotations

from typing import Iterable, Iterator, List, Optional

from .disk import VirtualDisk
from .errors import (
    BlockAlreadyFreeError,
    BlockOutOfRangeError,
    DiskFullError,
    InvalidDiskError,
    InvalidParameterError,
)
from .layout import Layout


class Bitmap:
    def __init__(self, disk: VirtualDisk, layout: Layout, data: bytearray) -> None:
        self._disk = disk
        self._layout = layout
        self._bits = data
        self._free = self._count_free_data()

    @classmethod
    def create(cls, disk: VirtualDisk, layout: Layout) -> "Bitmap":
        """Bitmap inicial com metadados e bits excedentes marcados como ocupados."""
        data = bytearray(layout.bitmap_blocks * layout.block_size)
        for block in range(layout.metadata_blocks):
            _set(data, block)
        for bit in range(layout.total_blocks, len(data) * 8):
            _set(data, bit)
        bitmap = cls(disk, layout, data)
        bitmap.flush_all()
        return bitmap

    @classmethod
    def load(cls, disk: VirtualDisk, layout: Layout) -> "Bitmap":
        """Lê o bitmap do disco e verifica se os metadados estão marcados como ocupados."""
        data = bytearray(disk.read_blocks(layout.bitmap_start, layout.bitmap_blocks))
        for block in range(layout.metadata_blocks):
            if not _get(data, block):
                raise InvalidDiskError(
                    f"bitmap corrompido: bloco de metadados {block} marcado como livre"
                )
        return cls(disk, layout, data)

    def is_used(self, block: int) -> bool:
        self._layout.check_block(block)
        return _get(self._bits, block)

    def is_free(self, block: int) -> bool:
        return not self.is_used(block)

    def free_count(self) -> int:
        """Quantidade de blocos de dados livres."""
        return self._free

    def used_data_count(self) -> int:
        return self._layout.data_blocks - self._free

    def used_data_blocks(self) -> Iterator[int]:
        for block in range(self._layout.data_start, self._layout.total_blocks):
            if _get(self._bits, block):
                yield block

    def allocate(self, count: int = 1) -> List[int]:
        """Reserva count blocos de dados livres e retorna seus números.

        Lança DiskFullError sem alterar o bitmap se não houver blocos suficientes.
        """
        if isinstance(count, bool) or not isinstance(count, int) or count < 0:
            raise InvalidParameterError(f"quantidade de blocos inválida: {count!r}")
        if count == 0:
            return []
        if count > self._free:
            raise DiskFullError(
                f"disco cheio: {count} bloco(s) solicitado(s), {self._free} livre(s)"
            )

        chosen: List[int] = []
        lo = self._layout
        bits = self._bits
        block = lo.data_start
        while len(chosen) < count and block < lo.total_blocks:
            byte = bits[block >> 3]
            # Byte alinhado com os 8 blocos ocupados é ignorado de uma vez.
            if byte == 0xFF and block & 7 == 0:
                block += 8
                continue
            if not byte & (1 << (block & 7)):
                chosen.append(block)
            block += 1

        if len(chosen) < count:
            raise InvalidDiskError("contador de blocos livres inconsistente com o bitmap")

        for b in chosen:
            _set(bits, b)
        self._free -= count
        self._flush(chosen)
        return chosen

    def free(self, blocks: Iterable[int]) -> None:
        """Libera blocos de dados; valida todos antes de alterar qualquer bit."""
        blocks = list(blocks)
        lo = self._layout
        seen = set()
        for b in blocks:
            lo.check_block(b)
            if not lo.is_data_block(b):
                raise BlockOutOfRangeError(
                    f"bloco {b} pertence à região '{lo.region_of(b)}' e não pode ser liberado"
                )
            if b in seen or not _get(self._bits, b):
                raise BlockAlreadyFreeError(f"bloco {b} já está livre")
            seen.add(b)

        for b in blocks:
            _clear(self._bits, b)
        self._free += len(blocks)
        self._flush(blocks)

    def flush_all(self) -> None:
        self._disk.write_blocks(self._layout.bitmap_start, bytes(self._bits))

    def _flush(self, changed: Iterable[int]) -> None:
        """Regrava apenas os blocos do bitmap que contêm bits alterados."""
        bs = self._layout.block_size
        for idx in sorted({(b >> 3) // bs for b in changed}):
            self._disk.write_block(self._layout.bitmap_start + idx,
                                   bytes(self._bits[idx * bs:(idx + 1) * bs]))

    def render(self, start: int = 0, end: Optional[int] = None, width: int = 64) -> str:
        """Mapa textual: S superblock, B bitmap, I inodes, # dado ocupado, . livre."""
        lo = self._layout
        end = lo.total_blocks if end is None else min(end, lo.total_blocks)
        symbol = {"superblock": "S", "bitmap": "B", "inodes": "I"}
        lines = []
        for row in range(start, end, width):
            cells = []
            for b in range(row, min(row + width, end)):
                region = lo.region_of(b)
                cells.append(symbol.get(region) or ("#" if _get(self._bits, b) else "."))
            lines.append(f"{row:>7} {''.join(cells)}")
        return "\n".join(lines)

    def _count_free_data(self) -> int:
        bits = self._bits
        return sum(1 for b in range(self._layout.data_start, self._layout.total_blocks)
                   if not _get(bits, b))


def _get(data: bytearray, bit: int) -> bool:
    return bool(data[bit >> 3] & (1 << (bit & 7)))


def _set(data: bytearray, bit: int) -> None:
    data[bit >> 3] |= 1 << (bit & 7)


def _clear(data: bytearray, bit: int) -> None:
    data[bit >> 3] &= ~(1 << (bit & 7)) & 0xFF
