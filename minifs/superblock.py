"""Superblock do MiniFS, gravado nos primeiros 64 bytes do bloco 0.

Campos e offsets descritos em docs/LAYOUT_DISCO.md, seção 3.
"""

from __future__ import annotations

import struct
import time
import zlib
from dataclasses import dataclass, replace

from .errors import InvalidDiskError, MiniFSError
from .layout import DIRECT_REFS, INODE_SIZE, MAGIC, VERSION, Layout, compute_layout

_BODY = struct.Struct("<8sHHIIIIIIIIHHQI")
_CRC = struct.Struct("<I")
SUPERBLOCK_SIZE = _BODY.size + _CRC.size
assert SUPERBLOCK_SIZE == 64


@dataclass(frozen=True)
class Superblock:
    layout: Layout
    created_at: int
    mount_count: int = 0
    version: int = VERSION

    @property
    def block_size(self) -> int:
        return self.layout.block_size

    @property
    def total_blocks(self) -> int:
        return self.layout.total_blocks

    @classmethod
    def new(cls, layout: Layout) -> "Superblock":
        return cls(layout=layout, created_at=int(time.time()), mount_count=0)

    def with_mount(self) -> "Superblock":
        """Cópia com o contador de montagens incrementado."""
        return replace(self, mount_count=self.mount_count + 1)

    def pack(self) -> bytes:
        lo = self.layout
        body = _BODY.pack(
            MAGIC, self.version, INODE_SIZE,
            lo.block_size, lo.total_blocks,
            lo.bitmap_start, lo.bitmap_blocks,
            lo.inode_table_start, lo.inode_table_blocks,
            lo.inode_count, lo.data_start,
            DIRECT_REFS, 0,
            self.created_at, self.mount_count,
        )
        return body + _CRC.pack(zlib.crc32(body))

    @classmethod
    def unpack(cls, raw: bytes) -> "Superblock":
        """Decodifica e valida o superblock; inconsistências geram InvalidDiskError."""
        if len(raw) < SUPERBLOCK_SIZE:
            raise InvalidDiskError("arquivo pequeno demais para conter um superblock")
        body = raw[:_BODY.size]
        (magic, version, inode_size, block_size, total_blocks,
         bitmap_start, bitmap_blocks, inode_table_start, inode_table_blocks,
         inode_count, data_start, direct_refs, _reserved,
         created_at, mount_count) = _BODY.unpack(body)
        (stored_crc,) = _CRC.unpack_from(raw, _BODY.size)

        if magic != MAGIC:
            raise InvalidDiskError("assinatura inválida: o arquivo não é um disco MiniFS")
        if zlib.crc32(body) != stored_crc:
            raise InvalidDiskError("checksum do superblock não confere (disco corrompido)")
        if version != VERSION:
            raise InvalidDiskError(f"versão de formato {version} não suportada")
        if inode_size != INODE_SIZE or direct_refs != DIRECT_REFS:
            raise InvalidDiskError("formato de inode incompatível com esta versão")

        # As regiões gravadas devem coincidir com as recalculadas a partir dos parâmetros.
        try:
            layout = compute_layout(total_blocks, block_size, inode_count)
        except MiniFSError as exc:
            raise InvalidDiskError(f"parâmetros inválidos no superblock: {exc}") from exc
        stored = (bitmap_start, bitmap_blocks, inode_table_start,
                  inode_table_blocks, data_start)
        expected = (layout.bitmap_start, layout.bitmap_blocks, layout.inode_table_start,
                    layout.inode_table_blocks, layout.data_start)
        if stored != expected:
            raise InvalidDiskError("regiões do superblock inconsistentes com seus parâmetros")

        return cls(layout=layout, created_at=created_at,
                   mount_count=mount_count, version=version)
