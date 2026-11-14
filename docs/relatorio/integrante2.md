# Relatório do integrante 2 — Metadados dos arquivos

A tabela de inodes ocupa uma região reservada da imagem do MiniFS. Cada registro tem 128 bytes e
guarda o indicador de uso, o identificador do arquivo, o tamanho em bytes, o número de blocos,
o nome em UTF-8 e até 20 referências diretas. Os números dos blocos aparecem na ordem do conteúdo e
podem apontar para posições distantes no disco. O maior arquivo suporta 20 × 512 B = 10 KiB na
configuração padrão. Cada bloco de 512 bytes acomoda quatro inodes.

Na montagem, o MiniFS carrega a tabela da imagem e verifica referências e identificadores dos
arquivos ativos. Para atualizar um inode, calcula o bloco e o deslocamento pelo layout, lê o bloco
inteiro, troca os 128 bytes do registro e grava o bloco de volta. Assim, os inodes vizinhos do mesmo
bloco são preservados.

`create` valida o nome e ocupa um registro livre. O arquivo começa com tamanho zero e nenhuma
referência, portanto sua criação não consome blocos de dados. Nome duplicado e tabela de inodes
cheia geram erros distintos. A tabela pode ficar cheia mesmo quando ainda há blocos de dados livres.
`stat` mostra identificador, nome, tamanho e referências de um arquivo. `ls` lista os registros ativos.

`rm` marca o registro como livre e persiste essa mudança antes de devolver os blocos ao bitmap. Em
seguida, o alocador *first-fit* já pode entregar esses blocos em pedidos futuros. Se a execução for
interrompida entre as duas etapas, podem sobrar blocos ocupados sem arquivo associado. O registro
liberado conserva apenas seu último identificador, o que permite reutilizar o slot sem repetir ids
após remontar a imagem.
