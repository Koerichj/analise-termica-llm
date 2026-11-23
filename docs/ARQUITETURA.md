# Arquitetura

## Fluxo de referência

1. **Fonte:** leituras do sistema industrial (origem real) ou CSV sintético (demonstração).
2. **ETL:** conversão de tipos, checagem de ausências, ordenação temporal e validação de intervalos.
3. **Indicadores:** cálculo de ΔT quando ausente, estatísticas de temperatura e vazão, conformidade por leitura e agregação de energia e volume fornecidos pela origem.
4. **Contexto do LLM:** fornecimento de métricas já calculadas, período, quantidade de registros, advertências e regras do processo.
5. **LLM:** síntese, explicação e recomendações contextualizadas; nenhuma medição deve ser inventada.
6. **Streamlit:** dados, gráficos, texto gerado e ressalvas ao usuário.

## Limites de responsabilidade

**Código determinístico:** calcula indicadores, filtra registros, detecta dados ausentes, gera tabelas.

**LLM:** descreve tendências, contextualiza informações fornecidas, comunica hipóteses e limitações. Não deve alterar valores calculados nem apresentar hipótese como diagnóstico confirmado.

## Diagnóstico e impacto da revisão

- A branch local `main` e a remota apontavam para `5ac559a`. A alteração local preexistente da URL de clonagem foi preservada. A busca por padrões conhecidos de segredos no histórico não encontrou ocorrências. A base privada local e o `.env` estão no ignore.
- O ETL esperava os nomes de produção e interpretava datas sem offset como UTC. A normalização compartilhada permite usar a amostra e torna explícita a escolha do fuso das datas sem offset. Em São Paulo, a seleção padrão mantém o horário informado. Selecione UTC para conservar os recortes das exportações que usavam o comportamento antigo.
- As somas de campos vazios retornavam zero e as de campos parcialmente preenchidos pareciam totais completos. Agora energia, volume e economia ficam indisponíveis com cobertura incompleta. A economia nas duas páginas aplica a tarifa antes do arredondamento. Antes, o relatório arredondava primeiro a energia a quatro casas, o que podia alterar o valor em um centavo no limiar de arredondamento.
- As regras de estados, válvulas e limiar de vazão de 0,5 L/min foram preservadas. Conformidade percentual considera apenas leituras avaliáveis. Sua proporção representa registros, e a amostragem pode ser irregular. O desempenho térmico fornecido segue a referência do projeto de 15 °C. A economia estimada depende da tarifa de referência e a avaliação de eficiência física exige balanço energético independente.
- O identificador de modelo estava fixo em dois scripts, havia instruções duplicadas e o erro bruto podia vazar detalhes. A integração configura o modelo pelo ambiente, envia as instruções de `prompts/analise_termica.md` separadamente do resumo JSON e retorna mensagens controladas. O aplicativo mantém a estrutura específica de cada tipo de relatório.
- Todas as dependências diretas fixadas em `requirements.txt` são usadas, incluindo `openpyxl` para XLSX. A `.venv` local existente apontava para uma instalação Python indisponível. Os testes foram executados em Python 3.11 com as versões diretas fixadas pelo projeto.
