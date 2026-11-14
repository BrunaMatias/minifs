# MiniFS: sistema de arquivos simplificado

Trabalho prático de Sistemas Operacionais (UFSCar). O MiniFS é um sistema de arquivos que funciona
dentro de um único arquivo binário (o disco virtual), dividido em blocos de tamanho fixo, com
superblock, bitmap de blocos livres, tabela de metadados (inodes) com alocação indexada e
persistência entre execuções.

## Requisitos

- Python 3.8 ou superior (testado com 3.14), apenas com a biblioteca padrão.
- Não há etapa de compilação.

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
| `create <nome>` | cria arquivo vazio | Integrante 2 | pendente |
| `ls` | lista arquivos | Integrante 2 | pendente |
| `stat <nome>` | metadados do arquivo | Integrante 2 | pendente |
| `rm <nome>` | remove arquivo e libera os blocos | Integrante 2 | pendente |
| `write <nome> "conteudo"` | grava conteúdo | Integrante 3 | pendente |
| `read <nome>` | lê conteúdo | Integrante 3 | pendente |
| `help`, `exit` | ajuda e encerramento | Integrante 3 | versão básica |

Os comandos pendentes já estão registrados na CLI e informam o integrante responsável até serem
implementados.

Os comandos `dbg-alloc` e `dbg-free` alteram apenas o bitmap, sem inode associado aos blocos.
Devem ser usados somente em discos de teste.

## Testes

```bash
python -m unittest discover -s tests -t . -v
```

Cobrem layout, disco virtual, superblock (incluindo detecção de corrupção), bitmap (first-fit,
reutilização de blocos liberados, disco cheio, liberação duplicada), persistência entre montagens e
entre processos, e a CLI.

## Estrutura

```
minifs/
  errors.py      exceções usadas por todo o projeto
  layout.py      constantes do formato e cálculo das regiões do disco
  disk.py        VirtualDisk: leitura e escrita de blocos no arquivo hospedeiro
  superblock.py  Superblock: serialização e validação do bloco 0
  bitmap.py      Bitmap: blocos livres/ocupados e alocador first-fit
  fs.py          MiniFS: format, mount, df e operações de arquivo
  cli.py         Shell: interface de comandos
tests/           testes automatizados (unittest)
docs/
  LAYOUT_DISCO.md                  especificação do formato em disco
  INTERFACES.md                    contrato entre módulos e guia para os Integrantes 2 e 3
  relatorio/integrante1.md         seção do relatório: disco, superblock e bitmap
  video/roteiro_integrante1.md     roteiro da parte do Integrante 1 no vídeo
```

## Divisão do trabalho

| Integrante | Responsabilidade | Situação |
|---|---|---|
| 1 | Disco virtual, superblock e bitmap de blocos | concluído |
| 2 | Metadados dos arquivos, referências aos blocos e create/rm/stat/ls | pendente |
| 3 | Interface de comandos, read/write, integração e testes | pendente |

Os Integrantes 2 e 3 devem começar por [docs/INTERFACES.md](docs/INTERFACES.md).
