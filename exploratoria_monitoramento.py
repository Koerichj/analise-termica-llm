import pandas as pd
import streamlit as st
import plotly.express as px

from function_monitoramento import TARIFA_KWH, formatar_valor, total_periodo


# ============================================================
# CONFIGURAÇÃO DA PÁGINA
# ============================================================

st.title("Análise Exploratória")
st.divider()


# ============================================================
# VERIFICAR BASE
# ============================================================

if "monitoramento_df" not in st.session_state:
    st.warning(
        "Carregue e processe uma base primeiro na etapa ETL."
    )
    st.stop()


# Trabalhar com cópia para não alterar o DataFrame da sessão
df = st.session_state["monitoramento_df"].copy()


# ============================================================
# TRATAMENTO DA DATA
# ============================================================

df["dt_registro"] = pd.to_datetime(
    df["dt_registro"],
    errors="coerce"
)

# Remover timezone caso ainda exista
if df["dt_registro"].dt.tz is not None:
    df["dt_registro"] = (
        df["dt_registro"]
        .dt.tz_localize(None)
    )

# Remover registros sem data válida
datas_invalidas = int(df["dt_registro"].isna().sum())
if datas_invalidas:
    st.warning(f"{datas_invalidas:,} registros com data inválida foram excluídos.")

df = (
    df
    .dropna(subset=["dt_registro"])
    .sort_values("dt_registro")
)


if df.empty:
    st.error("Não existem registros válidos para análise.")
    st.stop()


# ============================================================
# FILTRO DE PERÍODO
# ============================================================

st.subheader("Período de análise")

periodo = st.segmented_control(
    "Selecione o período",
    options=[
        "1 dia",
        "7 dias",
        "30 dias",
        "90 dias",
        "Todo período",
        "Personalizado"
    ],
    default="30 dias"
)


data_min = df["dt_registro"].min()
data_max = df["dt_registro"].max()


if periodo == "1 dia":

    inicio = data_max - pd.Timedelta(days=1)
    fim = data_max


elif periodo == "7 dias":

    inicio = data_max - pd.Timedelta(days=7)
    fim = data_max


elif periodo == "30 dias":

    inicio = data_max - pd.Timedelta(days=30)
    fim = data_max


elif periodo == "90 dias":

    inicio = data_max - pd.Timedelta(days=90)
    fim = data_max


elif periodo == "Todo período":

    inicio = data_min
    fim = data_max


else:

    col_data1, col_data2 = st.columns(2)

    data_inicial = col_data1.date_input(
        "Data inicial",
        value=data_min.date(),
        min_value=data_min.date(),
        max_value=data_max.date()
    )

    data_final = col_data2.date_input(
        "Data final",
        value=data_max.date(),
        min_value=data_min.date(),
        max_value=data_max.date()
    )

    if data_inicial is None or data_final is None:
        st.info("Informe as duas datas para aplicar o período personalizado.")
        st.stop()

    inicio = pd.Timestamp(data_inicial)

    fim = (
        pd.Timestamp(data_final)
        + pd.Timedelta(days=1)
        - pd.Timedelta(nanoseconds=1)
    )


# ============================================================
# VALIDAR PERÍODO
# ============================================================

if inicio > fim:

    st.error(
        "A data inicial não pode ser maior que a data final."
    )

    st.stop()


# ============================================================
# APLICAR FILTRO DE PERÍODO
# ============================================================

df_periodo = df[
    (df["dt_registro"] >= inicio)
    &
    (df["dt_registro"] <= fim)
].copy()


if df_periodo.empty:

    st.warning(
        "Não existem registros no período selecionado."
    )

    st.stop()


st.caption(
    f"Período analisado: "
    f"{inicio.strftime('%d/%m/%Y %H:%M')} até "
    f"{fim.strftime('%d/%m/%Y %H:%M')} "
    f"• {len(df_periodo):,} registros"
)


# ============================================================
# FILTRO POR ESTADO DO PROCESSO
# ============================================================

st.subheader("Filtro operacional")

estados = sorted(
    df_periodo["ds_estado_processo"]
    .dropna()
    .unique()
    .tolist()
)


estado = st.selectbox(
    "Estado do processo",
    ["Todos"] + estados
)


if estado == "Todos":

    base = df_periodo.copy()

else:

    base = df_periodo[
        df_periodo["ds_estado_processo"] == estado
    ].copy()


if base.empty:

    st.warning(
        "Não existem registros para o estado selecionado."
    )

    st.stop()


st.caption(
    f"Estado analisado: {estado} "
    f"• {len(base):,} registros"
)


st.divider()


# ============================================================
# MÉTRICAS PRINCIPAIS
# ============================================================

col1, col2, col3, col4 = st.columns(4)


col1.metric(
    "Registros",
    f"{len(base):,}"
)


col2.metric(
    "Temperatura média de entrada",
    formatar_valor(base["nr_temperatura_entrada"].mean(), " °C")
)


col3.metric(
    "Temperatura média de saída",
    formatar_valor(base["nr_temperatura_saida"].mean(), " °C")
)


col4.metric(
    "ΔT médio",
    formatar_valor(base["nr_delta_t"].mean(), " °C")
)


st.divider()


# ============================================================
# SEGUNDA LINHA DE INDICADORES
# ============================================================

col1, col2, col3, col4 = st.columns(4)


col1.metric(
    "Vazão média",
    formatar_valor(base["nr_vazao_l_min"].mean(), " L/min")
)


energia_periodo = total_periodo(base, "nr_energia_kwh")

col2.metric(
    "Energia térmica no período",
    formatar_valor(energia_periodo, " kWh")
)


desempenho = base.get(
    "nr_desempenho_termico_percentual", pd.Series(dtype=float)
)

col3.metric(
    "Desempenho térmico médio",
    formatar_valor(desempenho.mean(), " %")
)


economia_periodo = energia_periodo * TARIFA_KWH
col4.metric(
    "Economia financeira estimada",
    "N/D" if pd.isna(economia_periodo) else f"R$ {economia_periodo:.2f}",
)
st.caption(
    "A energia depende dos valores fornecidos por leitura. A economia usa a tarifa "
    "de referência e o desempenho térmico expressa o atendimento a um ΔT de projeto."
)

st.divider()


# ============================================================
# GRANULARIDADE AUTOMÁTICA
# ============================================================

duracao = fim - inicio


if duracao <= pd.Timedelta(days=2):

    frequencia = "5min"
    descricao_frequencia = "5 minutos"


elif duracao <= pd.Timedelta(days=7):

    frequencia = "30min"
    descricao_frequencia = "30 minutos"


elif duracao <= pd.Timedelta(days=31):

    frequencia = "2h"
    descricao_frequencia = "2 horas"


elif duracao <= pd.Timedelta(days=90):

    frequencia = "6h"
    descricao_frequencia = "6 horas"


else:

    frequencia = "1D"
    descricao_frequencia = "1 dia"


# ============================================================
# CRIAR BASE AGREGADA PARA GRÁFICOS TEMPORAIS
# ============================================================

base_grafico = (
    base
    .dropna(subset=["dt_registro"])
    .set_index("dt_registro")
    .resample(frequencia)
    .agg({
        "nr_temperatura_entrada": "mean",
        "nr_temperatura_saida": "mean",
        "nr_delta_t": "mean",
        "nr_vazao_l_min": "mean"
    })
    .reset_index()
)


# Remover intervalos completamente vazios
base_grafico = base_grafico.dropna(
    how="all",
    subset=[
        "nr_temperatura_entrada",
        "nr_temperatura_saida",
        "nr_delta_t",
        "nr_vazao_l_min"
    ]
)


st.caption(
    f"Os gráficos temporais utilizam médias "
    f"agregadas a cada {descricao_frequencia}."
)


# ============================================================
# TEMPERATURAS AO LONGO DO TEMPO
# ============================================================

st.subheader("Temperaturas ao longo do tempo")


fig_temperaturas = px.line(
    base_grafico,
    x="dt_registro",
    y=[
        "nr_temperatura_entrada",
        "nr_temperatura_saida"
    ],
    labels={
        "dt_registro": "Data/Hora",
        "value": "Temperatura (°C)",
        "variable": "Temperatura"
    }
)


fig_temperaturas.for_each_trace(
    lambda trace: trace.update(
        name={
            "nr_temperatura_entrada": "Entrada",
            "nr_temperatura_saida": "Saída"
        }.get(
            trace.name,
            trace.name
        )
    )
)


fig_temperaturas.update_layout(
    legend_title_text="Temperatura",
    hovermode="x unified"
)


fig_temperaturas.update_xaxes(
    title="Data/Hora"
)


st.plotly_chart(
    fig_temperaturas,
    width="stretch"
)


# ============================================================
# GANHO TÉRMICO - DELTA T
# ============================================================

st.subheader("Ganho térmico - ΔT")


fig_delta = px.line(
    base_grafico,
    x="dt_registro",
    y="nr_delta_t",
    labels={
        "dt_registro": "Data/Hora",
        "nr_delta_t": "ΔT (°C)"
    }
)


fig_delta.update_layout(
    hovermode="x unified"
)


st.plotly_chart(
    fig_delta,
    width="stretch"
)


# ============================================================
# DISTRIBUIÇÃO DO DELTA T
# ============================================================

st.subheader("Distribuição do ganho térmico")


fig_hist_delta = px.histogram(
    base,
    x="nr_delta_t",
    nbins=30,
    labels={
        "nr_delta_t": "ΔT (°C)",
        "count": "Quantidade de leituras"
    }
)


fig_hist_delta.update_layout(
    showlegend=False,
    yaxis_title="Quantidade de leituras"
)


st.plotly_chart(
    fig_hist_delta,
    width="stretch"
)


# ============================================================
# VAZÃO
# ============================================================

st.subheader("Vazão ao longo do tempo")


fig_vazao = px.line(
    base_grafico,
    x="dt_registro",
    y="nr_vazao_l_min",
    labels={
        "dt_registro": "Data/Hora",
        "nr_vazao_l_min": "Vazão (L/min)"
    }
)


fig_vazao.update_layout(
    hovermode="x unified"
)


st.plotly_chart(
    fig_vazao,
    width="stretch"
)


# ============================================================
# DISTRIBUIÇÃO DOS ESTADOS DO PROCESSO
# ============================================================

st.subheader("Distribuição dos estados do processo")


# Aqui usamos df_periodo propositalmente,
# pois queremos comparar todos os estados dentro do período.
estados_contagem = (
    df_periodo["ds_estado_processo"]
    .value_counts()
    .rename_axis("estado")
    .reset_index(name="quantidade")
)


fig_estados = px.bar(
    estados_contagem,
    x="estado",
    y="quantidade",
    text_auto=True,
    labels={
        "estado": "Estado",
        "quantidade": "Quantidade de leituras"
    }
)


fig_estados.update_layout(
    showlegend=False
)


st.plotly_chart(
    fig_estados,
    width="stretch"
)


# ============================================================
# DESEMPENHO TÉRMICO POR ESTADO
# ============================================================

st.subheader("Desempenho térmico médio por estado")


if (
    "nr_desempenho_termico_percentual" in df_periodo
    and df_periodo["nr_desempenho_termico_percentual"].notna().any()
    and df_periodo.loc[
        df_periodo["nr_desempenho_termico_percentual"].notna(), "ds_estado_processo"
    ].notna().any()
):
    desempenho_estado = (
        df_periodo
        .groupby(
            "ds_estado_processo",
            as_index=False
        )
        ["nr_desempenho_termico_percentual"]
        .mean()
        .dropna(subset=["nr_desempenho_termico_percentual"])
    )


    desempenho_estado = desempenho_estado.rename(
        columns={
            "ds_estado_processo": "estado",
            "nr_desempenho_termico_percentual":
                "desempenho_medio"
        }
    )


    fig_desempenho = px.bar(
        desempenho_estado,
        x="estado",
        y="desempenho_medio",
        text_auto=".1f",
        labels={
            "estado": "Estado",
            "desempenho_medio":
                "Desempenho térmico médio (%)"
        }
    )


    fig_desempenho.update_layout(
        showlegend=False
    )


    st.plotly_chart(
        fig_desempenho,
        width="stretch"
    )
else:
    st.info("N/D: sem dados de desempenho térmico associados a estados.")

# ============================================================
# CRITICIDADE
# ============================================================

if "ds_criticidade" in df_periodo.columns:

    st.subheader(
        "Distribuição das criticidades"
    )


    criticidades = (
        df_periodo["ds_criticidade"]
        .fillna("Não informado")
        .value_counts()
        .rename_axis("criticidade")
        .reset_index(name="quantidade")
    )


    fig_criticidade = px.bar(
        criticidades,
        x="criticidade",
        y="quantidade",
        text_auto=True,
        labels={
            "criticidade": "Criticidade",
            "quantidade":
                "Quantidade de leituras"
        }
    )


    fig_criticidade.update_layout(
        showlegend=False
    )


    st.plotly_chart(
        fig_criticidade,
        width="stretch"
    )
