# Interfaces entre módulos e guia de continuação

Este documento descreve o que já está implementado, o que cabe a cada integrante e onde cada
parte deve ser integrada.

## 1. Implementado pelo Integrante 1

```
cli.py (Shell) ---> fs.py (MiniFS) ---> bitmap.py (Bitmap) ------+
                         |                                       v
                         +---> superblock.py (Superblock)   disk.py (VirtualDisk) ---> minifs.img
                         +---> inode.py (InodeTable) -----------+
```

| Componente | Interface |
|---|---|
| `VirtualDisk` | `read_block(n)` retorna sempre `block_size` bytes; `write_block(n, data)` completa com zeros e rejeita dados maiores que o bloco; `read_blocks`, `write_blocks`, `sync`, `close`. Escrita imediata no arquivo. |
| `Layout` (`fs.layout`) | `block_size`, `total_blocks`, `inode_count`, `inode_table_start`, `inode_table_blocks`, `data_start`, `data_blocks`, `max_file_size`, `inode_location(i)` retorna `(bloco, offset)`, `is_data_block(b)`. |
| `Bitmap` (`fs.bitmap`) | `allocate(n)` retorna `n` blocos (first-fit, não necessariamente contíguos) ou lança `DiskFullError` sem alterar o bitmap; `free(blocos)` valida tudo antes de liberar e rejeita liberação duplicada ou blocos fora da área de dados; `free_count()`, `is_used(b)`, `used_data_blocks()`. As alterações são gravadas no disco antes do retorno. |
| `MiniFS` | `format`, `mount`, `close`, `df`, `create`, `rm`, `stat`, `ls` e os atributos `disk`, `bitmap`, `superblock`, `layout`, `inodes`. |
| `errors.py` | Todas as exceções do projeto, incluindo `NoSuchFileError`, `DuplicateNameError`, `InvalidNameError`, `FileTooLargeError` e `NoFreeInodeError`. |
| `cli.py` | Modo interativo, modo roteiro (entrada padrão) e comando único; `create`, `ls`, `stat`, `rm`, `write` e `read` já chamam os métodos de `MiniFS`. |
| `fs.FileInfo` | `file_id`, `name`, `size`, `blocks`; tipo de retorno de `create`, `stat`, `ls` e `write`. |

Regras de uso:

1. O arquivo `.img` é acessado somente por meio de `fs.disk`.
2. Posições no disco são obtidas de `fs.layout`, por exemplo `inode_location`.
3. Os bits do bitmap são alterados somente por `allocate` e `free`.
4. Erros esperados herdam de `MiniFSError`, que a CLI exibe como `erro: ...`.

## 2. Metadados e operações do Integrante 2

O formato do registro de 128 bytes está em [LAYOUT_DISCO.md, seção 5](LAYOUT_DISCO.md#5-registro-de-arquivo-inode-128-bytes)
(`layout.INODE_FORMAT = "<B3xIIH2x32s20I"`, `MAX_NAME_LEN = 32`, `DIRECT_REFS = 20`).

O [módulo de inodes](../minifs/inode.py) carrega a tabela ao montar a imagem. O `format` deixa todos
os registros livres. `create` valida o nome (1 a 32 bytes UTF-8, sem NUL nem `/`), verifica duplicidade e
grava um inode vazio. `stat` e `ls` retornam `FileInfo`. `rm` persiste a remoção do inode antes de
liberar os blocos no bitmap. O registro livre conserva o `file_id` para a sequência de ids continuar
após nova montagem, mesmo se o último arquivo criado tiver sido removido.

| Interface de `fs.inodes` | Uso |
|---|---|
| `find(name)` | Busca pelo nome, retornando um `Inode` editável ou `None`. |
| `require(name)` | Busca pelo nome, lançando `NoSuchFileError` se ausente. |
| `save(inode)` | Persiste o registro no seu slot, identificado por `inode.index`. Em `write`, atualize `size` e `blocks` juntos. |
| `iter_used()` | Percorre os inodes ativos na ordem dos slots. |

## 3. Integrante 3: write, read, CLI, integração e testes

Sequência sugerida de `write(name, data)`. Verifique o tamanho e reserve os blocos adicionais
antes de iniciar a escrita para tratar arquivo acima do limite e disco cheio.

```python
inode = self.inodes.require(name)
bs = self.layout.block_size
if len(data) > self.layout.max_file_size:
    raise FileTooLargeError(...)
need = (len(data) + bs - 1) // bs
old = inode.blocks
extra = self.bitmap.allocate(max(0, need - len(old)))
blocks = old[:need] + extra
for i, b in enumerate(blocks):
    self.disk.write_block(b, data[i*bs:(i+1)*bs])
inode.size, inode.blocks = len(data), blocks
self.inodes.save(inode)
self.bitmap.free(old[need:])
return self.stat(name)
```

Em `read(name)`, obtenha o inode com `self.inodes.require(name)` e retorne
`b"".join(self.disk.read_block(b) for b in inode.blocks)[:inode.size]`.

Na CLI ([minifs/cli.py](../minifs/cli.py)), as funções `cmd_create`, `cmd_write`, `cmd_read`,
`cmd_ls`, `cmd_stat` e `cmd_rm` já existem e podem ter a saída ajustada. Novos comandos são
registrados no dicionário `COMMANDS`. O comando `dump <bloco>` permite conferir os inodes gravados.
Com `format 2048`, `dump 2 128` exibe o primeiro inode. Os comandos `dbg-*` podem ser mantidos como
ferramentas de depuração ou removidos na versão final.

## 4. Testes a ajustar

- Os testes de metadados já verificam nome duplicado, tabela de inodes cheia, arquivo inexistente
  em `stat` e `rm`, persistência e reutilização de blocos após `rm`.
- Ao integrar `read` e `write`, acrescentar os casos de arquivo inexistente em `read`, arquivo
  acima do limite (`> 20 x bs`), disco cheio via `write` e persistência do conteúdo entre processos.
  O `CliProcessTest` executa `python -m minifs` em subprocessos e pode servir de modelo.

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
