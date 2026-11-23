from zipfile import BadZipFile

import streamlit as st
import pandas as pd

from function_monitoramento import preparar_base


st.title("ETL - Monitoramento Térmico")

st.caption(
    "Extração, transformação e preparação "
    "dos dados do sistema de monitoramento."
)

st.divider()


arquivo = st.file_uploader(
    "Selecione a base de dados",
    type=["csv", "xlsx"]
)


if arquivo is not None:

    try:
        df = pd.read_csv(arquivo) if arquivo.name.lower().endswith(".csv") else pd.read_excel(arquivo)
    except (ValueError, OSError, BadZipFile):
        st.error("Não foi possível ler o arquivo. Verifique se é um CSV ou XLSX válido.")
        st.stop()

    st.subheader("Dados originais")

    st.dataframe(
        df.head(100),
        width="stretch"
    )

    fuso_sem_offset = st.selectbox(
        "Fuso das datas sem offset",
        ["America/Sao_Paulo", "UTC"],
        help="Use UTC se a origem exportou horários UTC sem indicar o fuso. Datas com offset são convertidas automaticamente.",
    )
    st.caption("As datas processadas são exibidas no horário de São Paulo.")

    if st.button("Processar dados"):

        try:
            base = preparar_base(df, fuso_sem_offset=fuso_sem_offset)
        except ValueError as erro:
            st.error(str(erro))
            st.stop()

        st.session_state["monitoramento_df"] = base

        st.session_state.pop("relatorio_ia", None)
        st.session_state.pop("relatorio_contexto", None)

        datas_invalidas = int(base["dt_registro"].isna().sum())
        if datas_invalidas:
            st.warning(f"{datas_invalidas:,} registros com data inválida serão excluídos das análises.")

        st.success(
            f"{len(base):,} registros processados."
        )

        st.subheader("Dados tratados")

        st.dataframe(
            base.head(100),
            width="stretch"
        )