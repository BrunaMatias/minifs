"""Registros de arquivo e tabela de inodes do formato MiniFS v1."""

from __future__ import annotations

import struct
from dataclasses import dataclass, field, replace
from typing import Iterator, List, Optional

from .disk import VirtualDisk
from .errors import DiskClosedError, InvalidDiskError, InvalidNameError, NoSuchFileError
from .layout import DIRECT_REFS, INODE_FORMAT, INODE_SIZE, MAX_NAME_LEN, Layout

_RECORD = struct.Struct(INODE_FORMAT)
MAX_FILE_ID = (1 << 32) - 1


def validate_name(name: str) -> bytes:
    """Valida o nome e devolve sua representação em UTF-8."""
    if not isinstance(name, str) or not name or "\0" in name or "/" in name:
        raise InvalidNameError("o nome deve ser não vazio e não pode conter '/' nem NUL")
    try:
        encoded = name.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise InvalidNameError("o nome deve ser representável em UTF-8") from exc
    if len(encoded) > MAX_NAME_LEN:
        raise InvalidNameError(f"o nome pode ter no máximo {MAX_NAME_LEN} bytes em UTF-8")
    return encoded


@dataclass
class Inode:
    index: int
    used: bool = False
    file_id: int = 0
    size: int = 0
    name: str = ""
    blocks: List[int] = field(default_factory=list)

    def pack(self, layout: Layout) -> bytes:
        if not self.used:
            # Um registro livre pode guardar o último id para impedir sua reutilização.
            return _RECORD.pack(0, self.file_id, 0, 0, b"", *([0] * DIRECT_REFS))
        self._validate(layout)
        name = validate_name(self.name)
        refs = self.blocks + [0] * (DIRECT_REFS - len(self.blocks))
        return _RECORD.pack(1, self.file_id, self.size, len(self.blocks), name, *refs)

    @classmethod
    def unpack(cls, index: int, raw: bytes, layout: Layout) -> "Inode":
        used, file_id, size, count, name, *refs = _RECORD.unpack(raw)
        if used == 0:
            return cls(index, file_id=file_id)
        if used != 1 or count > DIRECT_REFS:
            raise InvalidDiskError(f"inode {index}: registro inválido")
        try:
            decoded = name.rstrip(b"\0").decode("utf-8")
            validate_name(decoded)
        except (UnicodeDecodeError, InvalidNameError) as exc:
            raise InvalidDiskError(f"inode {index}: nome inválido") from exc
        inode = cls(index, True, file_id, size, decoded, refs[:count])
        inode._validate(layout)
        return inode

    def _validate(self, layout: Layout) -> None:
        if not 0 < self.file_id <= MAX_FILE_ID:
            raise InvalidDiskError(f"inode {self.index}: identificador inválido")
        expected = (self.size + layout.block_size - 1) // layout.block_size
        if not 0 <= self.size <= layout.max_file_size or len(self.blocks) != expected:
            raise InvalidDiskError(f"inode {self.index}: tamanho incompatível com os blocos")
        if len(set(self.blocks)) != len(self.blocks) or any(
            not layout.is_data_block(block) for block in self.blocks
        ):
            raise InvalidDiskError(f"inode {self.index}: referência de bloco inválida")


class InodeTable:
    """Tabela persistente com cópias editáveis dos registros para o chamador."""

    def __init__(self, disk: VirtualDisk, layout: Layout, records: List[Inode]) -> None:
        self._disk = disk
        self._layout = layout
        self._records = records
        self.last_file_id = max((inode.file_id for inode in records), default=0)

    @classmethod
    def load(cls, disk: VirtualDisk, layout: Layout) -> "InodeTable":
        raw = disk.read_blocks(layout.inode_table_start, layout.inode_table_blocks)
        records = [
            Inode.unpack(index, raw[offset:offset + INODE_SIZE], layout)
            for index, offset in enumerate(range(0, layout.inode_count * INODE_SIZE, INODE_SIZE))
        ]
        ids, names, blocks = set(), set(), set()
        for inode in records:
            if not inode.used:
                continue
            if inode.file_id in ids or inode.name in names or blocks.intersection(inode.blocks):
                raise InvalidDiskError(f"inode {inode.index}: id, nome ou bloco compartilhado")
            ids.add(inode.file_id)
            names.add(inode.name)
            blocks.update(inode.blocks)
        return cls(disk, layout, records)

    def _check_open(self) -> None:
        if self._disk.closed:
            raise DiskClosedError("o disco virtual já foi fechado")

    def find(self, name: str) -> Optional[Inode]:
        self._check_open()
        for inode in self._records:
            if inode.used and inode.name == name:
                return replace(inode, blocks=inode.blocks.copy())
        return None

    def require(self, name: str) -> Inode:
        inode = self.find(name)
        if inode is None:
            raise NoSuchFileError(f"arquivo {name!r} não encontrado")
        return inode

    def find_free(self) -> Optional[Inode]:
        self._check_open()
        for inode in self._records:
            if not inode.used:
                return replace(inode)
        return None

    def iter_used(self) -> Iterator[Inode]:
        self._check_open()
        for inode in self._records:
            if inode.used:
                yield replace(inode, blocks=inode.blocks.copy())

    def save(self, inode: Inode) -> None:
        """Atualiza apenas o registro indicado no bloco de metadados."""
        block, offset = self._layout.inode_location(inode.index)
        record = inode.pack(self._layout)
        raw = self._disk.read_block(block)
        self._disk.write_block(block, raw[:offset] + record + raw[offset + INODE_SIZE:])
        self._records[inode.index] = replace(inode, blocks=inode.blocks.copy())
        self.last_file_id = max(self.last_file_id, inode.file_id)
