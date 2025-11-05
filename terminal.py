# ==========================================================
# 1. IMPORTS
# ==========================================================
import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.express as px
from datetime import date
import requests 
import plotly.graph_objects as go 

# ==========================================================
# 2. VARIÁVEIS GLOBAIS
# ==========================================================
### PARÂMETROS INICIAIS ###
ACAO_PADRAO = "PETR4.SA" 
DATA_INICIO_PADRAO = "2023-01-01"

# NOVAS VARIÁVEIS PARA KPIS
TICKERS_KPIS = ["^BVSP", "USDBRL=X", "EURBRL=X", "BTC-USD", "ETH-USD"] # Ibovespa, Dólar/Real, Euro/Real, Bitcoin, Ethereum

# Suas Chaves de API
ALPHA_VANTAGE_KEY = "32KLQPTJOM2PCM6A" 
NEWS_API_KEY = "422d1eea07014251afa314afec0e6e41" 



# ==========================================================
# 3. FUNÇÕES DE BUSCA DE DADOS
# ==========================================================
@st.cache_data
def buscar_dados_historicos(ticker, data_inicio):
    """ Busca dados históricos usando yfinance. """
    try:
        data_inicio_str = data_inicio.strftime("%Y-%m-%d")
        dados = yf.download(ticker, start=data_inicio_str, end=date.today().strftime("%Y-%m-%d"), progress=False)
        return dados
    except Exception as e:
        return pd.DataFrame()

@st.cache_data(ttl=60)
def buscar_cotacoes_atuais(ticker):
    """ Busca o preço atual, variação e volume de um ticker. """
    try:
        ativo = yf.Ticker(ticker)
        info = ativo.info
        preco_atual = info.get('regularMarketPrice')
        variacao = info.get('regularMarketChangePercent')
        volume = info.get('volume')
        return preco_atual, variacao, volume
    except Exception:
        return None, None, None
    

### FUNÇÃO: BUSCAR DADOS PARA O TOP N ###
@st.cache_data(ttl=120) # Atualiza a cada 2 minutos
def buscar_top_performances():
    """
    Busca dados atuais de uma lista de tickers e classifica em Top Gainers/Losers.
    """
    TICKERS_MERCADO = ["PETR4.SA", "VALE3.SA", "ITUB4.SA", "BBDC4.SA", "MGLU3.SA", "BBAS3.SA", "AMER3.SA", "HAPV3.SA", "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "TSLA", "NFLX"]
    dados_tabela = []
    
    for ticker in TICKERS_MERCADO:
        try:
            ativo = yf.Ticker(ticker)
            info = ativo.info
            
            preco_atual = info.get('regularMarketPrice')
            abertura = info.get('regularMarketOpen')
            maior_alta = info.get('dayHigh')
            maior_baixa = info.get('dayLow')
            fechamento_anterior = info.get('previousClose')
            volume_atual = info.get('volume')
            
            if preco_atual and fechamento_anterior:
                variacao_dia = ((preco_atual - fechamento_anterior) / fechamento_anterior) * 100
            else:
                variacao_dia = 0

            dados_tabela.append({
                "Ticker": ticker.replace(".SA", ""), "Abertura": abertura, "Alta": maior_alta,
                "Baixa": maior_baixa, "Fech. Ant.": fechamento_anterior, "Volume": volume_atual,
                "Variação (%)": variacao_dia, "Preço Atual": preco_atual
            })
        except Exception:
            continue

    df = pd.DataFrame(dados_tabela)
    if df.empty:
        return pd.DataFrame(), pd.DataFrame()

    df = df.sort_values(by="Variação (%)", ascending=False)
    
    top_gainers = df.head(6).copy()
    top_losers = df.tail(6).copy()
    
    return top_gainers, top_losers


@st.cache_data(ttl=600) 
def buscar_noticias(query="finanças"):
    """
    Busca notícias de mercado usando NewsAPI, limitando a fontes financeiras e de negócios.
    """
    if not NEWS_API_KEY:
        return [] 
        
    dominios_financeiros = "exame.com, infomoney.com.br, valor.globo.com, folha.uol.com.br, cnn.com, bloomberg.com"
    
    url = (f"https://newsapi.org/v2/everything?q={query}&language=pt&pageSize=5"
        f"&sortBy=publishedAt&apiKey={NEWS_API_KEY}&domains={dominios_financeiros}")
    
    try:
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        if data['status'] == 'ok':
            return [{"title": a['title'], "source": a['source']['name'], "url": a['url']} for a in data['articles']]
    except requests.exceptions.RequestException:
        return []

@st.cache_data(ttl=600) 
def buscar_noticias_av(ticker, limite=5):
    """ Busca notícias específicas de um ticker no Alpha Vantage. """
    if not ALPHA_VANTAGE_KEY:
        return []
    ticker_av = ticker.replace(".SA", "")
    url = (f"https://www.alphavantage.co/query?function=NEWS_SENTIMENT&"
           f"tickers={ticker_av}&limit={limite}&apikey={ALPHA_VANTAGE_KEY}")
    try:
        response = requests.get(url)
        response.raise_for_status() 
        data = response.json()
        if 'feed' in data and data['feed']:
            noticias_av = []
            for artigo in data['feed']:
                noticias_av.append({"title": artigo['title'], "source": f"AV ({artigo['source']})", "url": artigo['url']})
            return noticias_av
    except requests.exceptions.RequestException:
        return []
    return []

### FUNÇÃO: BUSCAR DADOS DE MOEDAS E CRIPTOS ###
@st.cache_data(ttl=60) # Atualiza a cada 1 minuto
def buscar_cotacoes_kpis(tickers_list):
    """
    Busca cotacões e a variação diária para uma lista de ativos (Moedas/Criptos).
    """
    dados_kpis = {}
    for ticker in tickers_list:
        try:
            ativo = yf.Ticker(ticker)
            info = ativo.info
            
            preco_atual = info.get('regularMarketPrice')
            fechamento_anterior = info.get('previousClose')
            
            variacao = 0
            if preco_atual and fechamento_anterior:
                variacao = ((preco_atual - fechamento_anterior) / fechamento_anterior) * 100
                
            nome_ativo = info.get('shortName', ticker)
            
            dados_kpis[ticker] = {
                "Nome": nome_ativo,
                "Preco": preco_atual,
                "Variacao": variacao
            }
        except Exception:
            dados_kpis[ticker] = {"Nome": ticker, "Preco": None, "Variacao": None}
            continue
            
    return dados_kpis

# ==========================================================
# 4. INTERFACE STREAMLIT (def main())
# ==========================================================
def main():
    # --- CONFIGURAÇÃO E CSS (Fundo Preto + Sidebar Ativa) ---
    st.set_page_config(layout="wide", page_title="Terminal Financeiro Gratuito")

    st.markdown("""
        <style>
        .stApp {background-color: #000000; color: #FFFFFF;}
        .block-container {padding-top: 2rem; padding-bottom: 0rem; padding-left: 2rem; padding-right: 2rem;}
        [data-testid="stSidebar"] {display: block;}
        /* Ajuste fino para o título */
        h1 {font-size: 2.5rem; margin-top: 0px;}
        </style>
        """, unsafe_allow_html=True)

    # --- 1. CONFIGURAÇÕES NA BARRA LATERAL (SIDEBAR) ---
    st.sidebar.header("Configurações do Ativo")
    
    ticker_input = st.sidebar.text_input("Código da Ação/Cripto (Ticker):", value=ACAO_PADRAO).upper()
    data_inicio_input = st.sidebar.date_input("Data de Início do Histórico:", value=pd.to_datetime(DATA_INICIO_PADRAO), min_value=pd.to_datetime('1990-01-01'), max_value=date.today())
    
    # --- 2. TÍTULO PRINCIPAL (CENTRALIZADO CORRIGIDO) ---
    col_t1, col_t2, col_t3 = st.columns([1, 2, 1]) 
    
    with col_t2:
        st.title("Terminal F(ree)nance - Dashboard") 
    st.markdown("---") 

    # 3. Busca dos Dados e Cálculos (SMA)
    dados_historicos = buscar_dados_historicos(ticker_input, data_inicio_input)
    
    if dados_historicos.empty:
        st.error(f"Não foi possível carregar dados para {ticker_input}. Verifique o ticker.")
        return

    if isinstance(dados_historicos.columns, pd.MultiIndex):
        dados_historicos.columns = dados_historicos.columns.droplevel(1)
        
    dados_historicos['SMA_20'] = dados_historicos['Close'].rolling(window=20).mean()
    dados_historicos['SMA_50'] = dados_historicos['Close'].rolling(window=50).mean()

    # ==========================================================
    # 5. LAYOUT: QUDRANTES SUPERIORES (Q1 e Q2)
    # ==========================================================
    col_kpi, col_news = st.columns([1, 2])
    
    # --- QUADRANTE 1 (Superior Esquerdo): HEATMAP DE PERFORMANCE UNIFICADO ---
    # ==========================================================
    # 5. LAYOUT: QUDRANTES SUPERIORES (Q1 e Q2)
    # ==========================================================
    col_kpi, col_news = st.columns([1, 2])
    
    # --- QUADRANTE 1 (Superior Esquerdo): VISÃO RÁPIDA (KPIs) e HEATMAP ---
    with col_kpi:
        st.subheader("Visão Rápida do Mercado")
        
        # --- 1. Exibição de Moedas e Criptos (KPIs) ---
        st.markdown("#### Índices, Moedas e Criptos")
        
        kpi_data = buscar_cotacoes_kpis(TICKERS_KPIS)
        
        # Divide o espaço em 3 colunas para os KPIs (2 linhas de 3)
        cols_kpi = st.columns(3) 
        
        for i, (ticker, data) in enumerate(kpi_data.items()):
            
            # Formatação para o st.metric
            preco_str = f"R$ {data['Preco']:,.4f}" if "=" in ticker else f"{data['Preco']:,.2f}"
            variacao_str = f"{data['Variacao']:,.2f} %" if data['Variacao'] is not None else "N/A"
            delta_color = "inverse" if (data['Variacao'] or 0) < 0 else "normal" # Verde para positivo, vermelho para negativo
            
            with cols_kpi[i % 3]: # i % 3 garante que o índice varia entre 0, 1 e 2
                if data['Preco'] is not None:
                    st.metric(
                        label=data['Nome'],
                        value=preco_str.replace(",", "X").replace(".", ",").replace("X", "."), # Troca de separador de milhar/decimal
                        delta=variacao_str.replace(",", "X").replace(".", ",").replace("X", "."),
                        delta_color=delta_color
                    )
                else:
                    st.metric(label=data['Nome'], value="N/A", delta="N/A")

        st.markdown("---") # Separador visual

        # --- 2. Heatmap de Performance (Código existente) ---
        st.markdown("#### Melhores e Piores Ativos do Dia")
        
        top_gainers, top_losers = buscar_top_performances()

        if not top_gainers.empty:
            
            # --- Combinação e Estilo ---
            def aplicar_estilo_performance(val):
                """Aplica cor de fundo e cor da fonte com base na Variação (%)"""
                try:
                    val_float = float(val) 
                except:
                    return '' 

                if val_float >= 0:
                    return 'background-color: #5cb85c; color: black; font-weight: bold;'
                else:
                    return 'background-color: #d9534f; color: white; font-weight: bold;'

            df_final = pd.concat([top_gainers, top_losers], ignore_index=True)

            cols_exibidas = ['Ticker', 'Preço Atual', 'Variação (%)', 'Volume']
            
            st.dataframe(
                df_final[cols_exibidas].style.applymap(
                    aplicar_estilo_performance, 
                    subset=pd.IndexSlice[:, ['Variação (%)']]
                ).format({
                    'Preço Atual': '{:.2f}',
                    'Variação (%)': '{:.2f}',
                    'Volume': '{:.0f}'
                }),
                hide_index=True,
                use_container_width=True,
            )
        else:
            st.warning("Não foi possível carregar dados de Performance.")
    
    # --- QUADRANTE 2 (Superior Direito): NOTÍCIAS (LIMPEZA FINAL) ---
    # --- QUADRANTE 2 (Superior Direito): NOTÍCIAS (CORREÇÃO DE ALINHAMENTO) ---
# --- QUADRANTE 2 (Superior Direito): NOTÍCIAS (CORREÇÃO FINAL DE ALINHAMENTO) ---
    with col_news:
        # st.subheader("Manchetes de Mercado") <-- REMOVIDO
        # Usaremos um título de Markdown simples para minimizar o padding:
        st.markdown("### Manchetes de Mercado")
        
        # 1. Busca dos dados de notícia (definido em outro lugar)
        termo_geral = "Mercado OR Negócios" 
        noticias_newsapi = buscar_noticias(query=termo_geral) 
        noticias_av = buscar_noticias_av(ticker_input, limite=3) 
        noticias_combinadas = noticias_av + noticias_newsapi 
        
        # 2. Exibição
        if noticias_combinadas:
            for artigo in noticias_combinadas:
                # Usamos um tamanho de fonte menor (markdown H6) para simular densidade
                st.markdown(f"###### **[{artigo['title']}]({artigo['url']})** \n *{artigo['source']}*")
                # Sem st.markdown("---") para máximo alinhamento
        else:
            st.info("Não foi possível carregar notícias.")
    
    # ==========================================================
    # 6. LAYOUT: QUDRANTES INFERIORES (Q3 e Q4)
    # ==========================================================
    st.markdown("---") 
    col_grafico_q3, col_dados_q4 = st.columns([1, 1]) 

    # --- QUADRANTE 3 (Inferior Esquerdo): GRÁFICO ---
    with col_grafico_q3:
        st.header(f"Gráfico Histórico de Análise: {ticker_input}")

        # Criação do Gráfico
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=dados_historicos.index, y=dados_historicos['Close'], name='Fechamento', line=dict(color='white'), hovertemplate='Fechamento: %{y:,.2f}<extra></extra>'))
        fig.add_trace(go.Scatter(x=dados_historicos.index, y=dados_historicos['SMA_20'], name='Média Móvel 20', line=dict(color='yellow', dash='dot'), hovertemplate='Média Móvel 20: %{y:,.2f}<extra></extra>'))
        fig.add_trace(go.Scatter(x=dados_historicos.index, y=dados_historicos['SMA_50'], name='Média Móvel 50', line=dict(color='cyan'), hovertemplate='Média Móvel 50: %{y:,.2f}<extra></extra>'))

        fig.update_layout(
            title=f"Preço de Fechamento e Médias Móveis de {ticker_input}",
            xaxis_title="Data",
            yaxis_title="Preço",
            hovermode="x unified",
            template="plotly_dark",
            height=450
        )
        
        st.plotly_chart(fig, use_container_width=True)
        
# --- QUADRANTE 4 (Inferior Direito): DADOS BRUTOS ---
    with col_dados_q4:
        st.header(f"Dados Brutos de {ticker_input}")
        
        # Exibe apenas colunas originais (sem SMA para limpeza)
        df_display = dados_historicos.drop(columns=['SMA_20', 'SMA_50'])
        
        # >>> CÓDIGO CORRIGIDO: ALTURA LIMITADA PARA 12 LINHAS <<<
        # Reduzindo a altura para 500px, o que limita a visualização a cerca de 12-14 linhas.
        st.dataframe(df_display, use_container_width=True, height=450)


if __name__ == "__main__":
    main()