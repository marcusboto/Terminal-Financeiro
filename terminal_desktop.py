# ==========================================================
# 1. IMPORTS (FINAL CONSOLIDADO PARA PyQt5 + Matplotlib)
# ==========================================================
import sys
import pandas as pd
import yfinance as yf
import requests
from datetime import date
import time
# Imports Matplotlib NATIVOS
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
import matplotlib.dates as mdates

# 💡 MÓDULOS PyQt5 (INTERFACE GRÁFICA)
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout,
    QHBoxLayout, QLabel, QLineEdit, QPushButton, QGridLayout,
    QFrame, QTabWidget, QTableWidget, QTableWidgetItem, QHeaderView, QScrollArea,
    QTextEdit 
)
# PyQt5 - Core (Threading, Signals e Timer)
from PyQt5.QtCore import (
    Qt, QTimer, QRunnable, QThreadPool, pyqtSignal, QObject
)
# PyQt5 - Gráficos e Estilo
from PyQt5.QtGui import (
    QFont, QPalette, QColor, QBrush, 
    QIntValidator 
)
# REMOVIDOS: PyQtWebEngine e Plotly.js!

# ==========================================================
# 2. VARIÁVEIS GLOBAIS (SINTAXE CORRIGIDA - REMOVIDO U+00A0)
# ==========================================================
ACAO_PADRAO = "PETR4.SA" 
DATA_INICIO_PADRAO = "2023-01-01"
TICKERS_KPIS = ["^BVSP", "USDBRL=X", "EURBRL=X", "BTC-USD", "ETH-USD", "BNO"] 
TICKER_IBOVESPA = "^BVSP"

TICKERS_TAPE = ["USDBRL=X", "^BVSP", "^N225", "000001.SS", "^MERV"]

TICKERS_S_AND_P = ["^GSPC", "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "TSLA", "NFLX", "JPM"]
TICKERS_CRYPTO = ["BTC-USD", "ETH-USD", "SOL-USD", "ADA-USD", "XRP-USD", "DOGE-USD", "DOT-USD"]

TICKERS_COMMODITIES = ["CL=F", "GC=F", "SI=F", "KC=F", "NG=F"] 
TICKER_CDI = "BNDX" 

# SUAS Chaves de API (Sintaxe limpa)
ALPHA_VANTAGE_KEY = "32KLQPTJOM2PCM6A" 
NEWS_API_KEY = "422d1eea07014251afa314afec0e6e41" 

# ==========================================================
# 2.5. THREADING UTILITY CLASSES (Para não bloquear a UI)
# ==========================================================
class WorkerSignals(QObject):
    """ Define os sinais disponíveis do QRunnable Worker. """
    finished = pyqtSignal()
    error = pyqtSignal(tuple)
    result = pyqtSignal(object)

class Worker(QRunnable):
    """ Worker thread para executar funções de longa duração. """
    def __init__(self, fn, *args, **kwargs):
        super(Worker, self).__init__()
        self.fn = fn
        self.args = args
        self.kwargs = kwargs
        self.signals = WorkerSignals()
        self.setAutoDelete(True) 

    def run(self):
        """ Inicializa o worker e executa a função de longa duração. """
        try:
            result = self.fn(*self.args, **self.kwargs)
        except:
            import traceback, sys
            traceback.print_exc()
            exctype, value = sys.exc_info()[:2]
            self.signals.error.emit((exctype, value, traceback.format_exc()))
        else:
             self.signals.result.emit(result)
        finally:
            self.signals.finished.emit()


# ==========================================================
# 3. FUNÇÕES DE BUSCA DE DADOS (COM RETRY PARA MITIGAÇÃO DE ERRO 401)
# ==========================================================

# Função auxiliar para tentar a busca mais de uma vez
def _fetch_yfinance_with_retry(fetch_fn, retries=3, delay=1, *args, **kwargs):
    for i in range(retries):
        try:
            result = fetch_fn(*args, **kwargs)
            if not isinstance(result, pd.DataFrame) or not result.empty:
                 return result
        except Exception as e:
            if i < retries - 1:
                print(f"Erro de yfinance (Tentativa {i+1}/{retries}): {e}. Tentando novamente em {delay}s...")
                time.sleep(delay)
            else:
                print(f"ERRO CRÍTICO yfinance: Falhou após {retries} tentativas. {e}")
                return None
    return None

def buscar_dados_historicos(ticker, data_inicio_str):
    """ Busca dados históricos usando yfinance e calcula SMAs. """
    def fetch_data():
        dados = yf.download(
            ticker, 
            start=data_inicio_str, 
            end=date.today().strftime("%Y-%m-%d"), 
            progress=False
        )
        if isinstance(dados.columns, pd.MultiIndex):
            dados.columns = dados.columns.droplevel(1)
        return dados
        
    try:
        dados = _fetch_yfinance_with_retry(fetch_data)
        if dados is None or dados.empty:
            return pd.DataFrame()
            
        dados['SMA_20'] = dados['Close'].rolling(window=20).mean()
        dados['SMA_50'] = dados['Close'].rolling(window=50).mean()
        return dados
    except Exception:
        return pd.DataFrame()

def buscar_cotacoes_kpis(tickers_list):
    """ Busca cotacões e a variação diária para uma lista de ativos (Moedas/Criptos/Índices). """
    dados_kpis = {}
    for ticker in tickers_list:
        try:
            ativo = yf.Ticker(ticker)
            info = ativo.info
            
            preco_atual = info.get('regularMarketPrice')
            fechamento_anterior = info.get('previousMarketPrice', info.get('previousClose'))
            
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

def buscar_noticias(query="finanças"):
    """ Busca notícias de mercado usando NewsAPI. """
    if not NEWS_API_KEY:
        return []
        
    dominios_financeiros = "exame.com, infomoney.com.br, valor.globo.com, folha.uol.com.br, cnn.com, bloomberg.com"
    
    url = (f"https://newsapi.org/v2/everything?q={query}&language=pt&pageSize=10"
        f"&sortBy=publishedAt&apiKey={NEWS_API_KEY}&domains={dominios_financeiros}")
    
    try:
        response = requests.get(url, timeout=5)
        response.raise_for_status()
        data = response.json()
        if data.get('status') == 'ok':
            return [{"title": a['title'], "source": a['source']['name'], "url": a['url']} for a in data['articles']]
    
    except requests.exceptions.RequestException as e:
        print(f"Erro ao buscar notícias da NewsAPI: {e}")
        return []
    
    return []

def buscar_noticias_av(ticker, limite=3):
    """ Busca notícias específicas de um ticker no Alpha Vantage. """
    if not ALPHA_VANTAGE_KEY:
        return []
    ticker_av = ticker.replace(".SA", "")
    url = (f"https://www.alphavantage.co/query?function=NEWS_SENTIMENT&"
           f"tickers={ticker_av}&limit={limite}&apikey={ALPHA_VANTAGE_KEY}")
    try:
        response = requests.get(url, timeout=5)
        response.raise_for_status() 
        data = response.json()
        if 'feed' in data and data['feed']:
            noticias_av = []
            for artigo in data['feed']:
                noticias_av.append({"title": artigo['title'], "source": f"AV ({artigo['source']})", "url": artigo['url']})
            return noticias_av
    except requests.exceptions.RequestException as e:
        print(f"Erro ao buscar notícias da Alpha Vantage para {ticker}: {e}")
        return [] 
    
    return []

def buscar_top_performances(tickers_list=None):
    """
    Busca dados atuais de uma lista de tickers (B3 + Internacionais) e classifica em Top Gainers/Losers.
    """
    if tickers_list is None:
        TICKERS_MERCADO = ["PETR4.SA", "VALE3.SA", "ITUB4.SA", "BBDC4.SA", "MGLU3.SA"] 
    else:
        TICKERS_MERCADO = tickers_list

    dados_tabela = []
    
    for ticker in TICKERS_MERCADO:
        try:
            # Tentar 3 vezes para mitigar o erro 401
            def fetch_info():
                return yf.Ticker(ticker).info
            
            info = _fetch_yfinance_with_retry(fetch_info, retries=3, delay=2)
            
            if info is None:
                continue

            preco_atual = info.get('regularMarketPrice')
            fechamento_anterior = info.get('previousMarketPrice', info.get('previousClose'))
            
            variacao = 0
            if preco_atual and fechamento_anterior:
                variacao = ((preco_atual - fechamento_anterior) / fechamento_anterior) * 100
            else:
                variacao = 0

            dados_tabela.append({
                "Ticker": ticker.replace(".SA", ""), 
                "Preço": preco_atual, 
                "Variação (%)": variacao, 
                "Volume": info.get('volume')
            })
        except Exception:
            continue

    df = pd.DataFrame(dados_tabela)
    if df.empty:
        return pd.DataFrame()

    df = df[~df['Ticker'].str.startswith('^')].copy()
    df = df.sort_values(by="Variação (%)", ascending=False)
    
    return df

# Função Auxiliar para o Worker (Cálculo da Carteira)
def _calcular_carteira_async(portfolio_weights, data_inicio):
    tickers = list(portfolio_weights.keys())
    all_data = {t: buscar_dados_historicos(t, data_inicio) for t in tickers}
    df_cdi = buscar_dados_historicos(TICKER_CDI, data_inicio)

    daily_returns = pd.DataFrame({
        t: all_data[t]['Close'].pct_change() * portfolio_weights[t]
        for t in portfolio_weights.keys() if not all_data[t].empty
    })
    
    portfolio_daily_return = daily_returns.sum(axis=1)
    portfolio_cumulative_return = (1 + portfolio_daily_return).cumprod().fillna(1)
    
    if not df_cdi.empty:
        cdi_daily_return = df_cdi['Close'].pct_change()
        cdi_cumulative_return = (1 + cdi_daily_return).cumprod().fillna(1)
        
        df_comparison = pd.DataFrame({
            'Carteira': portfolio_cumulative_return,
            'CDI': cdi_cumulative_return
        }).fillna(method='ffill').dropna()
        
        df_comparison = df_comparison.div(df_comparison.iloc[0]).sub(1).mul(100) 
        return df_comparison
    
    return pd.DataFrame({'Carteira': portfolio_cumulative_return}).div(portfolio_cumulative_return.iloc[0]).sub(1).mul(100).fillna(0)


# Função Auxiliar de Busca (Roda dentro da Thread para a Aba)
def _buscar_dados_para_aba(index_ticker, performance_tickers, data_inicio):
    dados_historicos = buscar_dados_historicos(index_ticker, data_inicio)
    df_performance = buscar_top_performances(performance_tickers)
    return dados_historicos, df_performance

# Função Auxiliar de Busca (Roda dentro da Thread para a Aba)
def _buscar_e_combinar_dados_ativo(ticker, data_inicio):
    """ Agrupa todas as chamadas de API para o Ticker selecionado. """
    dados_historicos = buscar_dados_historicos(ticker, data_inicio)
    noticias_av = buscar_noticias_av(ticker, limite=3)
    noticias_newsapi = buscar_noticias(query=ticker.split('.')[0])
    return dados_historicos, noticias_av, noticias_newsapi


# ==========================================================
# 4. WIDGETS PERSONALIZADOS (MATPLOTLIB)
# ==========================================================

# NOVO WIDGET: MatplotlibCanvas para desenhar o gráfico
class MatplotlibWidget(QWidget):
    """
    Widget nativo para renderização de gráficos Matplotlib dentro do PyQt.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # 1. Configura a figura (área de desenho)
        plt.style.use('dark_background')
        self.fig, self.ax = plt.subplots(facecolor='#1A1A1A') # Cor de fundo da figura
        self.canvas = FigureCanvas(self.fig)
        
        # 2. Configura o layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.addWidget(self.canvas)
        
        # Configurações iniciais do eixo (para ter certeza que o tema escuro se aplica)
        self.ax.tick_params(colors='white')
        self.ax.xaxis.label.set_color('white')
        self.ax.yaxis.label.set_color('white')
        self.ax.title.set_color('white')
        self.ax.set_facecolor('#1A1A1A') # Cor do painel do gráfico
        self.ax.spines['bottom'].set_color('#333333')
        self.ax.spines['left'].set_color('#333333')
        self.ax.spines['top'].set_color('#1A1A1A')
        self.ax.spines['right'].set_color('#1A1A1A')
        
    def plot_dados(self, df, ticker):
        """ Desenha o gráfico de Fechamento e Médias Móveis. """
        
        self.ax.clear() # Limpa o gráfico anterior
        
        if df.empty or 'Close' not in df.columns:
            self.ax.text(0.5, 0.5, "Dados não disponíveis para plotagem.", 
                         color='red', fontsize=12, ha='center', transform=self.ax.transAxes)
            self.canvas.draw()
            return
            
        # 1. Plota o preço de fechamento
        self.ax.plot(df.index, df['Close'], label='Fechamento', color='white', linewidth=1.5)
        
        # 2. Plota as Médias Móveis
        if 'SMA_20' in df.columns:
            self.ax.plot(df.index, df['SMA_20'], label='Média Móvel 20', color='yellow', linestyle='--')
        if 'SMA_50' in df.columns:
            self.ax.plot(df.index, df['SMA_50'], label='Média Móvel 50', color='cyan')
            
        # 3. Formatação Final
        self.ax.set_title(f"Preço de Fechamento e Médias Móveis de {ticker}", color='white')
        
        # CORREÇÃO AQUI (AXIS LABELS)
        self.ax.set_xlabel("Data") # Usar self.ax
        self.ax.set_ylabel("Preço") # Usar self.ax

        self.ax.legend(loc='upper left', frameon=False, fontsize=8)
        self.ax.grid(True, linestyle=':', alpha=0.5, color='#333333')
        
        # Formatação do eixo X (Datas)
        self.ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))
        self.fig.autofmt_xdate(rotation=45)
        
        # Garante que as cores personalizadas do Matplotlib sejam aplicadas
        self.ax.tick_params(axis='x', colors='white')
        self.ax.tick_params(axis='y', colors='white')
        
        # Desenha o novo gráfico
        self.canvas.draw()


class GlobalTickerTape(QWidget):
    """ Widget que simula um carrossel de notícias da bolsa (Ticker Tape). """
    def __init__(self, tickers_list):
        super().__init__()
        self.tickers_list = tickers_list
        self.scroll_offset = 0
        self.speed = 1.5 
        
        self.scroll_content_widget = QWidget()
        self.scroll_layout = QHBoxLayout(self.scroll_content_widget)
        self.scroll_layout.setContentsMargins(0, 0, 0, 0)
        self.scroll_layout.setSpacing(50) 
        
        self.scroll_area = QScrollArea(self)
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setWidget(self.scroll_content_widget)
        
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll_area.setStyleSheet("QScrollArea { border: none; background-color: black; }")
        
        self.main_layout = QHBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.addWidget(self.scroll_area)
        
        self.setStyleSheet("background-color: #000000; border-top: 1px solid #333; border-bottom: 1px solid #333;")
        self.setFixedHeight(30)
        
        self.scroll_timer = QTimer(self)
        self.scroll_timer.timeout.connect(self.scroll_content)
        self.scroll_timer.start(30) 

        self.data_timer = QTimer(self)
        self.data_timer.timeout.connect(self.update_data)
        self.data_timer.start(60000) 
        
        self.update_data()
        
    def update_data(self):
        """ Inicia a busca de dados de Ticker Tape em uma thread. """
        app = QApplication.instance()
        if hasattr(app, 'threadpool'):
            worker = Worker(buscar_cotacoes_kpis, self.tickers_list)
            worker.signals.result.connect(self.processar_dados_tape)
            app.threadpool.start(worker)


    def processar_dados_tape(self, dados):
        """ Callback para o Worker: Atualiza os rótulos do Ticker Tape. """
        while self.scroll_layout.count():
            item = self.scroll_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
                
        itens_para_rolar = []

        for ticker in self.tickers_list:
            data = dados.get(ticker, {"Nome": ticker, "Preco": None, "Variacao": None})
            
            if data['Preco'] is None or data['Variacao'] is None:
                continue

            variacao = data['Variacao']
            
            if variacao > 0.05:
                cor = "#76DD76"
                seta = "▲"
            elif variacao < -0.05:
                cor = "#FF6B6B"
                seta = "▼"
            else:
                cor = "#AAAAAA"
                seta = "—"
            
            if "BRL" in ticker:
                nome_display = "DÓLAR"
            elif ticker == "^BVSP":
                nome_display = "IBOVESPA"
            elif ticker == "^N225":
                nome_display = "NIKKEI"
            elif ticker == "000001.SS":
                nome_display = "SHANGHAI"
            elif ticker == "^MERV":
                nome_display = "MERVAL"
            elif ticker == "CL=F":
                nome_display = "CRUDE OIL"
            elif ticker == "GC=F":
                nome_display = "OURO"
            elif ticker == "SI=F":
                nome_display = "PRATA"
            elif ticker == "KC=F":
                nome_display = "CAFÉ"
            elif ticker == "NG=F":
                nome_display = "GÁS NAT."
            else:
                nome_display = data['Nome'].upper()
                
            frase = f"{nome_display} ({variacao:+.2f}%) {seta}"
            
            label = QLabel(frase)
            label.setStyleSheet(f"color: {cor}; font-weight: bold; font-size: 12px;")
            label.setAlignment(Qt.AlignCenter)
            label.setFixedWidth(250) 
            
            itens_para_rolar.append(label)
        
        for _ in range(2): 
            for item in itens_para_rolar:
                cloned_label = QLabel(item.text())
                cloned_label.setStyleSheet(item.styleSheet())
                cloned_label.setFixedWidth(item.width()) 
                self.scroll_layout.addWidget(cloned_label)

        self.scroll_content_widget.adjustSize()
        self.scroll_offset = 0
        self.scroll_area.horizontalScrollBar().setValue(0)


    def scroll_content(self):
        """ Move o conteúdo da barra horizontalmente. """
        total_width = self.scroll_content_widget.width()
        restart_point = total_width / 2
        
        if total_width == 0:
            return
            
        self.scroll_offset -= self.speed
        
        if self.scroll_offset < -restart_point:
            self.scroll_offset += restart_point 
        
        self.scroll_area.horizontalScrollBar().setValue(int(-self.scroll_offset))


class KPIMetric(QFrame):
    """ Widget que exibe preço e variação. """
    def __init__(self, titulo):
        super().__init__()
        
        self.setFrameShape(QFrame.StyledPanel)
        self.setFrameShadow(QFrame.Raised)
        self.setStyleSheet("background-color: #282828; border: 1px solid #404040; border-radius: 6px; padding: 5px;")
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8) 

        self.titulo_label = QLabel(titulo)
        self.titulo_label.setFont(QFont("Consolas", 10))
        self.titulo_label.setStyleSheet("color: #AAAAAA;")
        layout.addWidget(self.titulo_label)

        self.valor_label = QLabel("N/A")
        self.valor_label.setFont(QFont("Consolas", 16, QFont.Bold)) 
        layout.addWidget(self.valor_label)

        self.delta_label = QLabel("")
        self.delta_label.setFont(QFont("Consolas", 11)) 
        layout.addWidget(self.delta_label)
        
        layout.addStretch(1)

    def set_data(self, preco, variacao):
        """ Atualiza os dados do widget. """
        
        if preco is None:
            self.valor_label.setText("Erro")
            self.delta_label.setText("")
            self.valor_label.setStyleSheet("color: #FF6B6B;")
            return
            
        # Formatação
        if preco > 1000:
            preco_formatado = f"{preco:,.0f}".replace(",", "X").replace(".", ",").replace("X", ".")
        else:
            preco_formatado = f"{preco:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


        variacao_formatada = f"{variacao:+.2f} %".replace(",", "X").replace(".", ",").replace("X", ".")
        
        cor = "#76DD76" if variacao >= 0 else "#FF6B6B" 
        
        self.valor_label.setText(preco_formatado)
        self.valor_label.setStyleSheet("color: #E6E6E6;")
        self.delta_label.setText(variacao_formatada)
        self.delta_label.setStyleSheet(f"color: {cor}; font-weight: bold;")


class NewsPanel(QWidget):
    """ Painel que exibe manchetes de notícias com links. """
    def __init__(self, titulo="Manchetes de Mercado"):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10) 
        
        titulo_label = QLabel(titulo)
        titulo_label.setFont(QFont("Consolas", 13, QFont.Bold)) 
        titulo_label.setStyleSheet("color: #E6E6E6;") 
        layout.addWidget(titulo_label)
        
        self.news_list_widget = QWidget()
        self.news_layout = QVBoxLayout(self.news_list_widget)
        self.news_layout.setSpacing(8)
        self.news_layout.setContentsMargins(0, 10, 0, 5) 
        
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setWidget(self.news_list_widget)
        scroll_area.setStyleSheet("border: none;") 
        layout.addWidget(scroll_area)
        
    def update_news(self, noticias):
        """ Limpa o painel e adiciona novas notícias. """
        
        while self.news_layout.count():
            item = self.news_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        
        if not noticias:
            info_label = QLabel("Não foi possível carregar notícias. Verifique as chaves de API.")
            info_label.setStyleSheet("color: #FF6B6B;") 
            self.news_layout.addWidget(info_label)
            self.news_layout.addStretch(1)
            return
            
        for artigo in noticias:
            html_content = f"""
            <a href="{artigo['url']}" style="color: #E6E6E6; text-decoration: none;">
                <span style="font-weight: bold; font-size: 10pt;">{artigo['title']}</span>
            </a>
            <br><span style="color: #AAAAAA; font-size: 8pt;">{artigo['source']}</span>
            """
            news_label = QLabel(html_content)
            news_label.setTextFormat(Qt.RichText)
            news_label.setOpenExternalLinks(True) 
            news_label.setWordWrap(True)
            
            self.news_layout.addWidget(news_label)
            
        self.news_layout.addStretch(1)

class PerformanceTable(QWidget):
    """ Widget que exibe a tabela completa de Performance (Gainers e Losers). """
    def __init__(self, titulo="Performance de Mercado - Maiores Altas/Baixas"):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10) 
        
        titulo_label = QLabel(titulo)
        titulo_label.setFont(QFont("Consolas", 14, QFont.Bold))
        titulo_label.setStyleSheet("color: #E6E6E6;") 
        layout.addWidget(titulo_label)
        
        self.table_widget = QTableWidget()
        self.table_widget.setColumnCount(4)
        self.table_widget.setHorizontalHeaderLabels(["Ticker", "Preço", "Variação (%)", "Volume"])
        
        self.table_widget.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table_widget.verticalHeader().setVisible(False) 
        self.table_widget.setSelectionBehavior(QTableWidget.SelectRows) 
        
        self.table_widget.setStyleSheet("""
            QTableWidget { 
                gridline-color: #333333; 
                background-color: #1A1A1A; 
                color: #E6E6E6; 
                border: 1px solid #333333; 
                border-radius: 6px;
                selection-background-color: #2A82DA; 
                selection-color: black;
            }
            QHeaderView::section { 
                background-color: #282828; 
                color: #AAAAAA; 
                padding: 8px; 
                border-bottom: 1px solid #333333;
                font-weight: bold;
            }
            QTableWidget::item {
                padding: 6px; 
            }
            QTableWidget::item:selected {
                color: black; 
            }
        """)
        
        layout.addWidget(self.table_widget)
        
    def update_table(self, df):
        """ Preenche a tabela com os dados do DataFrame, usando cor da LETRA para Variação. """
        self.table_widget.setRowCount(0)
        
        if df.empty:
            return

        self.table_widget.setRowCount(len(df))
        
        for i, row in df.iterrows():
            ticker_item = QTableWidgetItem(row['Ticker'])
            preco_str = f"{row['Preço']:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".") if row['Preço'] is not None else "N/A"
            preco_item = QTableWidgetItem(preco_str)
            
            variacao_str = f"{row['Variação (%)']:+.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
            variacao_item = QTableWidgetItem(variacao_str)
            
            volume_str = f"{row['Volume']:.0f}" if row['Volume'] is not None else "0"
            volume_item = QTableWidgetItem(volume_str)
            
            # --- LÓGICA DE COR DA FONTE (FOREGROUND) ---
            if row['Variação (%)'] >= 0:
                variacao_item.setForeground(QBrush(QColor(118, 221, 118))) 
            else:
                variacao_item.setForeground(QBrush(QColor(255, 107, 107))) 
                
            self.table_widget.setItem(i, 0, ticker_item)
            self.table_widget.setItem(i, 1, preco_item)
            self.table_widget.setItem(i, 2, variacao_item)
            self.table_widget.setItem(i, 3, volume_item)
            
            # Centraliza o texto nas células
            for col in range(4):
                item = self.table_widget.item(i, col)
                if item is not None:
                    item.setTextAlignment(Qt.AlignCenter)
            
            # CORREÇÃO DO BUG DO LISTRADO: Aplica a cor de fundo cinza/cinza escuro
            if i % 2 == 0:
                background_color = QColor(30, 30, 30) # Cor mais escura
            else:
                background_color = QColor(20, 20, 20) # Cor mais clara
                
            for col in range(self.table_widget.columnCount()):
                item = self.table_widget.item(i, col)
                if item is not None:
                    item.setBackground(QBrush(background_color)) 

class RawDataTable(QWidget):
    """ Widget que exibe os dados brutos históricos de um ticker (OHLCV). """
    def __init__(self, titulo="Dados Históricos Brutos"):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)

        titulo_label = QLabel(titulo)
        titulo_label.setFont(QFont("Consolas", 14, QFont.Bold))
        titulo_label.setStyleSheet("color: #E6E6E6;")
        layout.addWidget(titulo_label)
        
        self.table_widget = QTableWidget()
        self.table_widget.setColumnCount(6)
        self.table_widget.setHorizontalHeaderLabels(["Data", "Fechamento", "Máx. Dia", "Mín. Dia", "Abertura", "Volume"])
        
        self.table_widget.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table_widget.verticalHeader().setVisible(False)
        self.table_widget.setSelectionBehavior(QTableWidget.SelectRows)
        
        self.table_widget.setStyleSheet("""
            QTableWidget { 
                gridline-color: #333333; 
                background-color: #1A1A1A; 
                color: #E6E6E6; 
                border: 1px solid #333333; 
                border-radius: 6px;
                selection-background-color: #2A82DA; 
                selection-color: black;
            }
            QHeaderView::section { 
                background-color: #282828; 
                color: #AAAAAA; 
                padding: 8px; 
                border-bottom: 1px solid #333333;
                font-weight: bold;
            }
            QTableWidget::item {
                padding: 6px; 
            }
            QTableWidget::item:selected {
                color: black; 
            }
        """)
        layout.addWidget(self.table_widget)

    def update_table(self, df_raw):
        """ Preenche a tabela com os dados brutos (OHLCV) do DataFrame. """
        self.table_widget.setRowCount(0)
        
        if df_raw.empty:
            return

        # Exibe apenas as últimas 150 linhas para evitar sobrecarga visual
        df_display = df_raw[['Close', 'High', 'Low', 'Open', 'Volume']].tail(150).copy()
        
        self.table_widget.setRowCount(len(df_display))
        
        for i, (index, row) in enumerate(df_display.iterrows()):
            # Coluna 1: Data
            data_str = index.strftime('%Y-%m-%d')
            self.table_widget.setItem(i, 0, QTableWidgetItem(data_str))
            
            # Colunas 2 a 5: Valores (Fechamento, Máx, Mín, Abertura)
            colunas_valores = ['Close', 'High', 'Low', 'Open']
            for col_idx, col_name in enumerate(colunas_valores, start=1):
                valor_str = f"{row[col_name]:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
                item = QTableWidgetItem(valor_str)
                item.setTextAlignment(Qt.AlignCenter)
                self.table_widget.setItem(i, col_idx, item)

            # Coluna 6: Volume
            volume_str = f"{row['Volume']:,.0f}".replace(",", "X").replace(".", ",").replace("X", ".")
            volume_item = QTableWidgetItem(volume_str)
            volume_item.setTextAlignment(Qt.AlignCenter)
            self.table_widget.setItem(i, 5, volume_item)
            
            # Aplica a cor de fundo cinza/cinza escuro
            if i % 2 == 0:
                background_color = QColor(30, 30, 30) # Cor mais escura
            else:
                background_color = QColor(20, 20, 20) # Cor mais clara
                
            for col in range(self.table_widget.columnCount()):
                item = self.table_widget.item(i, col)
                if item is not None:
                    item.setBackground(QBrush(background_color))

class AnalysisTabContent(QWidget):
    """ Widget reutilizável para uma Aba de Análise (Gráfico do Índice + Tabela de Performance). """
    def __init__(self, index_ticker, performance_tickers, index_name):
        super().__init__()
        self.index_ticker = index_ticker
        self.performance_tickers = performance_tickers
        self.index_name = index_name
        self.data_inicio = DATA_INICIO_PADRAO
        
        layout = QVBoxLayout(self)
        
        # ATENÇÃO: Substituído PlotlyWebView por MatplotlibWidget
        self.index_graph = MatplotlibWidget() 
        self.performance_table = PerformanceTable(titulo=f"Performance dos Ativos")
        
        graph_container = QWidget()
        graph_container.setLayout(QVBoxLayout())
        graph_container.layout().setContentsMargins(0, 0, 0, 0)
        graph_container.setStyleSheet("border: 1px solid #333333; border-radius: 6px;")
        graph_container.layout().addWidget(self.index_graph)

        layout.addWidget(QLabel(f"Gráfico Histórico: {index_name} ({index_ticker})"))
        layout.addWidget(graph_container, 1)
        
        layout.addWidget(QLabel(f"Tabela de Desempenho Diário"))
        layout.addWidget(self.performance_table, 1)
        
        # Chamada Assíncrona para iniciar
        self.load_data() 

    def load_data(self):
        """ Inicia a busca e plota os dados da aba de forma assíncrona. """
        app = QApplication.instance()
        if hasattr(app, 'threadpool'):
            worker = Worker(_buscar_dados_para_aba, self.index_ticker, self.performance_tickers, self.data_inicio)
            worker.signals.result.connect(self.processar_dados_aba)
            app.threadpool.start(worker)

    def processar_dados_aba(self, results):
        """ Callback para o Worker: Atualiza os widgets da aba. """
        dados_historicos, df_performance = results
        
        # Atualiza o Gráfico
        self.index_graph.plot_dados(dados_historicos, self.index_name)
        
        # Atualiza a Tabela
        self.performance_table.update_table(df_performance)

class PortfolioInputWidget(QWidget):
    """ Widget para selecionar ativos e quantidades da carteira. """
    def __init__(self):
        super().__init__()
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(10, 10, 10, 10)
        self.layout.setSpacing(10)
        
        titulo = QLabel("Selecione Ativos da Carteira (Ticker, Quantidade)")
        titulo.setFont(QFont("Consolas", 12, QFont.Bold))
        self.layout.addWidget(titulo)
        
        self.input_fields = []
        
        # Tickers de exemplo para input (B3)
        self.default_tickers = [("PETR4.SA", 6), ("VALE3.SA", 2), ("ITUB4.SA", 1), ("BBDC4.SA", 1)]
        
        self.grid_input = QGridLayout()
        self.layout.addLayout(self.grid_input)
        
        # Cabeçalhos
        self.grid_input.addWidget(QLabel("Ticker"), 0, 0)
        self.grid_input.addWidget(QLabel("Quantidade"), 0, 1)

        # Cria campos iniciais
        for i, (ticker, quantity) in enumerate(self.default_tickers):
            self.add_input_row(i + 1, ticker, quantity)
            
        # Botão Adicionar Linha 
        btn_add = QPushButton("Adicionar Ativo")
        btn_add.setStyleSheet("background-color: #007bff; color: white;")
        btn_add.clicked.connect(lambda: self.add_input_row(len(self.input_fields) + 1, "", 0))
        self.layout.addWidget(btn_add)
        
        self.layout.addStretch(1)

    def add_input_row(self, row_idx, ticker, quantity):
        """ Adiciona uma nova linha de input. """
        ticker_input = QLineEdit(ticker)
        quantity_input = QLineEdit(str(quantity))
        
        quantity_input.setValidator(QIntValidator(0, 1000000)) 
        
        self.grid_input.addWidget(ticker_input, row_idx, 0)
        self.grid_input.addWidget(quantity_input, row_idx, 1)
        self.input_fields.append((ticker_input, quantity_input))

    def get_portfolio(self):
        """ Retorna o portfólio (ticker: valor ponderado em R$). """
        quantities = {}
        for ticker_input, quantity_input in self.input_fields:
            ticker = ticker_input.text().upper().strip()
            try:
                quantity = int(quantity_input.text())
                if ticker and quantity > 0:
                    quantities[ticker] = quantity
            except ValueError:
                continue
        
        if not quantities:
            return {}

        total_value = 0
        current_prices = {}
        
        # NOTE: Esta busca de preços é síncrona, mas roda rápido o suficiente para a UI
        for ticker in quantities.keys():
            try:
                ativo = yf.Ticker(ticker)
                price = ativo.info.get('regularMarketPrice')
                if price is not None:
                    current_prices[ticker] = price
                    total_value += price * quantities[ticker]
            except Exception:
                continue

        if total_value == 0:
            return {}

        portfolio = {}
        for ticker, quantity in quantities.items():
            if ticker in current_prices:
                asset_value = current_prices[ticker] * quantity
                portfolio[ticker] = asset_value / total_value 
                
        return portfolio


class PortfolioAnalysisTab(QWidget):
    """ Aba dedicada à análise da carteira. """
    def __init__(self):
        super().__init__()
        self.layout = QHBoxLayout(self)
        
        self.input_widget = PortfolioInputWidget()
        
        self.result_container = QWidget()
        self.result_layout = QVBoxLayout(self.result_container)
        
        self.result_layout.addWidget(QLabel("Gráfico de Performance da Carteira vs. CDI"))
        # ATENÇÃO: Substituído PlotlyWebView por MatplotlibWidget
        self.graph_view = MatplotlibWidget() 
        self.result_layout.addWidget(self.graph_view, 1)
        
        self.btn_run = QPushButton("Atualizar gráfico")
        self.btn_run.setStyleSheet("background-color: #7b68ee; color: white; font-size: 14px; padding: 10px;")
        self.btn_run.clicked.connect(self.run_analysis)
        self.result_layout.addWidget(self.btn_run)
        
        self.layout.addWidget(self.input_widget, 1)
        self.layout.addWidget(self.result_container, 2)
        
        self.run_analysis() 

    def run_analysis(self):
        """ Inicia a execução do cálculo e plotagem em uma thread. """
        portfolio_weights = self.input_widget.get_portfolio() 
        
        if not portfolio_weights:
            # Mantemos o Matplotlib limpo em caso de erro
            self.graph_view.ax.clear()
            self.graph_view.ax.text(0.5, 0.5, "ERRO: Insira ativos válidos.", 
                                    color='red', fontsize=12, ha='center', transform=self.graph_view.ax.transAxes)
            self.graph_view.canvas.draw()
            return
        
        # Mensagem de carregamento (Matplotlib não permite HTML, usamos o console)
        print("Calculando portfólio... Aguarde.")

        app = QApplication.instance()
        if hasattr(app, 'threadpool'):
            worker = Worker(_calcular_carteira_async, portfolio_weights, DATA_INICIO_PADRAO)
            worker.signals.result.connect(self.processar_analise)
            app.threadpool.start(worker)

    def processar_analise(self, df_comparison):
        """ Callback para o Worker: Plota o resultado da análise da carteira. """
        self.plot_comparison(df_comparison)
        
    def plot_comparison(self, df_comparison):
        """ Plota o gráfico de comparação de performance usando Matplotlib. """
        
        self.graph_view.ax.clear()
        
        if df_comparison.empty:
            self.graph_view.ax.text(0.5, 0.5, "Dados insuficientes para plotagem.", 
                                    color='red', fontsize=12, ha='center', transform=self.graph_view.ax.transAxes)
            self.graph_view.canvas.draw()
            return

        # Plota Carteira
        self.graph_view.ax.plot(df_comparison.index, df_comparison['Carteira'], 
                                label='Minha Carteira', color='#FFA500', linewidth=2)

        # Plota CDI
        if 'CDI' in df_comparison.columns:
            self.graph_view.ax.plot(df_comparison.index, df_comparison['CDI'], 
                                    label='CDI', color='white', linestyle='--', linewidth=1)
            
        # Formatação
        self.graph_view.ax.set_title("Retorno Acumulado: Carteira vs. CDI (%)", color='white') # Já está certo (usando .ax.set_title)
        
        # CORREÇÃO AQUI (AXIS LABELS)
        self.graph_view.ax.set_xlabel("Data") # Usar .ax.set_xlabel
        self.graph_view.ax.set_ylabel("Retorno Acumulado (%)") # Usar .ax.set_ylabel

        self.graph_view.ax.legend(loc='upper left', frameon=False, fontsize=8, labelcolor='white')
        self.graph_view.ax.grid(True, linestyle=':', alpha=0.3, color='#333333')
        
        # Formatação do eixo X (Datas)
        self.graph_view.ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))
        self.graph_view.fig.autofmt_xdate(rotation=45)
        
        self.graph_view.canvas.draw()


# ==========================================================
# 5. CLASSE DA JANELA PRINCIPAL (TerminalFinanceiroApp)
# ==========================================================
class TerminalFinanceiroApp(QMainWindow):
    def __init__(self):
        super().__init__()
        
        self.data_inicio = DATA_INICIO_PADRAO
        
        # 0. Inicializar o Pool de Threads
        self.threadpool = QThreadPool()
        print(f"Multithreading com {self.threadpool.maxThreadCount()} threads disponível.")
        QApplication.instance().threadpool = self.threadpool # Adiciona o pool ao app instance
        
        self.input_ticker = QLineEdit(ACAO_PADRAO)
        self.btn_buscar = QPushButton("Buscar Ativo")
        
        self.setWindowTitle("Terminal F(ree)nance - Desktop")
        self.setGeometry(100, 100, 1400, 850) 
        
        self.configurar_tema_escuro()
        
        widget_central = QWidget()
        self.setCentralWidget(widget_central)
        layout_principal = QVBoxLayout(widget_central)
        
        self.construir_interface(layout_principal)
        
        self.btn_buscar.clicked.connect(self.atualizar_dados_ativo)
        
        self.timer_kpis = QTimer(self)
        self.timer_kpis.timeout.connect(self.atualizar_dados_periodicamente)
        self.timer_kpis.start(60000) 
        
        # 4. Chamadas iniciais (Assíncronas)
        self.atualizar_dados_kpis()
        self.atualizar_dados_top_movers_dashboard()
        self.plotar_grafico_b3()
        self.atualizar_dados_ativo() 
        self.atualizar_dados_performance_completa()


    def configurar_tema_escuro(self):
        """ Aplica um tema escuro consistente e define fontes. """
        app = QApplication.instance()
        palette = QPalette()
        
        BACKGROUND_COLOR_MAIN = QColor(20, 20, 20) 
        BACKGROUND_COLOR_PANEL = QColor(30, 30, 30) 
        TEXT_COLOR_PRIMARY = QColor(230, 230, 230) 
        HIGHLIGHT_COLOR = QColor(42, 130, 218)
        
        palette.setColor(QPalette.Window, BACKGROUND_COLOR_MAIN)
        palette.setColor(QPalette.WindowText, TEXT_COLOR_PRIMARY) 
        palette.setColor(QPalette.Base, BACKGROUND_COLOR_PANEL) 
        palette.setColor(QPalette.Text, TEXT_COLOR_PRIMARY)
        palette.setColor(QPalette.Button, QColor(50, 50, 50)) 
        palette.setColor(QPalette.ButtonText, TEXT_COLOR_PRIMARY)
        palette.setColor(QPalette.Highlight, HIGHLIGHT_COLOR)
        palette.setColor(QPalette.HighlightedText, QColor(0, 0, 0)) 
        
        app.setPalette(palette)
        app.setFont(QFont("Consolas", 10)) 
        
        app.setStyleSheet("""
            QLineEdit {
                background-color: #282828;
                color: #E6E6E6;
                border: 1px solid #404040;
                border-radius: 4px;
                padding: 5px;
            }
            QPushButton {
                background-color: #404040;
                color: #E6E6E6;
                border: none;
                border-radius: 4px;
                padding: 6px 12px;
            }
            QPushButton:hover {
                background-color: #555555;
            }
            QTabWidget::pane {
                border: 1px solid #333333;
                background-color: #1A1A1A; 
            }
            QTabBar::tab {
                background: #282828;
                color: #AAAAAA;
                padding: 8px 15px;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
                margin-right: 2px;
            }
            QTabBar::tab:selected {
                background: #1A1A1A;
                color: #E6E6E6;
                border-bottom: 2px solid #d3bcf6; 
            }
            QTabBar::tab:hover {
                background: #353535;
            }
        """)
        
    def construir_interface(self, layout_principal):
        """ Cria e adiciona todos os componentes no layout com 4 abas. """
        self.tab_widget = QTabWidget()
        self.tab_widget.setFont(QFont("Consolas", 10, QFont.Bold))
        
        tab_dashboard = QWidget()
        layout_dashboard_principal = QVBoxLayout(tab_dashboard)
        layout_dashboard_principal.setContentsMargins(0, 0, 0, 0)
        layout_dashboard_principal.setSpacing(0)
        
        self.ticker_tape = GlobalTickerTape(TICKERS_TAPE)
        layout_dashboard_principal.addWidget(self.ticker_tape)
        
        grid_container = QWidget()
        self.grid_layout = QGridLayout(grid_container)
        self.grid_layout.setContentsMargins(10, 10, 10, 10)
        self.grid_layout.setSpacing(10)
        
        q1_widget = QWidget()
        layout_q1 = QVBoxLayout(q1_widget)
        titulo_kpi = QLabel("Visão Rápida: Índices, Moedas e Criptos")
        titulo_kpi.setFont(QFont("Consolas", 12, QFont.Bold))
        layout_q1.addWidget(titulo_kpi)
        
        self.kpi_grid_layout = QGridLayout()
        layout_q1.addLayout(self.kpi_grid_layout)

        self.kpi_widgets = {}
        for i, ticker in enumerate(TICKERS_KPIS):
            display_ticker = ticker.replace("=X", "").replace("-USD", "").replace("BNO", "BRENT")
            kpi_widget = KPIMetric(display_ticker)
            self.kpi_widgets[ticker] = kpi_widget
            self.kpi_grid_layout.addWidget(kpi_widget, i // 3, i % 3) 
            
        layout_q1.addStretch(1)
        
        self.news_panel = NewsPanel("Manchetes de Mercado")
        
        self.table_top_movers_dashboard = PerformanceTable(titulo="Performance do Dia")

        ibovespa_container = QWidget()
        ibovespa_container.setLayout(QVBoxLayout())
        ibovespa_container.layout().setContentsMargins(0, 0, 0, 0)
        ibovespa_container.setStyleSheet("border: 1px solid #333333; border-radius: 6px;")
        
        # ATENÇÃO: SUBSTITUIÇÃO AQUI
        self.grafico_ibov_canvas = MatplotlibWidget() 
        ibovespa_container.layout().addWidget(self.grafico_ibov_canvas)


        self.grid_layout.addWidget(q1_widget, 0, 0, 1, 1) 
        self.grid_layout.addWidget(self.news_panel, 0, 1, 1, 1) 
        self.grid_layout.addWidget(self.table_top_movers_dashboard, 1, 0, 1, 1) 
        self.grid_layout.addWidget(ibovespa_container, 1, 1, 1, 1) 
        
        layout_dashboard_principal.addWidget(grid_container, 1)

        tab_detalhes = QWidget()
        layout_detalhes = QVBoxLayout(tab_detalhes)
        
        layout_busca_detalhes = QHBoxLayout()
        layout_busca_detalhes.addWidget(QLabel("Ticker:"))
        layout_busca_detalhes.addWidget(self.input_ticker) 
        layout_busca_detalhes.addWidget(self.btn_buscar)
        
        layout_busca_detalhes.addStretch(1)
        layout_detalhes.addLayout(layout_busca_detalhes)
        
        self.commodity_tape = GlobalTickerTape(TICKERS_COMMODITIES)
        layout_detalhes.addWidget(self.commodity_tape) 

        ativo_graph_container = QWidget()
        ativo_graph_container.setLayout(QVBoxLayout())
        ativo_graph_container.layout().setContentsMargins(0, 0, 0, 0)
        ativo_graph_container.setStyleSheet("border: 1px solid #333333; border-radius: 6px;")
        
        # ATENÇÃO: SUBSTITUIÇÃO AQUI
        self.grafico_ativo_canvas = MatplotlibWidget() 
        ativo_graph_container.layout().addWidget(self.grafico_ativo_canvas)

        layout_detalhes.addWidget(QLabel("Gráfico Histórico do Ativo Selecionado"))
        layout_detalhes.addWidget(ativo_graph_container, 1)

        self.raw_data_table = RawDataTable(titulo="Dados Históricos Brutos do Ativo")
        layout_detalhes.addWidget(QLabel("Dados Detalhados (OHLCV)"))
        layout_detalhes.addWidget(self.raw_data_table, 1)

        self.tab_sp500 = AnalysisTabContent(
            index_ticker="^GSPC", 
            performance_tickers=TICKERS_S_AND_P, 
            index_name="S&P 500 Index"
        )
        
        self.tab_crypto = AnalysisTabContent(
            index_ticker="BTC-USD", 
            performance_tickers=TICKERS_CRYPTO, 
            index_name="Bitcoin (BTC)"
        )
        
        self.tab_carteira = PortfolioAnalysisTab()
        
        self.tab_widget.addTab(tab_dashboard, "1. Dashboard (Visão Geral)")
        self.tab_widget.addTab(tab_detalhes, "2. Detalhes do Ativo") 
        self.tab_widget.addTab(self.tab_sp500, "3. S&P | 500") 
        self.tab_widget.addTab(self.tab_crypto, "4. Cripto") 
        self.tab_widget.addTab(self.tab_carteira, "5. Minha Carteira") 
        
        layout_principal.addWidget(self.tab_widget, 1)
        
    def execute_async_task(self, fn, callback_result, callback_finished=None, *args, **kwargs):
        """ Executa uma função em uma thread separada e conecta os sinais. """
        worker = Worker(fn, *args, **kwargs)
        
        worker.signals.result.connect(callback_result)
        if callback_finished:
            worker.signals.finished.connect(callback_finished)
            
        self.threadpool.start(worker)

    def atualizar_dados_periodicamente(self):
        """ Função disparada pelo QTimer para atualizar dados que mudam rapidamente. (Assíncrono) """
        self.atualizar_dados_kpis() 
        self.atualizar_dados_top_movers_dashboard()
        self.ticker_tape.update_data() 
        self.commodity_tape.update_data()
        print("Atualização periódica dos KPIs e Carrossel concluída.")
        
    def plotar_grafico_b3(self):
        """ Inicia a busca do gráfico do Ibovespa em uma thread. """
        self.execute_async_task(
            fn=buscar_dados_historicos, 
            callback_result=self.processar_grafico_b3, 
            ticker=TICKER_IBOVESPA,
            data_inicio=self.data_inicio
        )
    
    def processar_grafico_b3(self, dados_ibov):
        """ Callback para o Worker: Plota o gráfico do Ibovespa. """
        self.grafico_ibov_canvas.plot_dados(dados_ibov, "IBOVESPA")

    def atualizar_dados_kpis(self):
        """ Inicia a busca de KPIs em uma thread. """
        self.execute_async_task(
            fn=buscar_cotacoes_kpis, 
            callback_result=self.processar_kpis, 
            tickers_list=TICKERS_KPIS
        )
        
    def processar_kpis(self, kpi_data):
        """ Callback que atualiza a interface com os dados de KPIs. """
        for ticker_kpi, data in kpi_data.items():
            if ticker_kpi in self.kpi_widgets:
                self.kpi_widgets[ticker_kpi].set_data(data['Preco'], data['Variacao'])
        print("Atualização dos KPIs na UI concluída.")

    def atualizar_dados_top_movers_dashboard(self):
        """ Inicia a busca de Top Movers em uma thread. """
        self.execute_async_task(
            fn=buscar_top_performances, 
            callback_result=self.processar_top_movers, 
            tickers_list=["PETR4.SA", "VALE3.SA", "ITUB4.SA", "BBDC4.SA", "MGLU3.SA"]
        )

    def processar_top_movers(self, df_performance):
        """ Callback que atualiza a tabela de Top Movers. """
        self.table_top_movers_dashboard.update_table(df_performance)
        print("Atualização da Tabela Top Movers concluída.")

    def atualizar_dados_performance_completa(self):
        """ Dispara o carregamento das abas de análise (3, 4 e 5) assíncronamente. """
        print("Atualizando Tabela de Performance Completa...")
        
        # S&P 500
        self.execute_async_task(
            fn=_buscar_dados_para_aba, 
            callback_result=self.tab_sp500.processar_dados_aba, 
            index_ticker=self.tab_sp500.index_ticker, 
            performance_tickers=self.tab_sp500.performance_tickers,
            data_inicio=self.tab_sp500.data_inicio
        )
        
        # Cripto
        self.execute_async_task(
            fn=_buscar_dados_para_aba, 
            callback_result=self.tab_crypto.processar_dados_aba, 
            index_ticker=self.tab_crypto.index_ticker, 
            performance_tickers=self.tab_crypto.performance_tickers,
            data_inicio=self.tab_crypto.data_inicio
        )

        # Carteira (Dispara a análise da carteira inicial)
        if hasattr(self, 'tab_carteira'):
            self.tab_carteira.run_analysis()


    def atualizar_dados_ativo(self):
        """ Função principal para buscar, calcular e plotar o Ticker selecionado assíncronamente. """
        ticker = self.input_ticker.text().upper()
        
        # Não precisa mais de HTML de carregamento no Matplotlib, apenas do console.
        print(f"Buscando dados para o ativo {ticker}...")

        self.execute_async_task(
            fn=_buscar_e_combinar_dados_ativo,
            callback_result=self.processar_dados_ativo, 
            ticker=ticker,
            data_inicio=self.data_inicio
        )
        
    def processar_dados_ativo(self, results):
        """ Callback que atualiza UI após a busca de dados do Ticker. """
        dados_historicos, noticias_av, noticias_newsapi = results
        ticker = self.input_ticker.text().upper()

        self.grafico_ativo_canvas.plot_dados(dados_historicos, ticker)
        self.raw_data_table.update_table(dados_historicos)
        
        noticias_combinadas = noticias_av + noticias_newsapi 
        self.news_panel.update_news(noticias_combinadas)
        
        print(f"Dados, Gráfico e Notícias de {ticker} atualizados na UI com sucesso.")


# ==========================================================
# 6. PONTO DE ENTRADA (CORRIGIDO)
# ==========================================================
if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    janela = TerminalFinanceiroApp()
    janela.show()
    
    sys.exit(app.exec())