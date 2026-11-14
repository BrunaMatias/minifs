# Interfaces entre módulos e guia de continuação

Este documento descreve o que já está implementado, o que cabe a cada integrante e onde cada
parte deve ser integrada.

## 1. Implementado pelo Integrante 1

```
cli.py (Shell) ---> fs.py (MiniFS) ---> bitmap.py (Bitmap) ------+
                         |                                       v
                         +---> superblock.py (Superblock)   disk.py (VirtualDisk) ---> minifs.img
                         +---> InodeTable (Integrante 2) --------+
```

| Componente | Interface |
|---|---|
| `VirtualDisk` | `read_block(n)` retorna sempre `block_size` bytes; `write_block(n, data)` completa com zeros e rejeita dados maiores que o bloco; `read_blocks`, `write_blocks`, `sync`, `close`. Escrita imediata no arquivo. |
| `Layout` (`fs.layout`) | `block_size`, `total_blocks`, `inode_count`, `inode_table_start`, `inode_table_blocks`, `data_start`, `data_blocks`, `max_file_size`, `inode_location(i)` retorna `(bloco, offset)`, `is_data_block(b)`. |
| `Bitmap` (`fs.bitmap`) | `allocate(n)` retorna `n` blocos (first-fit, não necessariamente contíguos) ou lança `DiskFullError` sem alterar o bitmap; `free(blocos)` valida tudo antes de liberar e rejeita liberação duplicada ou blocos fora da área de dados; `free_count()`, `is_used(b)`, `used_data_blocks()`. As alterações são gravadas no disco antes do retorno. |
| `MiniFS` | `format`, `mount`, `close`, `df` e os atributos `disk`, `bitmap`, `superblock`, `layout`. |
| `errors.py` | Todas as exceções do projeto, incluindo `NoSuchFileError`, `DuplicateNameError`, `InvalidNameError`, `FileTooLargeError` e `NoFreeInodeError`. |
| `cli.py` | Modo interativo, modo roteiro (entrada padrão) e comando único; `create`, `ls`, `stat`, `rm`, `write` e `read` já chamam os métodos de `MiniFS`. |
| `fs.FileInfo` | `file_id`, `name`, `size`, `blocks`; tipo de retorno de `create`, `stat`, `ls` e `write`. |

Regras de uso:

1. O arquivo `.img` é acessado somente por meio de `fs.disk`.
2. Posições no disco são obtidas de `fs.layout`, por exemplo `inode_location`.
3. Os bits do bitmap são alterados somente por `allocate` e `free`.
4. Erros esperados herdam de `MiniFSError`, que a CLI exibe como `erro: ...`.

## 2. Integrante 2: metadados, create, rm, stat e ls

O formato do registro de 128 bytes está em [LAYOUT_DISCO.md, seção 5](LAYOUT_DISCO.md#5-registro-de-arquivo-inode-128-bytes)
(`layout.INODE_FORMAT = "<B3xIIH2x32s20I"`, `MAX_NAME_LEN = 32`, `DIRECT_REFS = 20`).

Sugestão de implementação em um novo módulo `minifs/inode.py`:

```python
import struct
from .layout import INODE_FORMAT, INODE_SIZE, DIRECT_REFS

@dataclass
class Inode:
    index: int; used: bool; file_id: int; size: int; name: str; blocks: list[int]

    def pack(self) -> bytes:
        refs = self.blocks + [0] * (DIRECT_REFS - len(self.blocks))
        return struct.pack(INODE_FORMAT, int(self.used), self.file_id, self.size,
                           len(self.blocks), self.name.encode("utf-8"), *refs)

class InodeTable:
    # load(disk, layout): lê os blocos da tabela e decodifica os registros
    # find(name), find_free(): busca por nome e por registro livre
    # save(inode): lê o bloco de inode_location(i), substitui os 128 bytes e regrava o bloco
```

Pontos de integração em [minifs/fs.py](../minifs/fs.py):

- Em `MiniFS.__init__`, carregar a tabela (`self.inodes = InodeTable.load(disk, layout)`).
  O format já deixa todos os registros com `used = 0`.
- Implementar `create`, `rm`, `stat` e `ls`.
- `file_id`: usar um contador `max(ids existentes) + 1` calculado no mount, para que os
  identificadores não se repitam.
- Validação de nome (`InvalidNameError`): não vazio, até 32 bytes em UTF-8, sem `\0` e sem `/`.
- No `rm`, gravar o inode com `used = 0` antes de chamar `bitmap.free(blocos)`. Em caso de queda
  entre as duas etapas, o pior cenário é um bloco ocupado sem dono, nunca um bloco referenciado e
  marcado como livre.
- Opcional: incluir inodes usados e livres no `df` (novos campos em `DiskUsage`).

## 3. Integrante 3: write, read, CLI, integração e testes

Sugestão de `write(name, data)` que não altera nada em caso de erro:

```python
bs = self.layout.block_size
if len(data) > self.layout.max_file_size:
    raise FileTooLargeError(...)
inode = ...  # NoSuchFileError se não existir
need = ceil(len(data) / bs)
old = inode.blocks
extra = self.bitmap.allocate(max(0, need - len(old)))
blocks = old[:need] + extra
for i, b in enumerate(blocks):
    self.disk.write_block(b, data[i*bs:(i+1)*bs])
inode.size, inode.blocks = len(data), blocks  # gravar o inode
self.bitmap.free(old[need:])
```

`read(name)`: `b"".join(self.disk.read_block(b) for b in inode.blocks)[:inode.size]`.

Na CLI ([minifs/cli.py](../minifs/cli.py)), as funções `cmd_create`, `cmd_write`, `cmd_read`,
`cmd_ls`, `cmd_stat` e `cmd_rm` já existem e podem ter a saída ajustada. Novos comandos são
registrados no dicionário `COMMANDS`. O comando `dump <bloco>` permite conferir os inodes gravados
(por exemplo, `dump 2 128` exibe os inodes 0 e 1). Os comandos `dbg-*` podem ser mantidos como
ferramentas de depuração ou removidos na versão final.

## 4. Testes a ajustar

- Remover `test_operacoes_dos_outros_integrantes_ainda_pendentes` ([tests/test_fs.py](../tests/test_fs.py))
  e `test_comando_pendente_informa_responsavel` ([tests/test_cli.py](../tests/test_cli.py)).
- Adicionar os casos exigidos pelo enunciado: nome duplicado, arquivo inexistente em `read`, `stat` e
  `rm`, arquivo acima do limite (`> 20 x bs`), disco cheio via `write`, tabela de inodes cheia,
  reutilização de blocos após `rm` e persistência do conteúdo entre processos (usar `CliProcessTest`
  como modelo, que executa `python -m minifs` em subprocessos).

Execução: `python -m unittest discover -s tests -t . -v`

## 5. Controle de versão

Repositório: https://github.com/BrunaMatias/minifs

```bash
git clone https://github.com/BrunaMatias/minifs.git
git checkout -b integrante2-inodes      # ou integrante3-rw-cli
# ao concluir: git push -u origin <branch> e abrir um pull request para main
```

## 6. Checklist da demonstração final (seção 9 do enunciado)

| Exigência | Comando |
|---|---|
| formatar o disco | `format 2048` |
| criar arquivo | `create arquivo.txt` |
| escrever e ler | `write arquivo.txt "Conteudo de teste"` e `read arquivo.txt` |
| listar | `ls`, `stat arquivo.txt`, `df` |
| remover | `rm arquivo.txt` |
| reutilização de blocos liberados | `bitmap` antes e depois do `rm`, seguido de um `write` que ocupa os mesmos blocos (`stat`) |
| persistência | `exit`, nova execução do programa, `ls`, `read` e `info` (contador de montagens) |
