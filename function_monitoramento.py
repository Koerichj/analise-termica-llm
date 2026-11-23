import re
from io import BytesIO
from xml.sax.saxutils import escape

import pandas as pd

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import (
    getSampleStyleSheet,
    ParagraphStyle
)
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle
)

DIMENSOES = [
    "ds_origem",
    "ds_estado_processo",
    "ds_status_operacional",
    "ds_valvula_entrada",
    "ds_valvula_saida",
    "ds_condicao_termica",
    "ds_condicao_transferencia",
    "ds_faixa_desempenho_termico",
    "ds_status_valvulas",
    "ds_criticidade",
    "ds_status_validacao",
]


MEDIDAS = [
    "nr_ciclo",
    "nr_temperatura_entrada",
    "nr_temperatura_saida",
    "nr_delta_t",
    "nr_vazao_l_min",
    "nr_volume_instante_l",
    "nr_volume_total_l",
    "nr_nivel_tubulacao_percentual",
    "nr_tempo_maturacao_min",
    "nr_energia_kj",
    "nr_energia_kwh",
    "nr_energia_total_kwh",
    "nr_desempenho_termico_percentual",
    "nr_economia_reais",
    "nr_fator_solar",
]


MAPA_COLUNAS = {
    "timestamp": "dt_registro",
    "origem": "ds_origem",
    "estado_processo": "ds_estado_processo",
    "ciclo": "nr_ciclo",
    "temperatura_entrada": "nr_temperatura_entrada",
    "temperatura_saida": "nr_temperatura_saida",
    "delta_t": "nr_delta_t",
    "vazao_l_min": "nr_vazao_l_min",
    "valvula_entrada": "ds_valvula_entrada",
    "valvula_saida": "ds_valvula_saida",
    "nivel_tubulacao_percentual": "nr_nivel_tubulacao_percentual",
    "tempo_maturacao_min": "nr_tempo_maturacao_min",
}

CAMPOS_OBRIGATORIOS = (
    "dt_registro", "ds_estado_processo", "nr_temperatura_entrada",
    "nr_temperatura_saida", "nr_vazao_l_min",
)
VALVULAS = ("ds_valvula_entrada", "ds_valvula_saida")
FUSO_LOCAL = "America/Sao_Paulo"
TARIFA_KWH = 0.52


def normalizar_coluna(dados, campo, fuso_sem_offset):
    if campo in ("dt_registro", "dt_cadastro"):
        texto = dados.astype("string").str.strip()
        com_fuso = texto.str.contains(
            r"(?:Z|UTC|GMT|[T ]\d{2}:.*[+-]\d{2}(?::?\d{2})?)$",
            case=False,
            na=False,
        )
        # Pandas pode descartar siglas de fuso desconhecidas ao ler texto.
        fuso_nominal = texto.str.contains(
            r"\d{1,2}:\d{2}(?:[:.,]\d+)*\s*(?!(?:AM|PM)$)[A-Za-z][A-Za-z_./+-]*$",
            case=False,
            na=False,
        )
        datas = pd.to_datetime(
            texto.mask(com_fuso | fuso_nominal), format="mixed", errors="coerce"
        )
        if fuso_sem_offset == "UTC":
            datas = datas.dt.tz_localize("UTC").dt.tz_convert(FUSO_LOCAL).dt.tz_localize(None)
        instantes = pd.to_datetime(
            texto.where(com_fuso), format="mixed", errors="coerce", utc=True
        )
        locais = instantes.dt.tz_convert(FUSO_LOCAL).dt.tz_localize(None)
        return datas.where(~com_fuso, locais)

    if campo in MEDIDAS:
        return pd.to_numeric(dados, errors="coerce").replace(
            [float("inf"), float("-inf")], float("nan")
        )

    texto = dados.astype("string").str.strip()
    texto = texto.mask(texto.eq(""))
    if campo in ("ds_estado_processo", *VALVULAS):
        texto = texto.str.upper()
    if campo in VALVULAS:
        texto = texto.replace({
            "1": "ABERTA", "1.0": "ABERTA", "TRUE": "ABERTA", "ABERTO": "ABERTA",
            "0": "FECHADA", "0.0": "FECHADA", "FALSE": "FECHADA", "FECHADO": "FECHADA",
        })
    if campo == "fg_validado":
        texto = texto.str.lower()
    return texto


def preparar_base(df, *, fuso_sem_offset=FUSO_LOCAL):
    """Normaliza leituras e conserva o horário de parede local por padrão."""
    if fuso_sem_offset not in (FUSO_LOCAL, "UTC"):
        raise ValueError(f"Fuso das datas sem offset inválido. Escolha {FUSO_LOCAL} ou UTC.")
    df = df.copy().reset_index(drop=True)
    df.columns = df.columns.astype(str).str.strip().str.lower()
    # Pandas acrescenta um sufixo numérico a cabeçalhos repetidos.
    sem_sufixo = df.columns.str.replace(r"\.\d+$", "", regex=True)
    conhecidas = [*MAPA_COLUNAS, *MEDIDAS, *DIMENSOES, "dt_registro", "dt_cadastro", "fg_validado"]
    duplicadas = df.columns[df.columns.duplicated()].union(
        sem_sufixo[sem_sufixo.duplicated() & sem_sufixo.isin(conhecidas)]
    ).unique()
    if len(duplicadas):
        raise ValueError(f"Colunas duplicadas: {', '.join(duplicadas)}.")

    for alias, campo in MAPA_COLUNAS.items():
        if alias not in df:
            continue
        if campo not in df:
            df = df.rename(columns={alias: campo})
            continue
        original = normalizar_coluna(df[campo], campo, fuso_sem_offset)
        alternativa = normalizar_coluna(df[alias], campo, fuso_sem_offset)
        bruto_original = df[campo].astype("string").str.strip().replace("", pd.NA)
        bruto_alternativo = df[alias].astype("string").str.strip().replace("", pd.NA)
        ambos_preenchidos = bruto_original.notna() & bruto_alternativo.notna()
        ambos_invalidos_iguais = (
            original.isna() & alternativa.isna() & bruto_original.eq(bruto_alternativo).fillna(False)
        )
        iguais = original.eq(alternativa).fillna(False) | ambos_invalidos_iguais
        if (ambos_preenchidos & ~iguais).any():
            raise ValueError(f"Valores conflitantes nas colunas '{campo}' e '{alias}'.")
        # Conserve os valores brutos até a conversão única de datas abaixo.
        df[campo] = bruto_original.where(original.notna(), bruto_alternativo)
        df = df.drop(columns=alias)

    faltantes = [campo for campo in CAMPOS_OBRIGATORIOS if campo not in df]
    if faltantes:
        raise ValueError(f"Colunas obrigatórias ausentes: {', '.join(faltantes)}.")

    for campo in (*MEDIDAS, "dt_registro", "dt_cadastro", "ds_estado_processo", "ds_origem",
                  *VALVULAS, "fg_validado"):
        if campo in df:
            df[campo] = normalizar_coluna(df[campo], campo, fuso_sem_offset)

    if df["dt_registro"].isna().all():
        raise ValueError("Nenhuma data de leitura válida em 'dt_registro' ou 'timestamp'.")

    delta = df["nr_temperatura_saida"] - df["nr_temperatura_entrada"]
    if "nr_delta_t" in df:
        delta = df["nr_delta_t"].fillna(delta)
    df["nr_delta_t"] = delta.replace([float("inf"), float("-inf")], float("nan"))

    df = df.sort_values("dt_registro", kind="stable", ignore_index=True)
    datas = df["dt_registro"].dt
    df["data"], df["hora"], df["mes"], df["ano"] = datas.date, datas.hour, datas.month, datas.year
    return df


def formatar_valor(valor, unidade=""):
    return "N/D" if pd.isna(valor) else f"{float(valor):.2f}{unidade}"


def total_periodo(base, campo):
    """Um total do período requer valor para cada leitura selecionada."""
    if campo in base and not base.empty:
        return base[campo].sum(min_count=len(base))
    return float("nan")


def obter_dimensoes(df):

    return [
        coluna
        for coluna in DIMENSOES
        if coluna in df.columns
    ]


def obter_medidas(df):

    return [
        coluna
        for coluna in MEDIDAS
        if coluna in df.columns
    ]

def gerar_pdf_relatorio(
    texto_markdown,
    tipo_relatorio
):
    """
    Converte o relatório Markdown gerado pela IA em PDF.
    Retorna o PDF em memória como bytes.
    """

    buffer = BytesIO()

    # ========================================================
    # FONTES
    # ========================================================

    fonte_normal = "Helvetica"
    fonte_bold = "Helvetica-Bold"

    # No Windows, utilizar Arial para suportar
    # corretamente caracteres como Δ, ° e acentuação.
    try:

        caminho_arial = (
            r"C:\Windows\Fonts\arial.ttf"
        )

        caminho_arial_bold = (
            r"C:\Windows\Fonts\arialbd.ttf"
        )

        pdfmetrics.registerFont(
            TTFont(
                "Arial",
                caminho_arial
            )
        )

        pdfmetrics.registerFont(
            TTFont(
                "Arial-Bold",
                caminho_arial_bold
            )
        )

        fonte_normal = "Arial"
        fonte_bold = "Arial-Bold"

    except Exception:

        pass


    # ========================================================
    # DOCUMENTO
    # ========================================================

    documento = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=2 * cm,
        leftMargin=2 * cm,
        topMargin=2 * cm,
        bottomMargin=2 * cm,
        title=(
            f"Relatório {tipo_relatorio} "
            f"- Monitoramento Térmico"
        )
    )


    estilos_base = (
        getSampleStyleSheet()
    )


    estilo_titulo = ParagraphStyle(
        "TituloRelatorio",
        parent=estilos_base["Title"],
        fontName=fonte_bold,
        fontSize=18,
        leading=22,
        alignment=TA_CENTER,
        spaceAfter=18
    )


    estilo_h1 = ParagraphStyle(
        "H1Relatorio",
        parent=estilos_base["Heading1"],
        fontName=fonte_bold,
        fontSize=14,
        leading=18,
        spaceBefore=12,
        spaceAfter=8
    )


    estilo_h2 = ParagraphStyle(
        "H2Relatorio",
        parent=estilos_base["Heading2"],
        fontName=fonte_bold,
        fontSize=12,
        leading=16,
        spaceBefore=10,
        spaceAfter=6
    )


    estilo_texto = ParagraphStyle(
        "TextoRelatorio",
        parent=estilos_base["BodyText"],
        fontName=fonte_normal,
        fontSize=10,
        leading=15,
        spaceAfter=7
    )


    estilo_lista = ParagraphStyle(
        "ListaRelatorio",
        parent=estilo_texto,
        leftIndent=14,
        firstLineIndent=-8,
        spaceAfter=4
    )


    elementos = []


    # ========================================================
    # TÍTULO
    # ========================================================

    elementos.append(
        Paragraph(
            f"Relatório {tipo_relatorio}",
            estilo_titulo
        )
    )

    elementos.append(
        Paragraph(
            "Sistema de Monitoramento Térmico",
            estilo_h2
        )
    )

    elementos.append(
        Spacer(
            1,
            10
        )
    )


    # ========================================================
    # FUNÇÃO PARA FORMATAR MARKDOWN SIMPLES
    # ========================================================

    def formatar_markdown(texto):

        texto = escape(texto.strip())

        texto = re.sub(
            r"\*\*(.+?)\*\*",
            r"<b>\1</b>",
            texto
        )

        texto = re.sub(
            r"`(.+?)`",
            r"<font name='Courier'>\1</font>",
            texto
        )

        return texto


    # ========================================================
    # PROCESSAR LINHAS
    # ========================================================

    linhas = texto_markdown.splitlines()

    i = 0

    while i < len(linhas):

        linha = linhas[i].strip()


        # Ignorar título Markdown original
        if linha.startswith("### Relatório"):
            i += 1
            continue


        # Linha vazia
        if not linha:
            elementos.append(
                Spacer(
                    1,
                    4
                )
            )

            i += 1
            continue


        # ====================================================
        # TABELA MARKDOWN
        # ====================================================

        if (
            linha.startswith("|")
            and
            linha.endswith("|")
        ):

            tabela_dados = []


            while (
                i < len(linhas)
                and
                linhas[i].strip().startswith("|")
                and
                linhas[i].strip().endswith("|")
            ):

                linha_tabela = (
                    linhas[i]
                    .strip()
                )


                celulas = [
                    celula.strip()
                    for celula
                    in linha_tabela.strip("|").split("|")
                ]


                # Ignorar linha separadora Markdown:
                # | --- | ---: |
                separador = all(
                    re.match(
                        r"^:?-+:?$",
                        celula.replace(
                            " ",
                            ""
                        )
                    )
                    for celula
                    in celulas
                )


                if not separador:

                    tabela_dados.append([
                        Paragraph(
                            formatar_markdown(
                                celula
                            ),
                            estilo_texto
                        )
                        for celula
                        in celulas
                    ])


                i += 1


            if tabela_dados:

                tabela = Table(
                    tabela_dados,
                    repeatRows=1,
                    hAlign="LEFT"
                )


                tabela.setStyle(
                    TableStyle([
                        (
                            "FONTNAME",
                            (0, 0),
                            (-1, -1),
                            fonte_normal
                        ),

                        (
                            "FONTNAME",
                            (0, 0),
                            (-1, 0),
                            fonte_bold
                        ),

                        (
                            "BACKGROUND",
                            (0, 0),
                            (-1, 0),
                            colors.HexColor(
                                "#EDEDED"
                            )
                        ),

                        (
                            "GRID",
                            (0, 0),
                            (-1, -1),
                            0.4,
                            colors.grey
                        ),

                        (
                            "VALIGN",
                            (0, 0),
                            (-1, -1),
                            "TOP"
                        ),

                        (
                            "LEFTPADDING",
                            (0, 0),
                            (-1, -1),
                            5
                        ),

                        (
                            "RIGHTPADDING",
                            (0, 0),
                            (-1, -1),
                            5
                        ),

                        (
                            "TOPPADDING",
                            (0, 0),
                            (-1, -1),
                            5
                        ),

                        (
                            "BOTTOMPADDING",
                            (0, 0),
                            (-1, -1),
                            5
                        )
                    ])
                )


                elementos.append(
                    tabela
                )

                elementos.append(
                    Spacer(
                        1,
                        10
                    )
                )


            continue


        # ====================================================
        # TÍTULOS
        # ====================================================

        if linha.startswith("## "):

            elementos.append(
                Paragraph(
                    formatar_markdown(
                        linha[3:]
                    ),
                    estilo_h1
                )
            )

            i += 1
            continue


        if linha.startswith("### "):

            elementos.append(
                Paragraph(
                    formatar_markdown(
                        linha[4:]
                    ),
                    estilo_h2
                )
            )

            i += 1
            continue


        # ====================================================
        # LISTA
        # ====================================================

        if linha.startswith("- "):

            elementos.append(
                Paragraph(
                    "• "
                    + formatar_markdown(
                        linha[2:]
                    ),
                    estilo_lista
                )
            )

            i += 1
            continue


        # Lista numerada
        if re.match(
            r"^\d+\.\s",
            linha
        ):

            elementos.append(
                Paragraph(
                    formatar_markdown(
                        linha
                    ),
                    estilo_lista
                )
            )

            i += 1
            continue


        # ====================================================
        # PARÁGRAFO NORMAL
        # ====================================================

        elementos.append(
            Paragraph(
                formatar_markdown(
                    linha
                ),
                estilo_texto
            )
        )

        i += 1


    # ========================================================
    # GERAR PDF
    # ========================================================

    documento.build(
        elementos
    )

    pdf = buffer.getvalue()

    buffer.close()

    return pdf

def normalizar_moeda_relatorio(texto):
    if not texto:
        return texto

    texto = texto.replace("R`", "R$")
    texto = texto.replace("R´", "R$")
    texto = texto.replace("R’", "R$")
    texto = texto.replace("R'", "R$")
    texto = texto.replace("R $", "R$")
    texto = texto.replace("R $", "R$")

    return texto
