# MiniFS: sistema de arquivos simplificado

Trabalho prático de Sistemas Operacionais (UFSCar). O MiniFS é um sistema de arquivos que funciona
dentro de um único arquivo binário (o disco virtual), dividido em blocos de tamanho fixo, com
superblock, bitmap de blocos livres, tabela de metadados (inodes) com alocação indexada e
persistência entre execuções.

## Requisitos

- Python 3.8 ou superior (testado com 3.14), apenas com a biblioteca padrão.
- Não há etapa de compilação.
- No Windows, se o comando `python` não for reconhecido, use `py -3` no lugar dele
  (por exemplo, `py -3 -m minifs format 2048`).

## Execução

Os comandos são executados a partir da pasta raiz do projeto.

```bash
# modo interativo
python -m minifs

# um comando por execução (disco padrão: ./minifs.img)
python -m minifs format 2048
python -m minifs df
python -m minifs info

# outro arquivo de disco
python -m minifs --disk teste.img format 4096 1024 128

# roteiro de comandos lido de um arquivo
python -m minifs < roteiro.txt
```

### Comandos

| Comando | Descrição | Responsável | Situação |
|---|---|---|---|
| `format <blocos> [tam_bloco] [inodes]` | cria/zera o disco (padrão: blocos de 512 B, 64 inodes) | Integrante 1 | concluído |
| `df` | espaço total, de metadados, usado e livre | Integrante 1 | concluído |
| `info` | conteúdo do superblock e layout do disco | Integrante 1 | concluído |
| `bitmap [inicio] [fim]` | mapa de blocos livres e ocupados | Integrante 1 | concluído |
| `dump <bloco> [bytes]` | depuração: hexdump de um bloco | Integrante 1 | concluído |
| `dbg-alloc <n>`, `dbg-free <b...>` | depuração: aloca/libera direto no bitmap | Integrante 1 | concluído |
| `create <nome>` | cria arquivo vazio | Integrante 2 | concluído |
| `ls` | lista arquivos | Integrante 2 | concluído |
| `stat <nome>` | metadados do arquivo | Integrante 2 | concluído |
| `rm <nome>` | remove arquivo e libera os blocos | Integrante 2 | concluído |
| `write <nome> "conteudo"` | grava conteúdo | Integrante 3 | concluído |
| `read <nome>` | lê conteúdo | Integrante 3 | concluído |
| `help`, `exit` | ajuda e encerramento | Integrante 3 | concluído |

A parte do Integrante 3 inclui a escrita e leitura de arquivos em blocos de dados, o controle de
limite de tamanho por inode e a integração da CLI com a fachada `MiniFS`.

### Operações de leitura e escrita

O comando `write` valida o nome do arquivo, rejeita conteúdos acima do limite do sistema
(`max_file_size = 20 x tamanho_do_bloco`), aloca blocos extras quando necessário e reaproveita
blocos livres após reduzir o tamanho do arquivo. O comando `read` recupera o conteúdo armazenado
em disco e devolve apenas os bytes do arquivo, respeitando `size` do inode.

A CLI aceita tanto execução em modo interativo quanto por script via `stdin` e comandos únicos por
linha de comando. O comando `help` lista operações disponíveis e `exit` encerra o shell.

Os comandos `dbg-alloc` e `dbg-free` alteram apenas o bitmap, sem inode associado aos blocos.
Devem ser usados somente em discos de teste.

## Testes

```bash
python -m unittest discover -s tests -t . -v
```

Cobrem layout, disco virtual, superblock, bitmap, operações de metadados e CLI. Verificam a
persistência entre processos, a reutilização de inodes e a liberação de blocos pelo `rm`.

## Documentação

- [docs/RELATORIO.pdf](docs/RELATORIO.pdf) (fonte em [docs/RELATORIO.md](docs/RELATORIO.md)): relatório do grupo (layout do disco, estruturas de dados,
  operações, tratamento de erros, análise de disco cheio e reutilização de blocos, testes).
- [docs/LAYOUT_DISCO.md](docs/LAYOUT_DISCO.md): especificação byte a byte do formato em disco.
- [docs/INTERFACES.md](docs/INTERFACES.md): contrato entre os módulos.

## Estrutura

```
minifs/
  errors.py      exceções usadas por todo o projeto
  layout.py      constantes do formato e cálculo das regiões do disco
  disk.py        VirtualDisk: leitura e escrita de blocos no arquivo hospedeiro
  superblock.py  Superblock: serialização e validação do bloco 0
  bitmap.py      Bitmap: blocos livres/ocupados e alocador first-fit
  inode.py       Inode e InodeTable: registros e referências aos blocos dos arquivos
  fs.py          MiniFS: format, mount, df e operações de arquivo
  cli.py         Shell: interface de comandos
tests/           testes automatizados (unittest)
docs/
  RELATORIO.pdf / .md                       relatório do grupo (documento de entrega)
  LAYOUT_DISCO.md                           especificação do formato em disco
  INTERFACES.md                             contrato entre módulos e guia para os Integrantes 2 e 3
  relatorio/integrante1.md                  rascunho detalhado: disco, superblock e bitmap
  relatorio/integrante2.md                  rascunho detalhado: inodes e operações de metadados
```

## Divisão do trabalho

| Integrante | Responsabilidade | Situação |
|---|---|---|
| 1 | Disco virtual, superblock e bitmap de blocos | concluído |
| 2 | Metadados dos arquivos, referências aos blocos e create/rm/stat/ls | concluído |
| 3 | Interface de comandos, read/write, integração e testes | concluído |

O contrato de integração está em [docs/INTERFACES.md](docs/INTERFACES.md).
