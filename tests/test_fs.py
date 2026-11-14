"""Testes da fachada MiniFS: format, mount, df e persistência (Integrante 1)."""

import os
import unittest
from unittest.mock import patch

from minifs.errors import (
    DiskClosedError,
    DiskNotFoundError,
    DuplicateNameError,
    InvalidDiskError,
    InvalidNameError,
    InvalidParameterError,
    NoFreeInodeError,
    NoSuchFileError,
)
from minifs.fs import MiniFS
from tests.helpers import TempDirTestCase


class MiniFSFormatMountTest(TempDirTestCase):
    def test_format_cria_disco_vazio(self):
        with MiniFS.format(self.disk_path, 2048) as fs:
            u = fs.df()
            self.assertEqual((u.total_blocks, u.metadata_blocks, u.data_blocks),
                             (2048, 18, 2030))
            self.assertEqual((u.used_blocks, u.free_blocks), (0, 2030))
            self.assertEqual(u.free_bytes, 2030 * 512)
        self.assertEqual(os.path.getsize(self.disk_path), 2048 * 512)

    def test_format_com_parametros(self):
        with MiniFS.format(self.disk_path, 1000, 4096, 256) as fs:
            lo = fs.layout
            self.assertEqual((lo.block_size, lo.inode_count, lo.inode_table_blocks),
                             (4096, 256, 8))

    def test_format_invalido_nao_cria_arquivo(self):
        with self.assertRaises(InvalidParameterError):
            MiniFS.format(self.disk_path, 10)
        self.assertFalse(os.path.exists(self.disk_path))

    def test_persistencia_entre_montagens(self):
        with MiniFS.format(self.disk_path, 2048) as fs:
            created = fs.superblock.created_at
            fs.bitmap.allocate(10)
            fs.bitmap.free([20, 21])
        with MiniFS.mount(self.disk_path) as fs:
            self.assertEqual(fs.superblock.created_at, created)
            self.assertEqual(fs.df().used_blocks, 8)
            self.assertEqual(fs.bitmap.allocate(2), [20, 21])
        with MiniFS.mount(self.disk_path) as fs:
            self.assertEqual(fs.df().used_blocks, 10)

    def test_mount_count_e_persistido(self):
        MiniFS.format(self.disk_path, 100).close()
        for expected in (2, 3, 4):
            with MiniFS.mount(self.disk_path) as fs:
                self.assertEqual(fs.superblock.mount_count, expected)

    def test_reformatar_apaga_tudo(self):
        with MiniFS.format(self.disk_path, 2048) as fs:
            fs.bitmap.allocate(100)
        with MiniFS.format(self.disk_path, 500) as fs:
            self.assertEqual(fs.df().used_blocks, 0)
            self.assertEqual(fs.layout.total_blocks, 500)
        self.assertEqual(os.path.getsize(self.disk_path), 500 * 512)

    def test_mount_disco_inexistente(self):
        with self.assertRaises(DiskNotFoundError):
            MiniFS.mount(self.path("nada.img"))

    def test_mount_arquivo_que_nao_e_minifs(self):
        with open(self.disk_path, "wb") as fh:
            fh.write(b"isto nao e um disco" * 100)
        with self.assertRaises(InvalidDiskError):
            MiniFS.mount(self.disk_path)

    def test_mount_arquivo_truncado(self):
        MiniFS.format(self.disk_path, 100).close()
        with open(self.disk_path, "r+b") as fh:
            fh.truncate(50 * 512)
        with self.assertRaises(InvalidDiskError):
            MiniFS.mount(self.disk_path)


class MiniFSMetadataTest(TempDirTestCase):
    def test_metadados_persistem_em_inodes_do_mesmo_bloco_e_de_blocos_distintos(self):
        names = ["primeiro", "segundo", "terceiro", "quarto", "é" * 16]
        with MiniFS.format(self.disk_path, 20, inode_count=5) as fs:
            created = [fs.create(name) for name in names]
            self.assertEqual([info.file_id for info in created], list(range(1, 6)))
            self.assertEqual(fs.df().used_blocks, 0)
        with MiniFS.mount(self.disk_path) as fs:
            self.assertEqual(fs.ls(), created)
            self.assertEqual(fs.stat(names[-1]), created[-1])
            self.assertEqual((created[-1].size, created[-1].blocks), (0, []))

    def test_nomes_invalidos_duplicados_e_tabela_cheia(self):
        with MiniFS.format(self.disk_path, 20, inode_count=1) as fs:
            for name in ("", "a/b", "a\0b", "é" * 17, "\ud800"):
                with self.subTest(name=name), self.assertRaises(InvalidNameError):
                    fs.create(name)
            info = fs.create("dados")
            with self.assertRaises(DuplicateNameError):
                fs.create("dados")
            with self.assertRaises(NoFreeInodeError):
                fs.create("outro")
            self.assertEqual(fs.ls(), [info])
            self.assertGreater(fs.df().free_blocks, 0)

    def test_rm_persiste_e_reutiliza_inode_com_novo_id_mesmo_apos_remontar(self):
        with MiniFS.format(self.disk_path, 20, inode_count=1) as fs:
            old = fs.create("dados")
            fs.rm("dados")
        with MiniFS.mount(self.disk_path) as fs:
            self.assertEqual(fs.ls(), [])
            for operation in (fs.stat, fs.rm):
                with self.assertRaises(NoSuchFileError):
                    operation("dados")
            self.assertGreater(fs.create("dados").file_id, old.file_id)

    def test_rm_libera_blocos_referenciados_e_first_fit_os_reutiliza(self):
        with MiniFS.format(self.disk_path, 10, inode_count=2) as fs:
            fs.bitmap.allocate(fs.layout.data_blocks)
            fs.create("dados")  # Um arquivo vazio pode ser criado com os blocos de dados cheios.
            inode = fs.inodes.require("dados")
            first = fs.layout.data_start
            inode.blocks = [first + 2, first]
            inode.size = fs.layout.block_size + 1
            fs.inodes.save(inode)  # Simula a atualização de metadados feita pelo futuro write.

        with MiniFS.mount(self.disk_path) as fs:
            info = fs.stat("dados")
            self.assertEqual(info.size, fs.layout.block_size + 1)
            self.assertEqual(info.blocks, [first + 2, first])
            info.blocks.clear()
            fs.rm("dados")
            self.assertEqual(fs.df().free_blocks, 2)

        with MiniFS.mount(self.disk_path) as fs:
            self.assertEqual(fs.ls(), [])
            self.assertEqual(fs.bitmap.allocate(2), [first, first + 2])

    def test_rm_preserva_blocos_quando_gravacao_do_inode_falha(self):
        with MiniFS.format(self.disk_path, 10, inode_count=1) as fs:
            fs.create("dados")
            inode = fs.inodes.require("dados")
            inode.blocks = fs.bitmap.allocate(1)
            inode.size = 1
            fs.inodes.save(inode)
            with patch.object(fs.disk, "write_block", side_effect=OSError("falha de escrita")):
                with self.assertRaises(OSError):
                    fs.rm("dados")
            self.assertEqual(fs.stat("dados").blocks, inode.blocks)
            self.assertTrue(fs.bitmap.is_used(inode.blocks[0]))

    def test_metadados_em_disco_fechado(self):
        fs = MiniFS.format(self.disk_path, 100)
        fs.close()
        with self.assertRaises(DiskClosedError):
            fs.ls()

    def test_mount_rejeita_inode_que_referencia_bloco_livre(self):
        with MiniFS.format(self.disk_path, 10, inode_count=1) as fs:
            fs.create("dados")
            inode = fs.inodes.require("dados")
            inode.blocks = fs.bitmap.allocate(1)
            inode.size = 1
            fs.inodes.save(inode)
            fs.bitmap.free(inode.blocks)
        with self.assertRaises(InvalidDiskError):
            MiniFS.mount(self.disk_path)


if __name__ == "__main__":
    unittest.main()
