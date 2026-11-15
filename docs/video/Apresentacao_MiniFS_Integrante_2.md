# MiniFS | Metadados dos arquivos

**Integrante 2 · Trabalho de Sistemas Operacionais**

## 1. O que fica no inode

Cada arquivo tem um registro de **128 bytes** na imagem do disco virtual.

| Campo | O que guarda |
| --- | --- |
| `used` | Se o registro está em uso |
| `file_id` e `name` | Identificador e nome do arquivo |
| `size` | Tamanho do conteúdo em bytes |
| `blocks` | Até 20 referências aos blocos de dados, na ordem do conteúdo |

## 2. Criar um arquivo — `create`

O MiniFS valida o nome, verifica se já existe um arquivo com esse nome e procura um registro livre. O arquivo começa com **0 bytes** e **nenhum bloco de dados**.

Trecho de `minifs/fs.py` que cria e grava o registro.

```python
inode = Inode(slot.index, used=True, file_id=self.inodes.last_file_id + 1, name=name)
self.inodes.save(inode)
```

A tabela é gravada na imagem do disco virtual e carregada novamente quando o MiniFS abre a imagem.

## 3. Consultar os metadados — `stat` e `ls`

| Comando | Resultado |
| --- | --- |
| `stat exemplo.txt` | Mostra ID, nome, tamanho e blocos do arquivo escolhido |
| `ls` | Lista os arquivos que têm um inode em uso |

## 4. Remover um arquivo — `rm`

Primeiro o MiniFS grava o inode como livre. Se o arquivo ocupava blocos de dados, o sistema confirma a gravação e depois devolve esses blocos ao bitmap para que possam ser reutilizados.

Trecho de `minifs/fs.py` que registra a remoção e libera os blocos.

```python
self.inodes.save(Inode(inode.index, file_id=inode.file_id))
if inode.blocks:
    # Persiste a remoção antes de permitir que o bitmap reutilize os blocos.
    self.disk.sync()
    self.bitmap.free(inode.blocks)
```
