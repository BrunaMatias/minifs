"""Testes da fachada MiniFS: format, mount, df e persistência (Integrante 1)."""

import os
import unittest

from minifs.errors import DiskNotFoundError, InvalidDiskError, InvalidParameterError
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

    def test_operacoes_dos_outros_integrantes_ainda_pendentes(self):
        # Este teste deve ser REMOVIDO pelos Integrantes 2 e 3 ao implementar.
        with MiniFS.format(self.disk_path, 100) as fs:
            for call in (lambda: fs.create("a"), lambda: fs.rm("a"),
                         lambda: fs.stat("a"), fs.ls,
                         lambda: fs.write("a", b"x"), lambda: fs.read("a")):
                with self.assertRaises(NotImplementedError):
                    call()


if __name__ == "__main__":
    unittest.main()
