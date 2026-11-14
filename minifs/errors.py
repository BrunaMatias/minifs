"""Exceções do MiniFS.

Erros tratados herdam de MiniFSError e são exibidos pela CLI sem encerrar o programa.
"""


class MiniFSError(Exception):
    """Classe base dos erros tratados do MiniFS."""


class InvalidParameterError(MiniFSError):
    """Parâmetro inválido, como tamanho de disco ou de bloco não suportado."""


class DiskNotFoundError(MiniFSError):
    """O arquivo do disco virtual não existe."""


class InvalidDiskError(MiniFSError):
    """O arquivo não é um disco MiniFS válido."""


class DiskClosedError(MiniFSError):
    """Operação sobre um disco já fechado."""


class BlockOutOfRangeError(MiniFSError):
    """Número de bloco fora do disco ou da região permitida."""


class DiskFullError(MiniFSError):
    """Não há blocos de dados livres suficientes."""


class BlockAlreadyFreeError(MiniFSError):
    """Tentativa de liberar um bloco que já está livre."""


class NoSuchFileError(MiniFSError):
    """Arquivo inexistente."""


class DuplicateNameError(MiniFSError):
    """Já existe um arquivo com esse nome."""


class InvalidNameError(MiniFSError):
    """Nome de arquivo vazio, longo demais ou com caracteres não permitidos."""


class FileTooLargeError(MiniFSError):
    """Conteúdo maior que o tamanho máximo de arquivo."""


class NoFreeInodeError(MiniFSError):
    """Tabela de inodes cheia."""
