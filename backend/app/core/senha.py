"""Política de senha.

Segue a recomendação do NIST SP 800-63B, que inverteu o que se fazia há
quinze anos:

- COMPRIMENTO mínimo (10) em vez de regras de composição. "Tenha maiúscula,
  número e símbolo" produz `Senha@2024` — que cumpre a regra e cai em
  qualquer lista de senhas vazadas.
- LISTA DE SENHAS CONHECIDAS: o que mais protege é recusar a senha que um
  atacante tenta primeiro.
- NADA DO CONTEXTO: nem o e-mail, nem o nome da pessoa, nem o da empresa.
- SEM TROCA PERIÓDICA OBRIGATÓRIA: força a pessoa a criar variações
  previsíveis (`Britto2025` -> `Britto2026`). Troca-se quando há motivo.

A lista é curta de propósito: senhas comuns no Brasil, sequências e as
palavras do próprio negócio. Uma lista de milhões pegaria mais — e seria
um arquivo de dezenas de megabytes num repositório público. Os padrões
(palavra comum + números, sequência, repetição) cobrem a maior parte do
que a lista longa pegaria.

`SenhaForte123` está na lista por um motivo concreto: é a senha usada nos
testes deste repositório, que é público.
"""

from __future__ import annotations

import re
import unicodedata

from app.core.errors import ValidationError

SENHA_MINIMA = 10
CARACTERES_DISTINTOS_MINIMOS = 5

#: Senhas e palavras-base mais usadas. Comparadas sem acento, em minúsculas
#: e também sem os números e símbolos do fim ("flamengo2024" -> "flamengo").
_LISTA = """
    senha senhas senha123 senhaforte senhaforte123 minhasenha novasenha mudar mudar123
    trocar trocarsenha acesso acessar entrar login admin administrador root usuario
    teste testando password passw0rd qwerty qwertyuiop asdfgh asdfghjkl zxcvbnm
    abc123 abcdef abcdefgh abcdefghij iloveyou princesa princess monkey dragon
    master sunshine shadow superman batman football baseball welcome letmein
    brasil brasil2014 saopaulo riodejaneiro campogrande matogrosso matogrossodosul
    flamengo corinthians palmeiras santos gremio internacional cruzeiro vasco
    botafogo fluminense atletico saopaulofc bahia sport comercial operario
    jesus jesuscristo deus deusefiel deuseamor deuseminhavida amor amorzinho
    amoreterno teamo meuamor familia felicidade liberdade saudade vitoria
    gabriel lucas mateus pedro joao maria ana julia beatriz camila amanda
    fernanda juliana rafael bruno felipe gustavo carlos marcos paulo diego
    britto brittomoveis moveis corrimao logrotas logistica entrega entregas
    rota rotas motorista caminhao empresa trabalho escritorio
"""
_CONHECIDAS = frozenset(_LISTA.split())

#: Pedaços do contexto que nunca podem estar na senha.
_CONTEXTO_FIXO = ("britto", "logrotas", "corrimao")

_SEQUENCIAS = (
    "01234567890123456789",
    "98765432109876543210",
    "abcdefghijklmnopqrstuvwxyz",
    "zyxwvutsrqponmlkjihgfedcba",
    "qwertyuiopasdfghjklzxcvbnm",
)


def _normalizar(texto: str) -> str:
    t = unicodedata.normalize("NFKD", texto or "")
    return "".join(c for c in t if not unicodedata.combining(c)).lower()


def _nucleo(senha: str) -> str:
    """"Flamengo@2024!" -> "flamengo": a palavra sem o enfeite do fim."""
    t = _normalizar(senha)
    t = re.sub(r"[^a-z0-9]", "", t)
    return re.sub(r"\d+$", "", t) or t


def _maior_sequencia(compacta: str) -> int:
    """Comprimento do maior trecho da senha que é uma sequência conhecida."""
    maior = 0
    for i in range(len(compacta)):
        for j in range(i + maior + 1, len(compacta) + 1):
            if any(compacta[i:j] in s for s in _SEQUENCIAS):
                maior = j - i
            else:
                break
    return maior


def _pedacos_do_contexto(email: str | None, nome: str | None) -> list[str]:
    pedacos = list(_CONTEXTO_FIXO)
    if email:
        local = _normalizar(email.split("@")[0])
        pedacos += [p for p in re.split(r"[^a-z0-9]+", local) if len(p) >= 4]
    if nome:
        pedacos += [p for p in re.split(r"[^a-z]+", _normalizar(nome)) if len(p) >= 4]
    return pedacos


def problemas(senha: str, *, email: str | None = None, nome: str | None = None) -> list[str]:
    """O que há de errado com a senha, em frases para a pessoa ler. Vazio: serve."""
    achados: list[str] = []
    normal = _normalizar(senha)

    if len(senha) < SENHA_MINIMA:
        achados.append(f"Use pelo menos {SENHA_MINIMA} caracteres.")
    if len(set(senha)) < CARACTERES_DISTINTOS_MINIMOS:
        achados.append("A senha repete poucos caracteres. Varie mais.")

    compacta = re.sub(r"[^a-z0-9]", "", normal)
    if normal in _CONHECIDAS or compacta in _CONHECIDAS or _nucleo(senha) in _CONHECIDAS:
        achados.append(
            "Esta senha (ou a palavra dela) está entre as mais usadas e é das primeiras "
            "que um invasor tenta."
        )
    elif _maior_sequencia(compacta) >= 6 and len(compacta) - _maior_sequencia(compacta) < 6:
        # A senha é, na maior parte, uma sequência: "1234567890ab" enfeita
        # uma sequência inteira com duas letras. Numa frase longa, um
        # "123456" no meio não domina a senha e não é recusado.
        achados.append("Sequências como 123456 ou abcdef são adivinhadas em segundos.")

    for pedaco in _pedacos_do_contexto(email, nome):
        if pedaco in compacta:
            achados.append(
                "Não use o seu nome, o seu e-mail nem o nome da empresa na senha."
            )
            break

    return achados


def exigir_senha_valida(
    senha: str, *, email: str | None = None, nome: str | None = None
) -> None:
    """Levanta ValidationError com todos os problemas de uma vez.

    Todos de uma vez: corrigir um e descobrir o próximo na tentativa seguinte
    é o que faz a pessoa desistir e escolher `Senha@1234`.
    """
    achados = problemas(senha, email=email, nome=nome)
    if achados:
        raise ValidationError(
            "Senha fraca: " + " ".join(achados), details={"problemas": achados}
        )


def e_fraca(senha: str, *, email: str | None = None, nome: str | None = None) -> bool:
    """Para o login: a senha em uso deixaria de passar na política de hoje?

    Senhas criadas antes da política continuam entrando — trancar alguém
    fora do sistema por uma regra nova seria pior —, mas a tela avisa.
    """
    return bool(problemas(senha, email=email, nome=nome))
