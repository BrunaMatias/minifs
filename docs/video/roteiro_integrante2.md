# Roteiro do integrante 2 — Metadados e inodes

## Demonstração no terminal

Na raiz do projeto, use uma imagem separada para demonstração. O `format` recria a imagem indicada.

```bash
python -m minifs --disk demo_inodes.img format 2048
python -m minifs --disk demo_inodes.img create exemplo.txt
python -m minifs --disk demo_inodes.img stat exemplo.txt
python -m minifs --disk demo_inodes.img ls
python -m minifs --disk demo_inodes.img dump 2 128
python -m minifs --disk demo_inodes.img rm exemplo.txt
python -m minifs --disk demo_inodes.img ls
python -m minifs --disk demo_inodes.img create novo.txt
python -m minifs --disk demo_inodes.img stat novo.txt
```

1. No primeiro `stat`, destaque o ID 1, o tamanho de 0 bytes e a ausência de blocos de dados.
   Explique que o `create` ocupou um inode, e que cada comando é uma nova execução do Python.
2. No `dump`, aponte o primeiro byte `01` (inode em uso) e o nome `exemplo.txt`, que começa no
   deslocamento `0x10`. O inode tem 128 bytes e reserva espaço para 20 referências diretas.
3. Após o `rm`, mostre a lista vazia. O novo arquivo usa o slot disponível e recebe o ID 2.
   Explique que, se o inode tiver blocos de dados, `rm` persiste a remoção e depois os libera no bitmap.

## Demonstração em grupo após a integração de `write`

Para mostrar a reutilização de um bloco de dados, use a mesma imagem recém-formatada e execute
os comandos abaixo em sequência. Com a configuração padrão, o primeiro bloco de dados é o 18.

```bash
python -m minifs --disk demo_blocos.img format 2048
python -m minifs --disk demo_blocos.img create primeiro.txt
python -m minifs --disk demo_blocos.img write primeiro.txt "primeiro conteudo"
python -m minifs --disk demo_blocos.img stat primeiro.txt
python -m minifs --disk demo_blocos.img rm primeiro.txt
python -m minifs --disk demo_blocos.img create segundo.txt
python -m minifs --disk demo_blocos.img write segundo.txt "segundo conteudo"
python -m minifs --disk demo_blocos.img stat segundo.txt
```

Compare os números de bloco mostrados pelos dois `stat`. A repetição do bloco mostra que o
alocador voltou a encontrá-lo livre após o `rm`.
