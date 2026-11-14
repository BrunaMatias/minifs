"""Fachada do MiniFS: integra disco, superblock, bitmap e metadados.

Divisão de responsabilidades por método descrita em docs/INTERFACES.md.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List

from .bitmap import Bitmap
from .disk import VirtualDisk
from .errors import DuplicateNameError, InvalidDiskError, NoFreeInodeError
from .inode import MAX_FILE_ID, Inode, InodeTable, validate_name
from .layout import DEFAULT_BLOCK_SIZE, DEFAULT_INODE_COUNT, Layout, compute_layout
from .superblock import SUPERBLOCK_SIZE, Superblock


@dataclass(frozen=True)
class DiskUsage:
    """Resultado do comando df; contagens referentes à área de dados."""

    block_size: int
    total_blocks: int
    metadata_blocks: int
    data_blocks: int
    used_blocks: int
    free_blocks: int

    @property
    def free_bytes(self) -> int:
        return self.free_blocks * self.block_size

    @property
    def used_bytes(self) -> int:
        return self.used_blocks * self.block_size

    @property
    def data_bytes(self) -> int:
        return self.data_blocks * self.block_size

    @property
    def use_percent(self) -> float:
        return 100.0 * self.used_blocks / self.data_blocks if self.data_blocks else 0.0


@dataclass(frozen=True)
class FileInfo:
    """Metadados de um arquivo retornados por create, stat, ls e write."""

    file_id: int
    name: str
    size: int
    blocks: List[int] = field(default_factory=list)


def _file_info(inode: Inode) -> FileInfo:
    return FileInfo(inode.file_id, inode.name, inode.size, inode.blocks.copy())


class MiniFS:
    """Sistema de arquivos montado sobre um disco virtual."""

    def __init__(self, disk: VirtualDisk, superblock: Superblock, bitmap: Bitmap) -> None:
        self.disk = disk
        self.superblock = superblock
        self.bitmap = bitmap
        self.inodes = InodeTable.load(disk, self.layout)
        for inode in self.inodes.iter_used():
            self._check_inode_blocks(inode)

    @property
    def layout(self) -> Layout:
        return self.superblock.layout

    @classmethod
    def format(cls, path: str, total_blocks: int,
               block_size: int = DEFAULT_BLOCK_SIZE,
               inode_count: int = DEFAULT_INODE_COUNT) -> "MiniFS":
        """Cria um disco vazio e o retorna montado.

        O superblock é gravado por último para que um format interrompido seja rejeitado.
        """
        layout = compute_layout(total_blocks, block_size, inode_count)
        disk = VirtualDisk.create(path, layout.total_blocks, layout.block_size)
        try:
            bitmap = Bitmap.create(disk, layout)
            superblock = Superblock.new(layout).with_mount()
            fs = cls(disk, superblock, bitmap)
            disk.write_block(0, superblock.pack())
            disk.sync()
            return fs
        except BaseException:
            disk.close()
            raise

    @classmethod
    def mount(cls, path: str) -> "MiniFS":
        """Abre um disco existente, carregando o superblock, o bitmap e os inodes."""
        superblock = Superblock.unpack(VirtualDisk.read_header(path, SUPERBLOCK_SIZE))
        disk = VirtualDisk.open(path, superblock.block_size, superblock.total_blocks)
        try:
            bitmap = Bitmap.load(disk, superblock.layout)
            superblock = superblock.with_mount()
            fs = cls(disk, superblock, bitmap)
            disk.write_block(0, superblock.pack())
            return fs
        except BaseException:
            disk.close()
            raise

    def close(self) -> None:
        self.disk.close()

    def __enter__(self) -> "MiniFS":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    def df(self) -> DiskUsage:
        lo = self.layout
        return DiskUsage(
            block_size=lo.block_size,
            total_blocks=lo.total_blocks,
            metadata_blocks=lo.metadata_blocks,
            data_blocks=lo.data_blocks,
            used_blocks=self.bitmap.used_data_count(),
            free_blocks=self.bitmap.free_count(),
        )

    def create(self, name: str) -> FileInfo:
        """Cria um arquivo vazio. Erros: InvalidNameError, DuplicateNameError, NoFreeInodeError."""
        validate_name(name)
        if self.inodes.find(name) is not None:
            raise DuplicateNameError(f"já existe um arquivo com o nome {name!r}")
        slot = self.inodes.find_free()
        if slot is None:
            raise NoFreeInodeError("tabela de inodes cheia")
        if self.inodes.last_file_id == MAX_FILE_ID:
            raise NoFreeInodeError("limite de identificadores de arquivos atingido")
        inode = Inode(slot.index, used=True, file_id=self.inodes.last_file_id + 1, name=name)
        self.inodes.save(inode)
        return _file_info(inode)

    def rm(self, name: str) -> None:
        """Remove o arquivo e libera seus blocos no bitmap. Erros: NoSuchFileError."""
        inode = self.inodes.require(name)
        self._check_inode_blocks(inode)
        self.inodes.save(Inode(inode.index, file_id=inode.file_id))
        if inode.blocks:
            # Persiste a remoção antes de permitir que o bitmap reutilize os blocos.
            self.disk.sync()
            self.bitmap.free(inode.blocks)

    def _check_inode_blocks(self, inode: Inode) -> None:
        for block in inode.blocks:
            if self.bitmap.is_free(block):
                raise InvalidDiskError(f"inode {inode.index}: bloco {block} marcado como livre")

    def stat(self, name: str) -> FileInfo:
        """Metadados do arquivo. Erros: NoSuchFileError."""
        return _file_info(self.inodes.require(name))

    def ls(self) -> List[FileInfo]:
        """Lista os arquivos existentes."""
        return [_file_info(inode) for inode in self.inodes.iter_used()]

    def write(self, name: str, data: bytes) -> FileInfo:
        """Substitui o conteúdo do arquivo.

        Erros: NoSuchFileError, FileTooLargeError, DiskFullError.
        """
        raise NotImplementedError("write: responsabilidade do Integrante 3")

    def read(self, name: str) -> bytes:
        """Conteúdo completo do arquivo. Erros: NoSuchFileError."""
        raise NotImplementedError("read: responsabilidade do Integrante 3")
