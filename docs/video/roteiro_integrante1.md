# Roteiro do vídeo: disco virtual, superblock e bitmap (Integrante 1)

**Duração-alvo:** 4 a 5 minutos, dentro do mini seminário do grupo.
**Formato:** 3 slides curtos e demonstração ao vivo no terminal.
**Ordem no vídeo do grupo:** o Integrante 1 abre, porque apresenta a base sobre a qual as outras partes funcionam.
Depois vem o Integrante 2 (inodes, create/rm/stat), e o Integrante 3 fecha com read/write e a
demonstração completa exigida na seção 9 do enunciado.

## Preparação (antes de gravar)

- Terminal na pasta do projeto, fonte grande (16 pt ou mais), janela larga (90 colunas ou mais).
- Apagar discos antigos: `del demo.img cheio.img` (Windows) ou `rm -f demo.img cheio.img`.
- Ensaiar uma vez. Todas as saídas abaixo foram conferidas na implementação.
- Slides: o diagrama de layout de [docs/LAYOUT_DISCO.md](../LAYOUT_DISCO.md) e a tabela do superblock.

---

## Bloco 1: Abertura e visão geral (cerca de 40 s, slide 1)

> "Sou responsável pela base do MiniFS: o disco virtual, o superblock e o bitmap de blocos livres.
> O disco é um único arquivo binário no Windows, dividido em blocos de tamanho fixo, por padrão
> 512 bytes. Nenhum arquivo do MiniFS é armazenado como arquivo separado no sistema hospedeiro. Todo o conteúdo fica
> dentro dessa imagem, e só uma classe, a `VirtualDisk`, acessa o arquivo. Ela lê e escreve blocos inteiros,
> como o driver de um disco real faz com os setores."

## Bloco 2: Layout do disco (cerca de 50 s, slide 2, diagrama)

```
 0     1     2 ............ 17   18 ............................... 2047
+-----+-----+-----------------+------------------------------------+
| SB  | BMP | tabela de inodes|          blocos de dados           |
+-----+-----+-----------------+------------------------------------+
```

> "O disco tem quatro regiões contíguas. O bloco 0 é o superblock. Em seguida vem o bitmap, com um bit
> por bloco. Depois vem a tabela de inodes, que é a parte do [nome do Integrante 2]: 64 registros de 128 bytes,
> 16 blocos. O resto são blocos de dados. O tamanho de cada região é calculado a partir de três parâmetros:
> número de blocos, tamanho do bloco e número de inodes. Com 2048 blocos, os metadados ocupam só 18 blocos,
> menos de 1% do disco."

## Bloco 3: Demonstração do format, info e dump do superblock (cerca de 70 s)

```text
python -m minifs --disk demo.img format 2048
```
Saída esperada:
```
disco 'demo.img' formatado: 2048 blocos x 512 B = 1048576 B
  metadados: 18 blocos | dados: 2030 blocos livres (a partir do bloco 18)
```
> "O format cria o arquivo com 1 MiB de zeros, grava o bitmap e grava o superblock por último.
> Se o format for interrompido, o disco não é reconhecido como válido."

```text
python -m minifs --disk demo.img info
```
> "O comando info mostra o que está gravado no superblock: tamanho do bloco, onde começa cada região,
> o maior arquivo suportado (20 blocos, ou seja, 10 KiB) e um contador de montagens."

```text
python -m minifs --disk demo.img dump 0 64
```
Saída esperada (os 4 bytes do CRC e a data mudam):
```
0000  4d 49 4e 49 46 53 30 31 01 00 80 00 00 02 00 00  |MINIFS01........|
0010  00 08 00 00 01 00 00 00 01 00 00 00 02 00 00 00  |................|
0020  10 00 00 00 40 00 00 00 12 00 00 00 14 00 00 00  |....@...........|
0030  .. .. .. .. 00 00 00 00 03 00 00 00 .. .. .. ..  |................|
```
> "Estes são os bytes reais do bloco 0. Os primeiros oito são a assinatura MINIFS01. Depois vêm `00 02`,
> que é 512 em little-endian (o tamanho do bloco), `00 08`, que é 2048 blocos, e `12`, que é 18,
> o primeiro bloco de dados. Os quatro últimos bytes são um CRC-32: se alguém corromper o superblock, o mount recusa o disco."

```text
python -m minifs --disk README.md info
```
Saída: `erro: assinatura inválida: o arquivo não é um disco MiniFS`
> "Se eu tentar montar um arquivo qualquer, o MiniFS percebe que ele não é um disco válido."

## Bloco 4: Bitmap, alocação e reutilização de blocos (cerca de 80 s, slide 3, opcional)

```text
python -m minifs --disk demo.img dump 1 16
```
```
0000  ff ff 03 00 00 00 00 00 00 00 00 00 00 00 00 00  |................|
```
> "Este é o bitmap no disco. Um bit 1 quer dizer ocupado. `ff ff 03` são 18 bits ligados: os blocos 0 a 17,
> que são os próprios metadados. Eles ficam sempre ocupados, então o alocador nunca entrega um deles."

> "Como create e write são responsabilidade dos outros integrantes, vou usar dois comandos de depuração que chamam o
> alocador diretamente."

```text
python -m minifs --disk demo.img dbg-alloc 5
```
Saída: `blocos alocados: 18 19 20 21 22`
> "A política é first-fit: os primeiros blocos livres a partir da área de dados. Os blocos não precisam
> ser vizinhos, porque a alocação é indexada: o inode guarda a lista de blocos. Por isso não há fragmentação externa."

```text
python -m minifs --disk demo.img dbg-free 19 20
python -m minifs --disk demo.img dbg-alloc 3
```
Saída: `blocos alocados: 19 20 23`
> "Liberei o 19 e o 20, e o próximo pedido de 3 blocos recebeu 19, 20 e só depois o 23.
> Os blocos liberados são reutilizados primeiro, porque a busca sempre recomeça no início da área de dados."

```text
python -m minifs --disk demo.img bitmap 0 63
```
```
      0 SBIIIIIIIIIIIIIIII######........................................
```

## Bloco 5: Persistência (cerca de 30 s)

> "Cada comando foi um processo diferente. O programa abriu, executou e fechou toda vez.
> Mesmo assim, o alocador manteve o registro dos blocos usados, porque o bitmap é gravado no disco a cada alteração."

```text
python -m minifs --disk demo.img info
```
> "O contador de montagens subiu a cada execução. É o superblock sendo relido e regravado."

## Bloco 6: Disco cheio (cerca de 40 s)

```text
python -m minifs --disk cheio.img format 20
python -m minifs --disk cheio.img dbg-alloc 3
python -m minifs --disk cheio.img dbg-alloc 2
python -m minifs --disk cheio.img df
```
Saídas:
```
erro: disco cheio: 3 bloco(s) solicitado(s), 2 livre(s)
blocos alocados: 18 19
...
uso da área de dados: 100.0%
```
> "Este disco só tem 2 blocos de dados. Um pedido de 3 blocos falha com 'disco cheio' sem alterar nada:
> o pedido seguinte de 2 blocos ainda é atendido. A alocação é atômica. Para o write, isso significa que um
> arquivo nunca fica gravado pela metade quando falta espaço."

## Bloco 7: Testes e passagem para o próximo integrante (cerca de 20 s)

```text
python -m unittest discover -s tests -t .
```
Saída: `Ran 58 tests ... OK`
> "São 58 testes automatizados, inclusive de persistência entre processos, reutilização de blocos e disco cheio.
> Sobre essa base, o [nome do Integrante 2] vai mostrar como os arquivos são registrados na tabela de inodes."

---

## Mapa para os critérios de avaliação

| Critério (pontos) | Onde aparece nesta parte |
|---|---|
| Estruturas internas e layout (25) | Blocos 2 e 3 (diagrama, superblock byte a byte) |
| Bitmap e gerenciamento de blocos (20) | Bloco 4 (dump do bitmap, first-fit, reutilização) |
| Persistência e tratamento de erros (15) | Blocos 3, 5 e 6 (disco inválido, contador de montagens, disco cheio) |
| Documentação, testes e demonstração (15) | Bloco 7 |

## Se algo der errado na gravação

- `erro: disco 'demo.img' não encontrado`: rode o `format` de novo.
- Os números dos blocos não batem com o roteiro: o `demo.img` não estava novo. Rode `format 2048` de novo
  e repita a partir do Bloco 3.
