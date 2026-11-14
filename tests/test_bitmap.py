"""Testes do bitmap e do gerenciamento de blocos (Integrante 1)."""

import unittest

from minifs.bitmap import Bitmap
from minifs.disk import VirtualDisk
from minifs.errors import (
    BlockAlreadyFreeError,
    BlockOutOfRangeError,
    DiskFullError,
    InvalidDiskError,
    InvalidParameterError,
)
from minifs.layout import compute_layout
from tests.helpers import TempDirTestCase


class BitmapTest(TempDirTestCase):
    def setUp(self):
        super().setUp()
        self.layout = compute_layout(64)  # dados: blocos 18..63 (46 blocos)
        self.disk = VirtualDisk.create(self.disk_path, 64, 512)
        self.bm = Bitmap.create(self.disk, self.layout)

    def tearDown(self):
        self.disk.close()
        super().tearDown()

    def reload(self) -> Bitmap:
        """Fecha e reabre o disco, relendo o bitmap gravado."""
        self.disk.close()
        self.disk = VirtualDisk.open(self.disk_path, 512, 64)
        return Bitmap.load(self.disk, self.layout)

    # ---- estado inicial ---------------------------------------------
    def test_metadados_ocupados_dados_livres(self):
        for b in range(18):
            self.assertTrue(self.bm.is_used(b), f"bloco {b} deveria estar ocupado")
        for b in range(18, 64):
            self.assertTrue(self.bm.is_free(b))
        self.assertEqual(self.bm.free_count(), 46)
        self.assertEqual(self.bm.used_data_count(), 0)

    def test_representacao_em_disco(self):
        raw = self.disk.read_block(1)
        # blocos 0..17 ocupados -> bytes 0,1 = 0xFF e byte 2 = 0b00000011
        self.assertEqual(raw[0:3], b"\xff\xff\x03")
        # 64 blocos -> 8 bytes; bits restantes do bloco do bitmap marcados como 1
        self.assertEqual(raw[8:], b"\xff" * (512 - 8))

    # ---- alocação ---------------------------------------------------
    def test_first_fit_retorna_menores_indices(self):
        self.assertEqual(self.bm.allocate(3), [18, 19, 20])
        self.assertEqual(self.bm.allocate(1), [21])
        self.assertEqual(self.bm.free_count(), 42)

    def test_allocate_zero_e_negativo(self):
        self.assertEqual(self.bm.allocate(0), [])
        with self.assertRaises(InvalidParameterError):
            self.bm.allocate(-1)

    def test_blocos_liberados_sao_reutilizados(self):
        self.bm.allocate(10)                      # 18..27
        self.bm.free([20, 21, 25])
        self.assertEqual(self.bm.free_count(), 39)
        # os buracos são preenchidos antes de avançar para a área nunca usada
        self.assertEqual(self.bm.allocate(4), [20, 21, 25, 28])

    def test_alocacao_nao_contigua(self):
        self.bm.allocate(5)                       # 18..22
        self.bm.free([18, 20, 22])
        self.assertEqual(self.bm.allocate(3), [18, 20, 22])

    def test_disco_cheio_e_atomico(self):
        self.bm.allocate(40)
        before = [self.bm.is_used(b) for b in range(64)]
        with self.assertRaises(DiskFullError):
            self.bm.allocate(7)                   # só há 6 livres
        self.assertEqual([self.bm.is_used(b) for b in range(64)], before)
        self.assertEqual(self.bm.free_count(), 6)
        self.assertEqual(len(self.bm.allocate(6)), 6)  # o que cabe ainda funciona
        with self.assertRaises(DiskFullError):
            self.bm.allocate(1)

    def test_disco_cheio_recupera_apos_liberacao(self):
        self.bm.allocate(46)
        with self.assertRaises(DiskFullError):
            self.bm.allocate(1)
        self.bm.free([40])
        self.assertEqual(self.bm.allocate(1), [40])

    # ---- liberação --------------------------------------------------
    def test_double_free(self):
        self.bm.allocate(2)
        self.bm.free([18])
        with self.assertRaises(BlockAlreadyFreeError):
            self.bm.free([18])
        with self.assertRaises(BlockAlreadyFreeError):
            self.bm.free([19, 19])

    def test_nao_libera_metadados_nem_fora_do_disco(self):
        for bad in (0, 1, 5, 17):
            with self.assertRaises(BlockOutOfRangeError):
                self.bm.free([bad])
        with self.assertRaises(BlockOutOfRangeError):
            self.bm.free([64])

    def test_free_e_atomico(self):
        self.bm.allocate(3)                       # 18, 19, 20
        with self.assertRaises(BlockAlreadyFreeError):
            self.bm.free([18, 30])                # 30 está livre -> nada muda
        self.assertTrue(self.bm.is_used(18))
        self.assertEqual(self.bm.free_count(), 43)

    # ---- persistência -----------------------------------------------
    def test_estado_persiste_apos_reabrir(self):
        self.bm.allocate(5)
        self.bm.free([19])
        bm2 = self.reload()
        self.assertEqual(bm2.free_count(), 42)
        self.assertEqual(list(bm2.used_data_blocks()), [18, 20, 21, 22])
        self.assertEqual(bm2.allocate(1), [19])   # reutilização após reinício

    def test_bitmap_corrompido_e_detectado(self):
        raw = bytearray(self.disk.read_block(1))
        raw[0] &= 0xFE                             # superblock marcado como livre
        self.disk.write_block(1, bytes(raw))
        with self.assertRaises(InvalidDiskError):
            self.reload()

    # ---- disco com bitmap de vários blocos ----------------------------
    def test_bitmap_multibloco(self):
        self.disk.close()
        lo = compute_layout(5000)                 # 2 blocos de bitmap
        self.disk = VirtualDisk.create(self.path("grande.img"), 5000, 512)
        bm = Bitmap.create(self.disk, lo)
        self.assertEqual(bm.free_count(), 5000 - lo.data_start)
        bm.allocate(5000 - lo.data_start - 1)     # deixa só o último bloco livre
        self.assertEqual(bm.allocate(1), [4999])  # bit 4999 está no 2º bloco do bitmap
        self.disk.close()
        self.disk = VirtualDisk.open(self.path("grande.img"), 512, 5000)
        bm2 = Bitmap.load(self.disk, lo)
        self.assertEqual(bm2.free_count(), 0)
        bm2.free([4999, lo.data_start])
        self.assertEqual(bm2.allocate(2), [lo.data_start, 4999])

    def test_render(self):
        self.bm.allocate(2)
        text = self.bm.render()
        self.assertIn("SB" + "I" * 16 + "##" + "." * 44, text)


if __name__ == "__main__":
    unittest.main()
