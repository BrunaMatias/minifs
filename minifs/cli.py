"""Interface de linha de comando do MiniFS.

Modos: interativo, roteiro lido da entrada padrão ou comando único na linha de comando.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import os
import shlex
import sys
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional, TextIO

from .errors import DiskNotFoundError, MiniFSError
from .fs import FileInfo, MiniFS
from .layout import DEFAULT_BLOCK_SIZE, DEFAULT_INODE_COUNT

DEFAULT_DISK = "minifs.img"
PROMPT = "minifs> "


class UsageError(Exception):
    """Argumentos inválidos para um comando."""


@dataclass
class Command:
    handler: Callable[["Shell", List[str]], None]
    usage: str
    help: str
    owner: str


class Shell:
    def __init__(self, disk_path: str = DEFAULT_DISK, out: TextIO = sys.stdout) -> None:
        self.disk_path = disk_path
        self.out = out
        self._fs: Optional[MiniFS] = None

    @property
    def fs(self) -> MiniFS:
        """Monta o disco na primeira operação que precisar dele."""
        if self._fs is None:
            if not os.path.isfile(self.disk_path):
                raise DiskNotFoundError(
                    f"disco '{self.disk_path}' não encontrado; execute 'format <blocos>'"
                )
            self._fs = MiniFS.mount(self.disk_path)
        return self._fs

    def close(self) -> None:
        if self._fs is not None:
            self._fs.close()
            self._fs = None

    def print(self, *args) -> None:
        print(*args, file=self.out)

    def execute(self, argv: List[str]) -> bool:
        """Executa um comando já separado em argumentos e indica se teve sucesso."""
        if not argv:
            return True
        name, args = argv[0].lower(), argv[1:]
        cmd = COMMANDS.get(name)
        if cmd is None:
            self.print(f"erro: comando desconhecido '{name}' (digite 'help')")
            return False
        try:
            cmd.handler(self, args)
            return True
        except UsageError as exc:
            self.print(f"uso: {cmd.usage}" + (f"  ({exc})" if str(exc) else ""))
        except NotImplementedError:
            self.print(f"[pendente] '{name}' ainda não implementado, "
                       f"responsabilidade do {cmd.owner} (ver docs/INTERFACES.md)")
        except MiniFSError as exc:
            self.print(f"erro: {exc}")
        return False

    def execute_line(self, line: str) -> bool:
        try:
            argv = shlex.split(line, comments=True, posix=True)
        except ValueError as exc:
            self.print(f"erro: linha inválida ({exc})")
            return False
        return self.execute(argv)

    def repl(self, stream: TextIO = sys.stdin) -> int:
        """Lê comandos até EOF ou exit e retorna o código de saída do processo."""
        interactive = stream.isatty()
        ok = True
        while True:
            if interactive:
                self.out.write(PROMPT)
                self.out.flush()
            line = stream.readline()
            if not line:
                break
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            # Comandos lidos de arquivo são ecoados para a saída ficar legível.
            if not interactive:
                self.print(PROMPT + line)
            if line.lower() in ("exit", "quit", "sair"):
                break
            ok = self.execute_line(line) and ok
        return 0 if ok else 1


def _int(value: str, what: str) -> int:
    try:
        return int(value)
    except ValueError:
        raise UsageError(f"{what} deve ser um número inteiro") from None


def cmd_format(sh: Shell, args: List[str]) -> None:
    if not 1 <= len(args) <= 3:
        raise UsageError()
    blocks = _int(args[0], "blocos")
    bs = _int(args[1], "tamanho do bloco") if len(args) > 1 else DEFAULT_BLOCK_SIZE
    inodes = _int(args[2], "inodes") if len(args) > 2 else DEFAULT_INODE_COUNT
    sh.close()
    sh._fs = MiniFS.format(sh.disk_path, blocks, bs, inodes)
    lo = sh._fs.layout
    sh.print(f"disco '{sh.disk_path}' formatado: {lo.total_blocks} blocos x "
             f"{lo.block_size} B = {lo.disk_size} B")
    sh.print(f"  metadados: {lo.metadata_blocks} blocos | dados: {lo.data_blocks} "
             f"blocos livres (a partir do bloco {lo.data_start})")


def cmd_df(sh: Shell, args: List[str]) -> None:
    if args:
        raise UsageError()
    u = sh.fs.df()
    sh.print(f"{'':12}{'blocos':>10}{'bytes':>12}")
    sh.print(f"{'total':12}{u.total_blocks:>10}{u.total_blocks * u.block_size:>12}")
    sh.print(f"{'metadados':12}{u.metadata_blocks:>10}{u.metadata_blocks * u.block_size:>12}")
    sh.print(f"{'dados':12}{u.data_blocks:>10}{u.data_bytes:>12}")
    sh.print(f"{'  usados':12}{u.used_blocks:>10}{u.used_bytes:>12}")
    sh.print(f"{'  livres':12}{u.free_blocks:>10}{u.free_bytes:>12}")
    sh.print(f"uso da área de dados: {u.use_percent:.1f}%  (bloco = {u.block_size} B)")


def cmd_info(sh: Shell, args: List[str]) -> None:
    if args:
        raise UsageError()
    sb = sh.fs.superblock
    lo = sb.layout
    created = _dt.datetime.fromtimestamp(sb.created_at).strftime("%d/%m/%Y %H:%M:%S")
    sh.print(f"MiniFS v{sb.version}: superblock (bloco 0)")
    sh.print(f"  arquivo do disco    : {sh.disk_path} ({lo.disk_size} B)")
    sh.print(f"  tamanho do bloco    : {lo.block_size} B")
    sh.print(f"  total de blocos     : {lo.total_blocks}")
    sh.print(f"  bitmap              : blocos {lo.bitmap_start}..{lo.inode_table_start - 1}"
             f" ({lo.bitmap_blocks})")
    sh.print(f"  tabela de inodes    : blocos {lo.inode_table_start}..{lo.data_start - 1}"
             f" ({lo.inode_table_blocks}; {lo.inode_count} inodes de 128 B)")
    sh.print(f"  área de dados       : blocos {lo.data_start}..{lo.total_blocks - 1}"
             f" ({lo.data_blocks})")
    sh.print(f"  maior arquivo       : {lo.max_file_size} B")
    sh.print(f"  formatado em        : {created}")
    sh.print(f"  montagens           : {sb.mount_count}")


def cmd_bitmap(sh: Shell, args: List[str]) -> None:
    if len(args) > 2:
        raise UsageError()
    lo = sh.fs.layout
    start = _int(args[0], "início") if args else 0
    end = _int(args[1], "fim") + 1 if len(args) > 1 else None
    if end is None and not args:
        # Sem argumentos, mostra os metadados e as primeiras linhas da área de dados.
        end = min(lo.total_blocks, (lo.data_start // 64 + 4) * 64)
    if not 0 <= start < lo.total_blocks:
        raise UsageError(f"início deve estar entre 0 e {lo.total_blocks - 1}")
    sh.print("legenda: S=superblock B=bitmap I=inodes #=dado ocupado .=livre")
    sh.print(sh.fs.bitmap.render(start, end))
    u = sh.fs.df()
    sh.print(f"blocos de dados: {u.used_blocks} ocupados, {u.free_blocks} livres")


def cmd_dump(sh: Shell, args: List[str]) -> None:
    if not 1 <= len(args) <= 2:
        raise UsageError()
    block = _int(args[0], "bloco")
    limit = _int(args[1], "bytes") if len(args) > 1 else None
    lo = sh.fs.layout
    lo.check_block(block)
    data = sh.fs.disk.read_block(block)[:limit]
    sh.print(f"bloco {block} (região: {lo.region_of(block)}), "
             f"offset no arquivo: {block * lo.block_size}")
    last = None
    skipped = False
    for off in range(0, len(data), 16):
        chunk = data[off:off + 16]
        # Linhas repetidas consecutivas são resumidas em um único '*'.
        if chunk == last and off + 16 < len(data):
            if not skipped:
                sh.print("*")
                skipped = True
            continue
        last, skipped = chunk, False
        hexpart = " ".join(f"{b:02x}" for b in chunk)
        text = "".join(chr(b) if 32 <= b < 127 else "." for b in chunk)
        sh.print(f"{off:04x}  {hexpart:<47}  |{text}|")


def cmd_dbg_alloc(sh: Shell, args: List[str]) -> None:
    if len(args) != 1:
        raise UsageError()
    blocks = sh.fs.bitmap.allocate(_int(args[0], "quantidade"))
    sh.print(f"blocos alocados: {' '.join(map(str, blocks)) or '(nenhum)'}")


def cmd_dbg_free(sh: Shell, args: List[str]) -> None:
    if not args:
        raise UsageError()
    blocks = [_int(a, "bloco") for a in args]
    sh.fs.bitmap.free(blocks)
    sh.print(f"blocos liberados: {' '.join(map(str, blocks))}")


def _print_info(sh: Shell, info: FileInfo) -> None:
    sh.print(f"  id      : {info.file_id}")
    sh.print(f"  nome    : {info.name}")
    sh.print(f"  tamanho : {info.size} B")
    sh.print(f"  blocos  : {' '.join(map(str, info.blocks)) or '(nenhum)'}")


def cmd_create(sh: Shell, args: List[str]) -> None:
    if len(args) != 1:
        raise UsageError()
    info = sh.fs.create(args[0])
    sh.print(f"arquivo '{info.name}' criado (id {info.file_id})")


def cmd_write(sh: Shell, args: List[str]) -> None:
    if len(args) < 2:
        raise UsageError()
    info = sh.fs.write(args[0], " ".join(args[1:]).encode("utf-8"))
    sh.print(f"{info.size} B gravados em '{info.name}' "
             f"(blocos: {' '.join(map(str, info.blocks)) or '-'})")


def cmd_read(sh: Shell, args: List[str]) -> None:
    if len(args) != 1:
        raise UsageError()
    sh.print(sh.fs.read(args[0]).decode("utf-8", errors="replace"))


def cmd_ls(sh: Shell, args: List[str]) -> None:
    if args:
        raise UsageError()
    files = sh.fs.ls()
    if not files:
        sh.print("(nenhum arquivo)")
        return
    sh.print(f"{'id':>4}  {'tamanho':>8}  {'blocos':>6}  nome")
    for f in files:
        sh.print(f"{f.file_id:>4}  {f.size:>8}  {len(f.blocks):>6}  {f.name}")


def cmd_stat(sh: Shell, args: List[str]) -> None:
    if len(args) != 1:
        raise UsageError()
    _print_info(sh, sh.fs.stat(args[0]))


def cmd_rm(sh: Shell, args: List[str]) -> None:
    if len(args) != 1:
        raise UsageError()
    sh.fs.rm(args[0])
    sh.print(f"arquivo '{args[0]}' removido")


def cmd_help(sh: Shell, args: List[str]) -> None:
    sh.print("comandos disponíveis:")
    for name, cmd in COMMANDS.items():
        sh.print(f"  {cmd.usage:<36} {cmd.help}  [{cmd.owner}]")
    sh.print(f"  {'exit':<36} encerra o programa")


I1, I2, I3 = "Integrante 1", "Integrante 2", "Integrante 3"

COMMANDS: Dict[str, Command] = {
    "format": Command(cmd_format, "format <blocos> [tam_bloco] [inodes]",
                      "cria/zera o disco virtual", I1),
    "df": Command(cmd_df, "df", "espaço total, usado e livre", I1),
    "info": Command(cmd_info, "info", "mostra o superblock", I1),
    "bitmap": Command(cmd_bitmap, "bitmap [inicio] [fim]",
                      "mapa de blocos livres/ocupados", I1),
    "create": Command(cmd_create, "create <nome>", "cria arquivo vazio", I2),
    "ls": Command(cmd_ls, "ls", "lista os arquivos", I2),
    "stat": Command(cmd_stat, "stat <nome>", "metadados do arquivo", I2),
    "rm": Command(cmd_rm, "rm <nome>", "remove arquivo e libera blocos", I2),
    "write": Command(cmd_write, "write <nome> \"conteudo\"",
                     "grava conteúdo no arquivo", I3),
    "read": Command(cmd_read, "read <nome>", "mostra o conteúdo do arquivo", I3),
    "dump": Command(cmd_dump, "dump <bloco> [bytes]",
                    "(depuração) hexdump de um bloco do disco", I1),
    "dbg-alloc": Command(cmd_dbg_alloc, "dbg-alloc <n>",
                         "(depuração) aloca n blocos direto no bitmap", I1),
    "dbg-free": Command(cmd_dbg_free, "dbg-free <bloco> [...]",
                        "(depuração) libera blocos direto no bitmap", I1),
    "help": Command(cmd_help, "help", "esta ajuda", I3),
}


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m minifs",
        description="MiniFS: sistema de arquivos simplificado sobre um disco virtual.",
    )
    parser.add_argument("--disk", default=DEFAULT_DISK,
                        help=f"arquivo do disco virtual (padrão: {DEFAULT_DISK})")
    parser.add_argument("command", nargs=argparse.REMAINDER,
                        help="comando único a executar; sem ele, abre o modo interativo")
    ns = parser.parse_args(argv)

    shell = Shell(ns.disk)
    try:
        if ns.command:
            return 0 if shell.execute(ns.command) else 1
        if sys.stdin.isatty():
            shell.print("MiniFS: digite 'help' para ver os comandos e 'exit' para sair.")
        return shell.repl(sys.stdin)
    except KeyboardInterrupt:
        shell.print()
        return 130
    finally:
        shell.close()
