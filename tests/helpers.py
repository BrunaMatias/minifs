"""Utilitários compartilhados pelos testes."""

import os
import shutil
import tempfile
import unittest


class TempDirTestCase(unittest.TestCase):
    """Cria um diretório temporário por teste e fornece ``self.path(...)``."""

    def setUp(self) -> None:
        self._tmp = tempfile.mkdtemp(prefix="minifs-test-")
        self.disk_path = self.path("disco.img")

    def tearDown(self) -> None:
        shutil.rmtree(self._tmp, ignore_errors=True)

    def path(self, name: str) -> str:
        return os.path.join(self._tmp, name)
