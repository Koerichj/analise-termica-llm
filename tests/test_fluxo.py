import json
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import httpx
import openai
import pandas as pd
from streamlit.testing.v1 import AppTest

from function_monitoramento import gerar_pdf_relatorio, preparar_base, total_periodo
from integracao_openai import ErroIntegracaoOpenAI, gerar_texto


RAIZ = Path(__file__).resolve().parents[1]
AMOSTRA = RAIZ / "data" / "amostra_leituras.csv"


class TestETL(unittest.TestCase):
    def test_aliases_e_fusos(self):
        dados = pd.read_csv(AMOSTRA).iloc[:3].copy()
        dados["timestamp"] = [
            "2026-11-09T08:00:00", "2026-11-09T11:01:00Z", "2026-11-09 08:02:00 EST",
        ]
        dados["dt_registro"] = [pd.NA, "2026-11-09T08:01:00-03:00", pd.NA]
        dados["nr_delta_t"] = [12.0, pd.NA, pd.NA]
        dados["delta_t"] = pd.NA
        dados.loc[2, "temperatura_saida"] = None

        base = preparar_base(dados)
        self.assertEqual(base["dt_registro"].dt.hour.tolist()[:2], [8, 8])
        self.assertTrue(pd.isna(base.loc[2, "dt_registro"]))
        self.assertEqual(base["ds_valvula_entrada"].tolist(), ["ABERTA", "ABERTA", "FECHADA"])
        self.assertEqual(base.loc[0, "nr_delta_t"], 12.0)
        self.assertAlmostEqual(base.loc[1, "nr_delta_t"], 0.11)
        self.assertTrue(pd.isna(base.loc[2, "nr_delta_t"]))
        pd.testing.assert_frame_equal(base, preparar_base(base))

        utc = preparar_base(dados.iloc[:1], fuso_sem_offset="UTC")
        self.assertEqual(utc["dt_registro"].dt.hour.iloc[0], 5)

    def test_entrada_incompativel(self):
        dados = pd.read_csv(AMOSTRA)
        with self.assertRaisesRegex(ValueError, "obrigatórias ausentes"):
            preparar_base(dados.drop(columns="vazao_l_min"))
        with self.assertRaisesRegex(ValueError, "conflitantes.*nr_vazao_l_min"):
            preparar_base(dados.assign(nr_vazao_l_min=90))
        with self.assertRaisesRegex(ValueError, "duplicadas.*vazao_l_min"):
            preparar_base(dados.assign(**{"vazao_l_min.1": 90}))
        with self.assertRaisesRegex(ValueError, "Nenhuma data"):
            preparar_base(dados.assign(timestamp="inválida"))

    def test_total_respeita_cobertura_e_zero_medido(self):
        base = pd.DataFrame({"nr_energia_kwh": [0.0, None]})
        self.assertTrue(pd.isna(total_periodo(base, "nr_energia_kwh")))
        self.assertEqual(total_periodo(base.iloc[:1], "nr_energia_kwh"), 0.0)


class TestFluxoStreamlit(unittest.TestCase):
    def test_xlsx_com_nomes_canonicos(self):
        dados = preparar_base(pd.read_csv(AMOSTRA))
        xlsx = BytesIO()
        dados.to_excel(xlsx, index=False, engine="openpyxl")
        etl = AppTest.from_file(RAIZ / "etl_monitoramento.py").run()
        etl.get("file_uploader")[0].set_value((
            "amostra.xlsx", xlsx.getvalue(),
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )).run()
        etl.button[0].click().run()
        self.assertFalse(etl.exception)
        base = etl.session_state["monitoramento_df"]
        self.assertEqual(len(base), len(dados))
        pd.testing.assert_series_equal(base["dt_registro"], dados["dt_registro"])

    def test_csv_e_relatorios_com_resposta_simulada(self):
        etl = AppTest.from_file(RAIZ / "etl_monitoramento.py").run()
        etl.get("file_uploader")[0].set_value((AMOSTRA.name, AMOSTRA.read_bytes(), "text/csv")).run()
        etl.button[0].click().run()
        self.assertFalse(etl.exception)
        base = etl.session_state["monitoramento_df"]

        exploratoria = AppTest.from_file(RAIZ / "exploratoria_monitoramento.py")
        exploratoria.session_state["monitoramento_df"] = base
        exploratoria.run()
        self.assertFalse(exploratoria.exception)
        self.assertEqual([metrica.value for metrica in exploratoria.metric][-3:], ["N/D"] * 3)

        relatorio = AppTest.from_file(RAIZ / "inteligencia_monitoramento.py")
        relatorio.session_state["monitoramento_df"] = base
        relatorio.run()
        self.assertFalse(relatorio.exception)
        for tipo, trecho in (
            ("Técnico", "relatório técnico detalhado"),
            ("Executivo", "relatório executivo conciso"),
            ("Acadêmico", "relatório acadêmico formal"),
        ):
            with self.subTest(tipo=tipo), patch(
                "integracao_openai.gerar_texto", return_value="## Evidências\n\n**ΔT** < referência & amostra."
            ) as gerar, patch("function_monitoramento.gerar_pdf_relatorio", wraps=gerar_pdf_relatorio) as pdf:
                relatorio.selectbox[1].select(tipo).run()
                relatorio.button[0].click().run()
                self.assertFalse(relatorio.exception)
                documento = json.loads(gerar.call_args.args[0])
                self.assertEqual(documento["qualidade_dados"]["registros_no_recorte_com_origem_sintetica"], 8)
                self.assertIsNone(documento["energia_e_volume"]["energia_termica_periodo_kwh"])
                self.assertEqual(documento["conformidade_operacional"]["inconformes"], 3)
                self.assertIn(trecho, gerar.call_args.kwargs["instrucoes"])
                self.assertIn("Use `regras_operacionais`", gerar.call_args.kwargs["instrucoes"])
                pdf.assert_called_once()
                self.assertTrue(relatorio.get("download_button"))

class TestOpenAI(unittest.TestCase):
    def test_configuracao_e_erros_sem_rede(self):
        requisicao = httpx.Request("POST", "https://api.openai.com/v1/responses")
        with patch("integracao_openai.load_dotenv"), patch.dict("os.environ", {}, clear=True), patch(
            "integracao_openai.OpenAI"
        ) as cliente:
            with self.assertRaisesRegex(ErroIntegracaoOpenAI, "OPENAI_API_KEY"):
                gerar_texto("Dados")
            cliente.assert_not_called()

            with patch.dict("os.environ", {"OPENAI_API_KEY": "chave-ficticia"}):
                with self.assertRaisesRegex(ErroIntegracaoOpenAI, "OPENAI_MODEL"):
                    gerar_texto("Dados")
            cliente.assert_not_called()

            criar = cliente.return_value.__enter__.return_value.responses.create
            with patch.dict("os.environ", {"OPENAI_API_KEY": "chave-ficticia", "OPENAI_MODEL": "modelo-teste"}):
                criar.return_value = SimpleNamespace(output_text="   ", status="completed")
                with self.assertRaisesRegex(ErroIntegracaoOpenAI, "sem texto"):
                    gerar_texto("Dados")

                criar.return_value = SimpleNamespace(output_text=" Relatório ", status="completed")
                self.assertEqual(gerar_texto("Dados", instrucoes="Instruções"), "Relatório")
                criar.assert_called_with(model="modelo-teste", instructions="Instruções", input="Dados", store=False)

                for classe, status, mensagem in (
                    (openai.AuthenticationError, 401, "autenticação"),
                    (openai.NotFoundError, 404, "Modelo indisponível"),
                    (openai.RateLimitError, 429, "Limite de requisições"),
                ):
                    criar.side_effect = classe(
                        "detalhe sensível", response=httpx.Response(status, request=requisicao), body=None
                    )
                    with self.assertRaisesRegex(ErroIntegracaoOpenAI, mensagem) as erro:
                        gerar_texto("Dados")
                    self.assertNotIn("detalhe sensível", str(erro.exception))

                criar.side_effect = openai.APITimeoutError(requisicao)
                with self.assertRaisesRegex(ErroIntegracaoOpenAI, "tempo limite"):
                    gerar_texto("Dados")
