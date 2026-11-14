"""Testes da CLI, incluindo persistência entre PROCESSOS diferentes."""

import io
import os
import subprocess
import sys
import unittest

from minifs.cli import Shell
from tests.helpers import TempDirTestCase

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def run_cli(disk, *args, stdin=None):
    """Executa ``python -m minifs`` em um processo separado."""
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    return subprocess.run(
        [sys.executable, "-m", "minifs", "--disk", disk, *args],
        input=stdin, capture_output=True, text=True, encoding="utf-8",
        cwd=ROOT, env=env, timeout=60,
    )


class ShellTest(TempDirTestCase):
    def setUp(self):
        super().setUp()
        self.out = io.StringIO()
        self.sh = Shell(self.disk_path, self.out)

    def tearDown(self):
        self.sh.close()
        super().tearDown()

    def run_line(self, line):
        self.out.seek(0)
        self.out.truncate()
        ok = self.sh.execute_line(line)
        return ok, self.out.getvalue()

    def test_comando_sem_disco(self):
        ok, out = self.run_line("df")
        self.assertFalse(ok)
        self.assertIn("execute 'format", out)

    def test_format_df_info_bitmap(self):
        self.assertTrue(self.run_line("format 2048")[0])
        ok, out = self.run_line("df")
        self.assertTrue(ok)
        self.assertIn("2030", out)
        ok, out = self.run_line("info")
        self.assertIn("montagens", out)
        ok, out = self.run_line("bitmap")
        self.assertIn("SBIIII", out)

    def test_dump_mostra_superblock_e_bitmap(self):
        self.run_line("format 64")
        ok, out = self.run_line("dump 0 64")
        self.assertTrue(ok)
        self.assertIn("região: superblock", out)
        self.assertIn("|MINIFS01", out)
        ok, out = self.run_line("dump 1")
        self.assertIn("0000  ff ff 03 00 00 00 00 00 ff ff", out)
        self.assertFalse(self.run_line("dump 64")[0])  # fora do disco

    def test_erros_de_uso(self):
        self.run_line("format 100")
        for line in ("format", "format abc", "df x", "dbg-alloc", "comando-inexistente",
                     'write "aspas abertas'):
            with self.subTest(line=line):
                ok, out = self.run_line(line)
                self.assertFalse(ok)
                self.assertTrue(out.startswith(("uso:", "erro:")), out)

    def test_disco_cheio_pela_cli(self):
        self.run_line("format 20")                 # 2 blocos de dados
        self.assertTrue(self.run_line("dbg-alloc 2")[0])
        ok, out = self.run_line("dbg-alloc 1")
        self.assertFalse(ok)
        self.assertIn("disco cheio", out)


class CliProcessTest(TempDirTestCase):
    def test_metadados_persistem_entre_processos(self):
        self.assertEqual(run_cli(self.disk_path, "format", "100").returncode, 0)
        created = run_cli(self.disk_path, "create", "dados.txt")
        self.assertEqual(created.returncode, 0, created.stdout)

        duplicate = run_cli(self.disk_path, "create", "dados.txt")
        self.assertEqual(duplicate.returncode, 1)
        self.assertIn("já existe", duplicate.stdout)
        self.assertIn("dados.txt", run_cli(self.disk_path, "ls").stdout)

        stat = run_cli(self.disk_path, "stat", "dados.txt")
        self.assertEqual(stat.returncode, 0, stat.stdout)
        self.assertIn("tamanho : 0 B", stat.stdout)
        self.assertIn("blocos  : (nenhum)", stat.stdout)

        removed = run_cli(self.disk_path, "rm", "dados.txt")
        self.assertEqual(removed.returncode, 0, removed.stdout)
        self.assertIn("(nenhum arquivo)", run_cli(self.disk_path, "ls").stdout)
        self.assertEqual(run_cli(self.disk_path, "stat", "dados.txt").returncode, 1)

    def test_persistencia_entre_execucoes_do_programa(self):
        r = run_cli(self.disk_path, "format", "2048")
        self.assertEqual(r.returncode, 0, r.stderr)
        r = run_cli(self.disk_path, "dbg-alloc", "5")
        self.assertIn("18 19 20 21 22", r.stdout)
        run_cli(self.disk_path, "dbg-free", "19", "20")
        # novo processo: o estado do bitmap foi lido do arquivo do disco
        r = run_cli(self.disk_path, "df")
        self.assertRegex(r.stdout, r"usados\s+3\s")
        r = run_cli(self.disk_path, "dbg-alloc", "3")
        self.assertIn("19 20 23", r.stdout)     # liberados são reutilizados primeiro

    def test_modo_script_por_stdin(self):
        script = "format 30\ndf\n# comentario\ndbg-alloc 12\ndbg-alloc 1\nexit\n"
        r = run_cli(self.disk_path, stdin=script)
        self.assertEqual(r.returncode, 1)       # houve um erro (disco cheio)
        self.assertIn("minifs> dbg-alloc 1", r.stdout)
        self.assertIn("disco cheio", r.stdout)

    def test_codigo_de_saida(self):
        self.assertEqual(run_cli(self.disk_path, "df").returncode, 1)
        self.assertEqual(run_cli(self.disk_path, "format", "100").returncode, 0)
        self.assertEqual(run_cli(self.disk_path, "df").returncode, 0)


if __name__ == "__main__":
    unittest.main()
