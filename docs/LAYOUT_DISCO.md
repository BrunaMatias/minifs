# Especificação do formato em disco (MiniFS v1)

Referência do formato binário, implementado em [minifs/layout.py](../minifs/layout.py),
[minifs/superblock.py](../minifs/superblock.py) e [minifs/bitmap.py](../minifs/bitmap.py).
Qualquer mudança no formato deve atualizar este arquivo, as constantes de `layout.py` e a constante `VERSION`.

Convenções: inteiros sem sinal em little-endian; blocos numerados a partir de 0; o bloco `b`
começa no deslocamento `b x block_size` do arquivo.

## 1. Parâmetros do format

| Parâmetro | Padrão | Valores aceitos |
|---|---|---|
| `total_blocks` (N) | obrigatório | de `data_start + 1` até 1.048.576 |
| `block_size` (bs) | 512 | 512, 1024, 2048, 4096 |
| `inode_count` | 64 | 1 a 4096 |

## 2. Regiões

As regiões são contíguas e calculadas a partir dos três parâmetros:

```
B = ceil(N / (8 x bs))                 blocos do bitmap
T = ceil(inode_count / (bs / 128))     blocos da tabela de inodes
D = 1 + B + T                          primeiro bloco de dados
```

| Região | Blocos | Conteúdo |
|---|---|---|
| Superblock | `0` | parâmetros do disco (64 bytes; restante zerado) |
| Bitmap | `1 .. B` | 1 bit por bloco do disco |
| Tabela de inodes | `1+B .. D-1` | `inode_count` registros de 128 bytes |
| Dados | `D .. N-1` | conteúdo dos arquivos |

Exemplo com `format 2048` (parâmetros padrão):

```
bloco:  0     1     2 ............. 17   18 ........................... 2047
       +-----+-----+------------------+---------------------------------+
       | SB  | BMP | inodes (16 blk)  |  dados (2030 blocos = 991 KiB)  |
       +-----+-----+------------------+---------------------------------+
        512 B 512 B  64 x 128 B = 8 KiB
```

Arquivo do disco: 2048 x 512 = 1.048.576 bytes. Metadados: 18 blocos (0,9%).

## 3. Superblock (bloco 0)

| Offset | Tam. | Campo | Valor / significado |
|---|---|---|---|
| 0 | 8 | `magic` | `"MINIFS01"`, identifica o MiniFS |
| 8 | 2 | `version` | `1` |
| 10 | 2 | `inode_size` | `128` |
| 12 | 4 | `block_size` | bytes por bloco |
| 16 | 4 | `total_blocks` | N |
| 20 | 4 | `bitmap_start` | `1` |
| 24 | 4 | `bitmap_blocks` | B |
| 28 | 4 | `inode_table_start` | `1 + B` |
| 32 | 4 | `inode_table_blocks` | T |
| 36 | 4 | `inode_count` | número máximo de arquivos |
| 40 | 4 | `data_start` | D |
| 44 | 2 | `direct_refs` | `20` (referências por inode) |
| 46 | 2 | reservado | `0` |
| 48 | 8 | `created_at` | instante do format (Unix epoch, segundos) |
| 56 | 4 | `mount_count` | incrementado a cada montagem |
| 60 | 4 | `checksum` | CRC-32 dos bytes 0 a 59 |

Validação no mount (qualquer falha gera `InvalidDiskError`): magic, CRC-32, versão,
`inode_size` e `direct_refs`, recálculo das regiões a partir de (N, bs, inode_count) comparado às
posições gravadas, e tamanho do arquivo igual a N x bs.

## 4. Bitmap

- O bit do bloco `b` está no byte `b // 8` do bitmap, posição `b % 8` (bit menos significativo primeiro).
- `1` indica bloco ocupado e `0` indica bloco livre.
- O bitmap cobre todos os blocos, inclusive os de metadados (0 a D-1), que ficam sempre em 1.
  Assim o índice do bit é o próprio número do bloco.
- Bits sem bloco correspondente (de N até o fim do último bloco do bitmap) ficam em 1.
- No mount, um bloco de metadados marcado como livre faz o disco ser rejeitado.

Exemplo (`format 64`, metadados nos blocos 0 a 17): bytes iniciais `FF FF 03 00 00 00 00 00`,
seguidos de `FF` até o fim do bloco.

## 5. Registro de arquivo (inode), 128 bytes

Formato definido em conjunto e implementado pelo Integrante 2. Struct Python:
`"<B3xIIH2x32s20I"` (`layout.INODE_FORMAT`).

| Offset | Tam. | Campo | Significado |
|---|---|---|---|
| 0 | 1 | `used` | 0 = registro livre, 1 = arquivo existente |
| 1 | 3 | padding | |
| 4 | 4 | `file_id` | identificador único do arquivo |
| 8 | 4 | `size` | tamanho do conteúdo em bytes |
| 12 | 2 | `n_blocks` | quantidade de entradas válidas em `blocks` |
| 14 | 2 | padding | |
| 16 | 32 | `name` | nome em UTF-8 completado com `\0` (máximo 32 bytes) |
| 48 | 80 | `blocks[20]` | números dos blocos de dados, na ordem do conteúdo |

- O inode `i` fica no bloco `inode_table_start + i // (bs/128)`, deslocamento `(i % (bs/128)) x 128`
  (`Layout.inode_location(i)`).
- Tamanho máximo de arquivo: `20 x bs` (10 KiB com blocos de 512 B).
- O format zera o disco inteiro, portanto todos os inodes começam com `used = 0`.

## 6. Blocos de dados

Contêm o conteúdo bruto dos arquivos. Um arquivo de `size` bytes ocupa `ceil(size / bs)` blocos;
o último bloco pode ficar parcialmente usado e o restante é ignorado na leitura, limitada por `size`.
