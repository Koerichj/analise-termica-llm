import os
from pathlib import Path

from dotenv import load_dotenv
from openai import (
    APIConnectionError,
    APIError,
    APIStatusError,
    APITimeoutError,
    AuthenticationError,
    NotFoundError,
    OpenAI,
    PermissionDeniedError,
    RateLimitError,
)


class ErroIntegracaoOpenAI(RuntimeError):
    """Mensagem segura para apresentação na interface."""


def gerar_texto(dados, *, instrucoes=None):
    load_dotenv(Path(__file__).resolve().with_name(".env"))
    chave = (os.getenv("OPENAI_API_KEY") or "").strip()
    modelo = (os.getenv("OPENAI_MODEL") or "").strip()
    if not chave:
        raise ErroIntegracaoOpenAI("Configure OPENAI_API_KEY para gerar o relatório.")
    if not modelo:
        raise ErroIntegracaoOpenAI("Configure OPENAI_MODEL com um modelo habilitado para a Responses API.")

    try:
        with OpenAI(api_key=chave, timeout=90.0, max_retries=0) as client:
            resposta = client.responses.create(
                model=modelo, instructions=instrucoes, input=dados, store=False
            )
    except AuthenticationError:
        raise ErroIntegracaoOpenAI("A OpenAI rejeitou a autenticação. Verifique OPENAI_API_KEY.") from None
    except (NotFoundError, PermissionDeniedError):
        raise ErroIntegracaoOpenAI("Modelo indisponível ou sem permissão. Verifique OPENAI_MODEL e o acesso do projeto.") from None
    except RateLimitError as erro:
        if erro.code == "insufficient_quota":
            raise ErroIntegracaoOpenAI("A cota da OpenAI está esgotada. Verifique os limites do projeto.") from None
        raise ErroIntegracaoOpenAI("Limite de requisições da OpenAI atingido. Tente novamente mais tarde.") from None
    except APITimeoutError:
        raise ErroIntegracaoOpenAI("A OpenAI excedeu o tempo limite da requisição.") from None
    except APIConnectionError:
        raise ErroIntegracaoOpenAI("Não foi possível conectar à OpenAI.") from None
    except APIStatusError as erro:
        if erro.code in {"model_not_found", "unsupported_model"} or erro.param == "model":
            raise ErroIntegracaoOpenAI("Modelo indisponível ou incompatível com a Responses API. Verifique OPENAI_MODEL.") from None
        raise ErroIntegracaoOpenAI("A OpenAI não conseguiu processar a requisição.") from None
    except APIError:
        raise ErroIntegracaoOpenAI("A OpenAI não conseguiu processar a requisição.") from None

    texto = (resposta.output_text or "").strip()
    if not texto:
        raise ErroIntegracaoOpenAI("A OpenAI retornou uma resposta sem texto.")
    if resposta.status != "completed":
        raise ErroIntegracaoOpenAI("A OpenAI retornou uma resposta incompleta.")
    return texto
