# MiniFS: sistema de arquivos simplificado

Relatório do trabalho prático de Sistemas Operacionais (UFSCar). Referência conceitual:
Tanenbaum, *Sistemas Operacionais Modernos*, capítulos sobre sistemas de arquivos e gerenciamento
de espaço em disco. A especificação byte a byte do formato está em [LAYOUT_DISCO.md](LAYOUT_DISCO.md).

## 1. Visão geral

O MiniFS é escrito em Python 3, sem bibliotecas externas, e funciona dentro de um único arquivo
binário do sistema hospedeiro (o disco virtual, padrão `minifs.img`). Os arquivos do MiniFS nunca
viram arquivos separados no hospedeiro: nomes, metadados e conteúdo ficam todos dentro da imagem.

```
cli.py (Shell) ---> fs.py (MiniFS) ---> bitmap.py (Bitmap) -----+
                         |                                      v
                         +---> superblock.py (Superblock)   disk.py (VirtualDisk) ---> minifs.img
                         +---> inode.py (InodeTable) ----------+
```

| Módulo | Responsabilidade |
|---|---|
| `disk.py` | `VirtualDisk`: única classe que acessa a imagem; lê e grava blocos inteiros |
| `layout.py` | constantes do formato e cálculo das regiões a partir dos parâmetros do `format` |
| `superblock.py` | serialização e validação do bloco 0 |
| `bitmap.py` | mapa de blocos livres/ocupados e alocador *first-fit* |
| `inode.py` | registros de arquivo (inodes) e suas referências aos blocos |
| `fs.py` | fachada `MiniFS`: `format`, `mount`, `create`, `write`, `read`, `rm`, `stat`, `ls`, `df` |
| `cli.py` | interface de comandos (interativa, roteiro pela entrada padrão ou comando único) |

## 2. Layout do disco virtual

O disco é um vetor de N blocos de tamanho fixo (512 B por padrão; 1, 2 ou 4 KiB opcionais). O bloco
`b` começa no deslocamento `b x bs` da imagem. As regiões são contíguas e calculadas a partir de N,
do tamanho do bloco (bs) e do número de inodes:

| Região | Blocos | Com `format 2048` |
|---|---|---|
| Superblock | 0 | 1 bloco |
| Bitmap | 1 .. B, com B = ⌈N / (8 x bs)⌉ | 1 bloco |
| Tabela de inodes | 1+B .. D-1, com T = ⌈inodes / (bs/128)⌉ | 16 blocos (64 x 128 B) |
| Dados | D = 1+B+T .. N-1 | 2030 blocos (991 KiB) |

```
 0     1     2 ............ 17   18 ............................... 2047
+-----+-----+-----------------+------------------------------------+
| SB  | BMP | tabela de inodes|          blocos de dados           |
+-----+-----+-----------------+------------------------------------+
```

Os metadados ocupam 18 de 2048 blocos (0,9%). O `format` cria a imagem com N x bs bytes zerados,
grava o bitmap e, por último, o superblock. Um `format` interrompido deixa o disco sem assinatura
válida, e o próximo `mount` o rejeita em vez de usá-lo.

## 3. Estruturas de dados

**Superblock (bloco 0, 64 bytes).** Guarda a assinatura `MINIFS01`, a versão do formato, o tamanho
do bloco, o total de blocos, o início e o tamanho de cada região, o número e o tamanho dos inodes,
o número de referências por inode (20), a data do `format`, um contador de montagens e um CRC-32
dos 60 bytes anteriores. No `mount`, o MiniFS confere a assinatura, o CRC, a coerência das regiões
(recalculadas a partir dos parâmetros) e o tamanho da imagem. Qualquer falha recusa o disco.

**Bitmap.** Um bit por bloco do disco (1 = ocupado, 0 = livre), no byte `b / 8`, posição `b % 8`.
O bitmap cobre também os blocos de metadados, que ficam sempre em 1; assim o número do bit é o
próprio número do bloco e o alocador nunca entrega um bloco reservado. O bitmap fica inteiro em
memória e cada alteração é gravada imediatamente (*write-through*), regravando só os blocos do
bitmap que mudaram. Um contador de blocos livres permite responder ao `df` em O(1).

**Inode (registro de arquivo, 128 bytes).** Cada bloco de 512 B guarda 4 inodes.

| Campo | Tamanho | Significado |
|---|---|---|
| `used` | 1 B | 0 = registro livre, 1 = arquivo existente |
| `file_id` | 4 B | identificador único do arquivo |
| `size` | 4 B | tamanho do conteúdo em bytes |
| `n_blocks` | 2 B | quantidade de referências válidas |
| `name` | 32 B | nome em UTF-8, completado com `\0` |
| `blocks[20]` | 80 B | números dos blocos de dados, na ordem do conteúdo |

A tabela de inodes faz também o papel de diretório (único, plano): o nome fica no próprio registro.

**Alocação indexada.** Cada inode lista os blocos que o arquivo usa, na ordem do conteúdo. Os blocos
não precisam ser contíguos, então não há fragmentação externa; a única perda é a fragmentação
interna no último bloco de cada arquivo. Com 20 referências diretas, o maior arquivo tem
20 x bs bytes (10 KiB com blocos de 512 B).

## 4. Operações

| Comando | Funcionamento |
|---|---|
| `format <blocos> [bs] [inodes]` | cria a imagem zerada, o bitmap e o superblock |
| `create <nome>` | valida o nome (1 a 32 bytes, sem `/` nem `\0`), recusa nome duplicado e ocupa um inode livre com tamanho 0 e nenhum bloco |
| `write <nome> "conteúdo"` | substitui o conteúdo do arquivo (detalhes abaixo) |
| `read <nome>` | concatena os blocos listados no inode e devolve apenas os `size` primeiros bytes |
| `ls` | lista os inodes em uso (id, tamanho, blocos, nome) |
| `stat <nome>` | mostra id, nome, tamanho e a lista de blocos do arquivo |
| `rm <nome>` | libera o inode e, em seguida, devolve os blocos ao bitmap |
| `df` | blocos e bytes totais, de metadados, usados e livres |

Comandos auxiliares: `info` (superblock e layout), `bitmap` (mapa de blocos), `dump` (hexdump de
um bloco), `help` e `exit`.

**write.** Primeiro verifica o arquivo e o limite de tamanho (`FileTooLargeError`). Depois calcula
quantos blocos o novo conteúdo precisa, reaproveita os blocos que o arquivo já tem e pede ao bitmap
apenas os que faltam. Como a alocação acontece antes de qualquer gravação, um `write` recusado por
falta de espaço (`DiskFullError`) deixa o arquivo e o bitmap como estavam. Em seguida grava os
blocos de dados, atualiza `size` e `blocks` no inode e, se o novo conteúdo for menor, libera os
blocos que sobraram.

**rm.** O inode é marcado como livre e gravado antes de os blocos voltarem ao bitmap. Se o programa
for interrompido entre as duas etapas, sobram no máximo blocos ocupados sem dono, mas nunca um
arquivo apontando para blocos que outro arquivo pode receber. O registro livre conserva o último
`file_id`, de modo que os ids continuam crescendo mesmo após remontar o disco.

**Interface.** A CLI aceita modo interativo (`python -m minifs`), roteiro pela entrada padrão
(`python -m minifs < roteiro.txt`) e comando único (`python -m minifs read a.txt`). Os argumentos
são separados como no shell, portanto aspas agrupam um conteúdo com espaços. Erros esperados
(subclasses de `MiniFSError`) aparecem como `erro: ...` e o programa continua funcionando.

## 5. Persistência e tratamento de erros

Todo o estado (superblock, bitmap, inodes e dados) é gravado na imagem durante a própria operação.
Ao executar o programa de novo, o `mount` lê o superblock, valida o disco, carrega o bitmap e a
tabela de inodes e confere se nenhum arquivo referencia um bloco marcado como livre. O contador de
montagens no superblock é incrementado a cada execução e serve como evidência simples de
persistência (comando `info`).

| Situação | Comportamento |
|---|---|
| arquivo inexistente (`read`, `write`, `stat`, `rm`) | `erro: arquivo 'x' não encontrado` |
| nome duplicado no `create` | `erro: já existe um arquivo com o nome 'x'` |
| disco cheio no `write` | `erro: disco cheio: k bloco(s) solicitado(s), m livre(s)`, sem alterar nada |
| arquivo acima do limite | `erro: arquivo 'x' excede o limite de 10240 bytes` |
| tabela de inodes cheia | `erro: tabela de inodes cheia` |
| imagem inexistente, corrompida ou de outro formato | disco recusado no `mount` com mensagem explicativa |

## 6. Análise: disco cheio e reutilização de blocos

**O que acontece quando o disco fica cheio?** O contador de blocos livres chega a zero e qualquer
pedido maior que o espaço disponível lança `DiskFullError`. Como o bitmap verifica a quantidade
antes de marcar qualquer bit, e o `write` aloca antes de gravar, a operação recusada não tem efeito
colateral: o arquivo mantém o conteúdo anterior e o `df` mostra os mesmos números. Pedidos menores,
que caibam nos blocos restantes, continuam sendo atendidos. Existe ainda um segundo limite,
independente do espaço: com os 64 inodes ocupados não é possível criar arquivos, mesmo que existam
blocos livres.

**Como os blocos liberados são reutilizados?** O `rm`, ou um `write` que diminui o arquivo, zera os
bits dos blocos no bitmap. Como o alocador *first-fit* sempre começa a busca em `data_start`, os
blocos liberados de número mais baixo são entregues antes da área nunca usada. Exemplo da
demonstração: `a.txt` ocupa o bloco 18 e `b` o bloco 19; após `rm a.txt`, o próximo `write`
recebe novamente o bloco 18. Isso vale também depois de fechar e reabrir o programa, porque o
bitmap está no disco. O conteúdo antigo não é apagado na liberação; o bloco só é sobrescrito quando
reutilizado, e o campo `size` do inode impede que restos de conteúdo apareçam no `read`.

## 7. Testes

Os testes automatizados usam apenas `unittest` (`python -m unittest discover -s tests -t . -v`) e
cobrem:

- **layout:** regiões contíguas e sem sobreposição para vários tamanhos, parâmetros inválidos;
- **disco virtual:** blocos zerados após o `format`, isolamento entre blocos vizinhos, acesso fora
  dos limites, persistência após fechar e reabrir;
- **superblock:** serialização nos offsets documentados, assinatura inválida, CRC e regiões adulteradas;
- **bitmap:** *first-fit*, alocação não contígua, reutilização de blocos liberados, disco cheio sem
  efeito colateral, liberação duplicada, proteção dos metadados;
- **metadados:** nomes inválidos e duplicados, tabela cheia, `rm` que libera os blocos e os
  devolve ao alocador, reutilização de inodes com novo id, disco com inode inconsistente;
- **CLI e persistência:** o programa é executado em subprocessos separados para comprovar que
  arquivos, bitmap e contador de montagens sobrevivem ao encerramento; mensagens de erro e código
  de saída.

O roteiro da demonstração em vídeo exercita, de ponta a ponta, `format`, `create`, `write`, `read`,
`ls`, `stat`, `df`, `rm`, a reutilização do bloco liberado e a persistência após reiniciar o programa.

## 8. Divisão do trabalho

| Integrante | Responsabilidade |
|---|---|
| 1 | disco virtual, layout, superblock e bitmap de blocos |
| 2 | inodes, referências aos blocos e `create`/`rm`/`stat`/`ls` |
| 3 | `write`/`read`, interface de comandos, integração e testes |

Todos participaram da definição do formato em disco e das interfaces entre os módulos
([INTERFACES.md](INTERFACES.md)).
