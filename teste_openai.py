import argparse

from integracao_openai import ErroIntegracaoOpenAI, gerar_texto


def main():
    parser = argparse.ArgumentParser(description="Teste opcional da Responses API.")
    parser.add_argument(
        "--executar", action="store_true",
        help="Autoriza uma chamada real à OpenAI, que pode gerar cobrança.",
    )
    args = parser.parse_args()
    if not args.executar:
        parser.print_help()
        return

    try:
        print(gerar_texto("Responda apenas: integração funcionando."))
    except ErroIntegracaoOpenAI as erro:
        parser.exit(1, f"{erro}\n")


if __name__ == "__main__":
    main()
