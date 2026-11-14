"""Testes do disco virtual (Integrante 1)."""

import os
import unittest

from minifs.disk import VirtualDisk
from minifs.errors import (
    BlockOutOfRangeError,
    DiskClosedError,
    DiskNotFoundError,
    InvalidDiskError,
    InvalidParameterError,
)
from tests.helpers import TempDirTestCase


class VirtualDiskTest(TempDirTestCase):
    def test_create_gera_arquivo_zerado_do_tamanho_certo(self):
        with VirtualDisk.create(self.disk_path, 100, 512) as disk:
            self.assertEqual(disk.read_block(0), bytes(512))
            self.assertEqual(disk.read_block(99), bytes(512))
        self.assertEqual(os.path.getsize(self.disk_path), 100 * 512)

    def test_escrita_e_leitura_de_bloco(self):
        with VirtualDisk.create(self.disk_path, 10, 512) as disk:
            disk.write_block(3, b"A" * 512)
            disk.write_block(4, b"curto")  # completado com zeros
            self.assertEqual(disk.read_block(3), b"A" * 512)
            self.assertEqual(disk.read_block(4), b"curto" + bytes(507))
            self.assertEqual(disk.read_block(2), bytes(512))  # vizinho intacto
            self.assertEqual(disk.read_block(5), bytes(512))

    def test_dados_persistem_apos_fechar_e_reabrir(self):
        with VirtualDisk.create(self.disk_path, 10, 512) as disk:
            disk.write_block(7, b"persistente")
        with VirtualDisk.open(self.disk_path, 512, 10) as disk:
            self.assertTrue(disk.read_block(7).startswith(b"persistente"))

    def test_bloco_fora_dos_limites(self):
        with VirtualDisk.create(self.disk_path, 10, 512) as disk:
            for bad in (-1, 10, 1000, True, "1"):
                with self.subTest(bloco=bad):
                    with self.assertRaises(BlockOutOfRangeError):
                        disk.read_block(bad)
                    with self.assertRaises(BlockOutOfRangeError):
                        disk.write_block(bad, b"x")

    def test_dado_maior_que_o_bloco(self):
        with VirtualDisk.create(self.disk_path, 10, 512) as disk:
            with self.assertRaises(InvalidParameterError):
                disk.write_block(1, b"x" * 513)

    def test_blocos_contiguos(self):
        with VirtualDisk.create(self.disk_path, 10, 512) as disk:
            payload = bytes(range(256)) * 5  # 1280 B -> 3 blocos
            disk.write_blocks(2, payload)
            self.assertEqual(disk.read_blocks(2, 3)[:1280], payload)
            self.assertEqual(disk.read_block(4)[256:], bytes(256))

    def test_abrir_disco_inexistente(self):
        with self.assertRaises(DiskNotFoundError):
            VirtualDisk.open(self.path("nao-existe.img"), 512, 10)

    def test_abrir_com_tamanho_divergente(self):
        VirtualDisk.create(self.disk_path, 10, 512).close()
        with self.assertRaises(InvalidDiskError):
            VirtualDisk.open(self.disk_path, 512, 11)

    def test_operacao_apos_close(self):
        disk = VirtualDisk.create(self.disk_path, 10, 512)
        disk.close()
        disk.close()  # idempotente
        self.assertTrue(disk.closed)
        with self.assertRaises(DiskClosedError):
            disk.read_block(0)


if __name__ == "__main__":
    unittest.main()
