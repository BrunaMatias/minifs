# Relatório: disco virtual, superblock e bitmap (Integrante 1)

Seção do documento do grupo, complementada pelas seções dos Integrantes 2 (metadados) e 3 (read/write e CLI).

## 1. Disco virtual

O disco do MiniFS é um único arquivo binário do sistema hospedeiro (padrão `minifs.img`),
tratado como um vetor de N blocos de tamanho fixo (512 B por padrão; 1, 2 ou 4 KiB opcionais).
A classe `VirtualDisk` é a única que acessa esse arquivo. Ela oferece apenas leitura e escrita de
blocos inteiros (`read_block(n)` / `write_block(n, dados)`), como um driver faz com os setores
de um disco real (Tanenbaum, cap. 4 e 5). Acessos fora de `0..N-1` geram erro, e nenhuma escrita
ultrapassa o limite do bloco. Os arquivos do MiniFS não são armazenados como arquivos separados no hospedeiro:
todo o conteúdo fica dentro da imagem.

O `format` cria o arquivo com N x bs bytes zerados. Com isso a tabela de inodes já nasce com todos
os registros livres. Depois o comando grava o bitmap e, por último, o superblock. Se o `format`
for interrompido, o disco fica sem assinatura válida e é rejeitado no próximo `mount`, em vez de
parecer um disco formatado.

## 2. Layout do disco

As regiões são contíguas e calculadas a partir de N, bs e do número de inodes:

| Região | Blocos | Tamanho com `format 2048` |
|---|---|---|
| Superblock | 0 | 1 bloco |
| Bitmap | 1 .. B, com B = ⌈N / 8bs⌉ | 1 bloco (2048 bits = 256 B) |
| Tabela de inodes | 1+B .. D-1, com T = ⌈inodes / (bs/128)⌉ | 16 blocos (64 x 128 B) |
| Dados | D = 1+B+T .. N-1 | 2030 blocos (991 KiB) |

```
 0     1     2 ............ 17   18 ............................... 2047
+-----+-----+-----------------+------------------------------------+
| SB  | BMP | tabela de inodes|          blocos de dados           |
+-----+-----+-----------------+------------------------------------+
```

Os metadados consomem 18 de 2048 blocos (0,9%). O bitmap cresce 1 bloco a cada 4096 blocos
de disco (com bs = 512).

## 3. Superblock

O superblock ocupa os primeiros 64 bytes do bloco 0. Ele guarda a assinatura `MINIFS01`, a versão
do formato, o tamanho do bloco, o total de blocos, o início e o tamanho de cada região, o número de
inodes, o tamanho do inode (128 B), o número de referências por inode (20), a data do `format`, um
contador de montagens e um CRC-32 dos 60 bytes anteriores. Todos os inteiros são little-endian.

Como o tamanho do bloco ainda não é conhecido no `mount`, o superblock fica sempre no deslocamento 0 e
é lido antes de tudo. Há quatro verificações: (i) assinatura, para reconhecer um disco MiniFS;
(ii) CRC, para detectar corrupção; (iii) recálculo das regiões a partir dos parâmetros e comparação
com o que está gravado; (iv) tamanho do arquivo igual a N x bs. Se qualquer uma falhar, o disco é
recusado com uma mensagem clara, e o programa não segue usando dados inconsistentes. O contador
de montagens é incrementado e regravado a cada `mount`. Ele serve como evidência simples de persistência.

## 4. Bitmap e gerenciamento de blocos

O bitmap usa 1 bit por bloco do disco (bit `b % 8` do byte `b / 8`; 1 = ocupado, 0 = livre).
Ele cobre também os blocos de metadados, que ficam sempre em 1. Assim o número do bit é o próprio número do
bloco e o alocador nunca entrega um bloco reservado. Os bits que sobram no fim do último byte também ficam em 1.
No `mount`, se algum bloco de metadados aparecer como livre, o bitmap é considerado corrompido.

Um bitmap ocupa N/8 bytes, enquanto uma lista encadeada de blocos livres pode ocupar mais quando o
disco está vazio. Ele também permite procurar blocos livres sem acessar o disco, porque fica inteiro em
memória (Tanenbaum, gerenciamento de espaço em disco, cap. 4). Toda alteração é gravada logo (*write-through*), e só os blocos do bitmap
que mudaram são regravados. Um contador de blocos livres em memória, recalculado no `mount`, faz o `df` responder em O(1).

**Alocação.** A política é *first-fit*: a busca começa em `data_start` e pega os primeiros blocos com bit 0.
Bytes com valor `0xFF` (8 blocos ocupados) são pulados de uma vez. Como a alocação do MiniFS é
indexada (o inode guarda a lista de blocos), os blocos não precisam ser contíguos. Por isso
não existe fragmentação externa: qualquer conjunto de blocos livres atende a qualquer pedido.
A única perda é a fragmentação interna no último bloco de cada arquivo (em média bs/2).

**Atomicidade.** `allocate(n)` verifica primeiro se há n blocos livres. Se não houver, lança
`DiskFullError` sem alterar nada. `free(blocos)` valida todos os blocos antes de liberar
(não aceita bloco de metadados, bloco fora do disco nem bloco já livre). Assim, uma operação que
falha nunca deixa o bitmap pela metade.

## 5. Análise: disco cheio e reutilização de blocos

**O que acontece quando o disco fica cheio?** O contador de blocos livres chega a zero, e qualquer
`allocate` que peça mais blocos do que os disponíveis lança `DiskFullError`, sem efeitos colaterais.
A interface mostra `erro: disco cheio: k bloco(s) solicitado(s), m livre(s)`, e o programa continua funcionando.
Um pedido que caiba nos blocos restantes ainda é atendido, e o `df` mostra 100% de uso. Pela interface
definida para o `write`, os blocos que faltam são alocados antes de gravar dados ou alterar o inode,
de modo que um `write` recusado por falta de espaço mantém o arquivo como estava. Existe ainda um segundo
limite, independente do espaço: a tabela de inodes. Quando os 64 registros estão ocupados, não é possível criar
arquivos mesmo com blocos livres (`NoFreeInodeError`).

**Como os blocos liberados são reutilizados?** O `rm` (ou um `write` que encolhe o arquivo) chama
`free`, que zera os bits correspondentes. Como a busca *first-fit* sempre recomeça em `data_start`,
os blocos liberados com menor número são os primeiros a serem entregues na próxima alocação, antes
da área nunca usada. Exemplo dos testes: alocam-se os blocos 18 a 22, liberam-se 19 e 20, e o pedido
seguinte de 3 blocos recebe `19, 20, 23`. Isso continua valendo depois de fechar e reabrir o programa,
porque o bitmap fica no disco. Os dados antigos não são apagados na liberação. O bloco só é sobrescrito
quando é reutilizado, e o `size` do inode impede ler restos de conteúdo.

## 6. Testes desta parte

São 58 testes automatizados (`python -m unittest discover -s tests -t .`), sem bibliotecas externas. Eles cobrem:
- layout: regiões contíguas e sem sobreposição para vários tamanhos; limites e parâmetros inválidos;
- disco virtual: blocos zerados após o `format`, isolamento entre blocos vizinhos, acesso fora dos limites,
  persistência após fechar e reabrir;
- superblock: serialização nos offsets documentados, assinatura inválida, CRC e regiões adulteradas;
- bitmap: first-fit, alocação não contígua, reutilização de blocos liberados, disco cheio sem
  efeito colateral, recuperação após liberar, double free, proteção dos metadados, bitmap com mais de um bloco;
- persistência: o estado do bitmap e o contador de montagens se mantêm entre montagens e entre
  processos diferentes (a CLI é executada em subprocessos separados).
