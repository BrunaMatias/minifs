"""Testes do cálculo do layout do disco (Integrante 1)."""

import unittest

from minifs.errors import BlockOutOfRangeError, InvalidParameterError
from minifs.layout import INODE_SIZE, compute_layout


class LayoutTest(unittest.TestCase):
    def test_layout_padrao_2048_blocos(self):
        lo = compute_layout(2048)
        self.assertEqual(lo.block_size, 512)
        self.assertEqual((lo.bitmap_start, lo.bitmap_blocks), (1, 1))
        self.assertEqual((lo.inode_table_start, lo.inode_table_blocks), (2, 16))
        self.assertEqual(lo.data_start, 18)
        self.assertEqual(lo.data_blocks, 2030)
        self.assertEqual(lo.max_file_size, 20 * 512)
        self.assertEqual(lo.disk_size, 2048 * 512)

    def test_regioes_sao_contiguas_e_sem_sobreposicao(self):
        for blocks, bs, inodes in [(2048, 512, 64), (50000, 512, 64),
                                   (10000, 4096, 1000), (40, 1024, 1)]:
            lo = compute_layout(blocks, bs, inodes)
            self.assertEqual(lo.bitmap_start, 1)
            self.assertEqual(lo.inode_table_start, lo.bitmap_start + lo.bitmap_blocks)
            self.assertEqual(lo.data_start, lo.inode_table_start + lo.inode_table_blocks)
            # o bitmap tem bits para todos os blocos
            self.assertGreaterEqual(lo.bitmap_blocks * bs * 8, blocks)
            # a tabela comporta todos os inodes
            self.assertGreaterEqual(lo.inode_table_blocks * bs // INODE_SIZE, inodes)

    def test_bitmap_cresce_com_o_disco(self):
        # 512 B de bitmap = 4096 bits -> 4097 blocos precisam de 2 blocos de bitmap
        self.assertEqual(compute_layout(4096).bitmap_blocks, 1)
        self.assertEqual(compute_layout(4097).bitmap_blocks, 2)

    def test_region_of(self):
        lo = compute_layout(2048)
        self.assertEqual(lo.region_of(0), "superblock")
        self.assertEqual(lo.region_of(1), "bitmap")
        self.assertEqual(lo.region_of(2), "inodes")
        self.assertEqual(lo.region_of(17), "inodes")
        self.assertEqual(lo.region_of(18), "dados")
        self.assertEqual(lo.region_of(2047), "dados")
        with self.assertRaises(BlockOutOfRangeError):
            lo.region_of(2048)

    def test_inode_location(self):
        lo = compute_layout(2048)  # 4 inodes por bloco de 512 B
        self.assertEqual(lo.inode_location(0), (2, 0))
        self.assertEqual(lo.inode_location(3), (2, 384))
        self.assertEqual(lo.inode_location(4), (3, 0))
        self.assertEqual(lo.inode_location(63), (17, 384))
        with self.assertRaises(InvalidParameterError):
            lo.inode_location(64)

    def test_parametros_invalidos(self):
        for args in [(0,), (-5,), (18,), (2048, 500), (2048, 512, 0),
                     (2048, 512, 5000), (1 << 21,), ("2048",), (2048.0,)]:
            with self.subTest(args=args), self.assertRaises(InvalidParameterError):
                compute_layout(*args)

    def test_menor_disco_possivel(self):
        lo = compute_layout(19)  # 18 de metadados + 1 de dados
        self.assertEqual(lo.data_blocks, 1)


if __name__ == "__main__":
    unittest.main()
