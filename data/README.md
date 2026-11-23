# Dados de exemplo

`amostra_leituras.csv` é **sintético**, criado apenas para teste estrutural e documentação. Não contém medições industriais reais.

## Colunas

- `timestamp`: data/hora no formato ISO 8601 (sem fuso informado no exemplo)
- `origem`: origem fictícia da leitura
- `estado_processo`: estado do ciclo (`RECARREGANDO`, `AQUECENDO`, `MATURANDO`, `TRANSFERINDO`)
- `ciclo`: identificador do ciclo
- `temperatura_entrada` e `temperatura_saida`: °C
- `vazao_l_min`: litros por minuto
- `valvula_entrada` e `valvula_saida`: 0/1 (0 = fechada, 1 = aberta)
- `nivel_tubulacao_percentual`: nível percentual de referência
- `tempo_maturacao_min`: duração configurada em minutos
- `delta_t`: temperatura de saída menos temperatura de entrada (°C)

## Contrato de entrada

O ETL aceita os nomes acima e o esquema original. Os campos obrigatórios no esquema original são `dt_registro`, `ds_estado_processo`, `nr_temperatura_entrada`, `nr_temperatura_saida` e `nr_vazao_l_min`. Se o arquivo trouxer duas colunas para o mesmo campo, o ETL concilia valores equivalentes e complementares e rejeita divergências. Estados são normalizados para maiúsculas. Válvulas aceitam os rótulos aberta/fechada, os códigos 1/0 e valores booleanos.

Datas com offset são convertidas para o horário de São Paulo. Datas sem offset mantêm o horário informado por padrão. Para exportações com horários UTC sem offset, selecione **UTC** no ETL para convertê-los para São Paulo, reproduzindo a interpretação anterior da aplicação. Prefira datas ISO 8601 com offset numérico ou Z. Siglas e nomes de fuso fora de UTC/GMT são tratados como inválidos. As análises excluem datas inválidas e o ETL informa quantas foram encontradas.

O ΔT fornecido tem prioridade. Quando faltar, a aplicação usa a diferença entre as temperaturas válidas da mesma leitura. As médias e o desvio-padrão amostral usam os valores disponíveis. Energia (kWh) e volume (L) somam os valores por leitura quando a cobertura do recorte é completa. Desempenho térmico usa o indicador fornecido pela origem. A economia estimada multiplica a energia do recorte pela tarifa de referência de R$ 0,52/kWh. Indicadores indisponíveis aparecem como `N/D`.

Na amostra, 5 das 8 leituras são conformes. As 3 leituras de recarga têm vazão zero, abaixo do critério existente de vazão superior a 0,5 L/min nesse estado. A amostra também não fornece energia, volume nem desempenho térmico.
