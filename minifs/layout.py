"""Constantes do formato em disco e cálculo das regiões do disco virtual.

Especificação completa em docs/LAYOUT_DISCO.md.
"""

from __future__ import annotations

import math
import struct
from dataclasses import dataclass
from typing import Tuple

from .errors import BlockOutOfRangeError, InvalidParameterError

MAGIC = b"MINIFS01"
VERSION = 1

DEFAULT_BLOCK_SIZE = 512
VALID_BLOCK_SIZES = (512, 1024, 2048, 4096)

DEFAULT_INODE_COUNT = 64
MIN_INODE_COUNT = 1
MAX_INODE_COUNT = 4096

MAX_TOTAL_BLOCKS = 1 << 20

SUPERBLOCK_BLOCK = 0
BITMAP_START = 1

# Registro de arquivo: used, file_id, size, n_blocks, name[32], blocks[20].
INODE_SIZE = 128
MAX_NAME_LEN = 32
DIRECT_REFS = 20
INODE_FORMAT = "<B3xIIH2x32s20I"
assert struct.calcsize(INODE_FORMAT) == INODE_SIZE


@dataclass(frozen=True)
class Layout:
    """Posição de cada região do disco, em números de bloco."""

    block_size: int
    total_blocks: int
    inode_count: int
    bitmap_start: int
    bitmap_blocks: int
    inode_table_start: int
    inode_table_blocks: int
    data_start: int

    @property
    def metadata_blocks(self) -> int:
        """Blocos reservados para superblock, bitmap e tabela de inodes."""
        return self.data_start

    @property
    def data_blocks(self) -> int:
        return self.total_blocks - self.data_start

    @property
    def disk_size(self) -> int:
        return self.total_blocks * self.block_size

    @property
    def inodes_per_block(self) -> int:
        return self.block_size // INODE_SIZE

    @property
    def max_file_size(self) -> int:
        return DIRECT_REFS * self.block_size

    def region_of(self, block: int) -> str:
        """Nome da região a que o bloco pertence."""
        self.check_block(block)
        if block == SUPERBLOCK_BLOCK:
            return "superblock"
        if block < self.inode_table_start:
            return "bitmap"
        if block < self.data_start:
            return "inodes"
        return "dados"

    def is_data_block(self, block: int) -> bool:
        return self.data_start <= block < self.total_blocks

    def check_block(self, block: int) -> None:
        if not isinstance(block, int) or not 0 <= block < self.total_blocks:
            raise BlockOutOfRangeError(
                f"bloco {block} fora do disco (válidos: 0..{self.total_blocks - 1})"
            )

    def inode_location(self, index: int) -> Tuple[int, int]:
        """Retorna (bloco, deslocamento em bytes) do inode na tabela."""
        if not 0 <= index < self.inode_count:
            raise InvalidParameterError(
                f"inode {index} inexistente (válidos: 0..{self.inode_count - 1})"
            )
        block = self.inode_table_start + index // self.inodes_per_block
        offset = (index % self.inodes_per_block) * INODE_SIZE
        return block, offset


def compute_layout(
    total_blocks: int,
    block_size: int = DEFAULT_BLOCK_SIZE,
    inode_count: int = DEFAULT_INODE_COUNT,
) -> Layout:
    """Valida os parâmetros do format e calcula as regiões do disco."""
    for name, value in (("total_blocks", total_blocks), ("block_size", block_size),
                        ("inode_count", inode_count)):
        if isinstance(value, bool) or not isinstance(value, int):
            raise InvalidParameterError(f"{name} deve ser inteiro (recebido {value!r})")

    if block_size not in VALID_BLOCK_SIZES:
        raise InvalidParameterError(
            f"tamanho de bloco {block_size} não suportado "
            f"(use um de {', '.join(map(str, VALID_BLOCK_SIZES))})"
        )
    if not MIN_INODE_COUNT <= inode_count <= MAX_INODE_COUNT:
        raise InvalidParameterError(
            f"número de inodes deve estar entre {MIN_INODE_COUNT} e {MAX_INODE_COUNT}"
        )
    if total_blocks > MAX_TOTAL_BLOCKS:
        raise InvalidParameterError(
            f"disco grande demais: máximo de {MAX_TOTAL_BLOCKS} blocos"
        )

    bitmap_blocks = max(1, math.ceil(total_blocks / (8 * block_size)))
    inode_table_start = BITMAP_START + bitmap_blocks
    inode_table_blocks = math.ceil(inode_count / (block_size // INODE_SIZE))
    data_start = inode_table_start + inode_table_blocks

    if total_blocks <= data_start:
        raise InvalidParameterError(
            f"disco pequeno demais: {total_blocks} blocos, mas os metadados já "
            f"ocupam {data_start} (mínimo: {data_start + 1} blocos)"
        )

    return Layout(
        block_size=block_size,
        total_blocks=total_blocks,
        inode_count=inode_count,
        bitmap_start=BITMAP_START,
        bitmap_blocks=bitmap_blocks,
        inode_table_start=inode_table_start,
        inode_table_blocks=inode_table_blocks,
        data_start=data_start,
    )
