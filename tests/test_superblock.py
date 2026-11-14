"""Testes do superblock (Integrante 1)."""

import struct
import unittest

from minifs.errors import InvalidDiskError
from minifs.layout import MAGIC, compute_layout
from minifs.superblock import SUPERBLOCK_SIZE, Superblock


class SuperblockTest(unittest.TestCase):
    def setUp(self):
        self.sb = Superblock(layout=compute_layout(2048), created_at=1_700_000_000,
                             mount_count=3)

    def test_ida_e_volta(self):
        raw = self.sb.pack()
        self.assertEqual(len(raw), SUPERBLOCK_SIZE)
        self.assertEqual(Superblock.unpack(raw), self.sb)

    def test_campos_nos_offsets_documentados(self):
        raw = self.sb.pack()
        self.assertEqual(raw[0:8], MAGIC)
        self.assertEqual(struct.unpack_from("<I", raw, 12)[0], 512)    # block_size
        self.assertEqual(struct.unpack_from("<I", raw, 16)[0], 2048)   # total_blocks
        self.assertEqual(struct.unpack_from("<I", raw, 40)[0], 18)     # data_start
        self.assertEqual(struct.unpack_from("<I", raw, 56)[0], 3)      # mount_count

    def test_with_mount_incrementa(self):
        self.assertEqual(self.sb.with_mount().mount_count, 4)
        self.assertEqual(self.sb.mount_count, 3)  # imutável

    def test_magic_invalido(self):
        raw = bytearray(self.sb.pack())
        raw[0:8] = b"NOTMINFS"
        with self.assertRaisesRegex(InvalidDiskError, "assinatura"):
            Superblock.unpack(bytes(raw))

    def test_bloco_zerado_nao_e_minifs(self):
        with self.assertRaises(InvalidDiskError):
            Superblock.unpack(bytes(512))

    def test_checksum_detecta_corrupcao(self):
        raw = bytearray(self.sb.pack())
        raw[16] ^= 0x01  # altera total_blocks
        with self.assertRaisesRegex(InvalidDiskError, "checksum"):
            Superblock.unpack(bytes(raw))

    def test_regioes_inconsistentes_mesmo_com_crc_valido(self):
        import zlib
        raw = bytearray(self.sb.pack())
        struct.pack_into("<I", raw, 40, 5)  # data_start falso
        struct.pack_into("<I", raw, 60, zlib.crc32(bytes(raw[:60])))
        with self.assertRaisesRegex(InvalidDiskError, "inconsistentes"):
            Superblock.unpack(bytes(raw))

    def test_dados_curtos(self):
        with self.assertRaises(InvalidDiskError):
            Superblock.unpack(b"MINIFS01")


if __name__ == "__main__":
    unittest.main()
