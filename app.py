import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, date, timedelta
import json
import numpy as np
import hashlib
import urllib.parse
import calendar
import subprocess
import platform
import pickle
import os
import webbrowser
from pathlib import Path

# Configuração da página
st.set_page_config(
    page_title="Dashboard Revisão Carteira",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Inicializar session state para dados persistentes
if 'dados_revisao' not in st.session_state:
    st.session_state.dados_revisao = {}

if 'df_original' not in st.session_state:
    st.session_state.df_original = None

if 'data_hash' not in st.session_state:
    st.session_state.data_hash = None

if 'cached_data' not in st.session_state:
    st.session_state.cached_data = {}

# Função para determinar o mês de trabalho
def get_mes_trabalho():
    """Retorna o mês que deve ser trabalhado baseado no mês atual"""
    hoje = datetime.now()
    mes_trabalho = hoje.month + 1
    ano_trabalho = hoje.year
    
    # Se dezembro, próximo é janeiro do ano seguinte
    if mes_trabalho > 12:
        mes_trabalho = 1
        ano_trabalho += 1
    
    return mes_trabalho, ano_trabalho

# Função para filtrar por mês de trabalho
def filtrar_por_mes_trabalho(df, mes=None, ano=None):
    """Filtra o dataframe pelo mês de trabalho"""
    if mes is None or ano is None:
        mes, ano = get_mes_trabalho()
    
    # Converter a coluna de data se necessário
    if 'Revisão Data Faturamento' in df.columns:
        df['Data_Trabalho'] = pd.to_datetime(df['Revisão Data Faturamento'], errors='coerce')
        
        # Filtrar pelo mês e ano
        mask = (df['Data_Trabalho'].dt.month == mes) & (df['Data_Trabalho'].dt.year == ano)
        return df[mask].copy()
    
    return df

# Função para gerar hash único do GC
def generate_gc_hash(gc_name, mes, ano):
    """Gera um hash único para o GC para criar link personalizado"""
    unique_string = f"{gc_name}_{mes}_{ano}"
    return hashlib.md5(unique_string.encode()).hexdigest()[:10]

# Função para gerar hash dos dados
def generate_data_hash(df):
    """Gera hash dos dados para identificação única"""
    # Usar as primeiras linhas e colunas para gerar um hash único
    sample_data = str(df.head(10).to_dict()) + str(df.columns.tolist())
    return hashlib.md5(sample_data.encode()).hexdigest()[:16]

# Funções para cache persistente em arquivo
def get_cache_file_path():
    """Retorna o caminho do arquivo de cache"""
    return Path("/tmp/carteira_cache.pkl") if os.name != 'nt' else Path("carteira_cache.pkl")

def save_data_to_persistent_cache(df, data_hash):
    """Salva dados em cache persistente (arquivo)"""
    try:
        cache_data = {
            'data_hash': data_hash,
            'dataframe': df,
            'timestamp': datetime.now(),
            'expires_at': datetime.now() + timedelta(days=30)  # Cache dura 30 dias
        }
        
        cache_file = get_cache_file_path()
        with open(cache_file, 'wb') as f:
            pickle.dump(cache_data, f)
        
        # Também salvar no session_state como backup
        if 'global_data_cache' not in st.session_state:
            st.session_state.global_data_cache = {}
        st.session_state.global_data_cache[data_hash] = df.copy()
        
        return True
    except Exception as e:
        st.error(f"Erro ao salvar cache: {str(e)}")
        return False

def load_data_from_persistent_cache(data_hash=None):
    """Carrega dados do cache persistente"""
    try:
        cache_file = get_cache_file_path()
        if not cache_file.exists():
            return None
        
        with open(cache_file, 'rb') as f:
            cache_data = pickle.load(f)
        
        # Verificar se não expirou
        if datetime.now() > cache_data['expires_at']:
            cache_file.unlink()  # Remove arquivo expirado
            return None
        
        # Se hash específico fornecido, verificar se bate
        if data_hash and cache_data['data_hash'] != data_hash:
            return None
        
        # Retornar dados
        df = cache_data['dataframe']
        
        # Salvar também no session_state
        st.session_state.df_original = df
        if 'global_data_cache' not in st.session_state:
            st.session_state.global_data_cache = {}
        st.session_state.global_data_cache[cache_data['data_hash']] = df.copy()
        
        return df, cache_data['data_hash'], cache_data['timestamp']
        
    except Exception as e:
        return None

def get_cache_info():
    """Retorna informações do cache atual"""
    try:
        cache_file = get_cache_file_path()
        if not cache_file.exists():
            return None
        
        with open(cache_file, 'rb') as f:
            cache_data = pickle.load(f)
        
        return {
            'exists': True,
            'hash': cache_data['data_hash'],
            'timestamp': cache_data['timestamp'],
            'expires_at': cache_data['expires_at'],
            'records': len(cache_data['dataframe']),
            'expired': datetime.now() > cache_data['expires_at']
        }
    except:
        return None

# Função para salvar dados no cache global
def save_data_to_cache(df, data_hash):
    """Salva dados no cache global do Streamlit"""
    if 'global_data_cache' not in st.session_state:
        st.session_state.global_data_cache = {}
    
    st.session_state.global_data_cache[data_hash] = df.copy()

# Função para recuperar dados do cache
def get_data_from_cache(data_hash):
    """Recupera dados do cache global"""
    if 'global_data_cache' in st.session_state:
        return st.session_state.global_data_cache.get(data_hash, None)
    return None

# Função para carregar dados
@st.cache_data
def load_data(uploaded_file):
    """Carrega e processa os dados do Excel"""
    try:
        df = pd.read_excel(uploaded_file)
        
        # Limpeza e tratamento dos dados
        if 'Vl.Saldo' in df.columns:
            # Tratar valores que podem vir em diferentes formatos
            df['Vl.Saldo'] = df['Vl.Saldo'].astype(str)
            # Remover espaços e caracteres especiais, exceto números, vírgulas e pontos
            df['Vl.Saldo'] = df['Vl.Saldo'].str.replace(r'[^\d,.-]', '', regex=True)
            # Se tem vírgula como decimal (formato brasileiro), substituir por ponto
            df['Vl.Saldo'] = df['Vl.Saldo'].str.replace(',', '.')
            # Converter para numérico
            df['Vl.Saldo'] = pd.to_numeric(df['Vl.Saldo'], errors='coerce')
        
        if 'Saldo' in df.columns:
            # Mesmo tratamento para Saldo
            df['Saldo'] = df['Saldo'].astype(str)
            df['Saldo'] = df['Saldo'].str.replace(r'[^\d,.-]', '', regex=True)
            df['Saldo'] = df['Saldo'].str.replace(',', '.')
            df['Saldo'] = pd.to_numeric(df['Saldo'], errors='coerce')
        
        # Converter data de entrega original
        if 'Dt. Dej. Rem.' in df.columns:
            df['Dt. Dej. Rem.'] = pd.to_datetime(df['Dt. Dej. Rem.'], format='%d/%m/%Y', errors='coerce')
        
        # Converter data de trabalho (Revisão Data Faturamento)
        if 'Revisão Data Faturamento' in df.columns:
            df['Data_Trabalho'] = pd.to_datetime(df['Revisão Data Faturamento'], errors='coerce')
        
        # Adicionar colunas de controle se não existirem
        if 'Revisao_Realizada' not in df.columns:
            df['Revisao_Realizada'] = False
        
        if 'Data_Original_Alterada' not in df.columns:
            df['Data_Original_Alterada'] = False
            
        if 'Nova_Data_Entrega' not in df.columns:
            df['Nova_Data_Entrega'] = pd.NaT
        
        if 'Data_Revisao' not in df.columns:
            df['Data_Revisao'] = pd.NaT
        
        if 'Revisado_Por' not in df.columns:
            df['Revisado_Por'] = None
            
        return df
    except Exception as e:
        st.error(f"Erro ao carregar arquivo: {str(e)}")
        return None

# Função para aplicar revisões dos session_state
def apply_revisoes_to_dataframe(df):
    """Aplica as revisões salvas no session_state ao dataframe"""
    if not st.session_state.dados_revisao:
        return df
    
    df_updated = df.copy()
    
    for revisao_key, revisao_data in st.session_state.dados_revisao.items():
        # Verificar se revisao_data é um dicionário válido
        if not isinstance(revisao_data, dict):
            continue
            
        # Verificar se tem dados essenciais
        if 'gc' not in revisao_data or 'data_revisao' not in revisao_data:
            continue
            
        # Verificar se é o formato novo (ordem_material) ou antigo (só ordem)
        if '_' in revisao_key and 'ordem' in revisao_data and 'material' in revisao_data:
            # Formato novo: usar ordem + material
            ordem = revisao_data['ordem']
            material = revisao_data['material']
            mask = (df_updated['Ord.venda'] == ordem) & (df_updated['Material'] == material)
        else:
            # Formato antigo: compatibilidade (só ordem)
            ordem = revisao_key if isinstance(revisao_key, (int, str)) else revisao_data.get('ordem', revisao_key)
            mask = df_updated['Ord.venda'] == ordem
        
        if mask.any():
            df_updated.loc[mask, 'Revisao_Realizada'] = True
            
            # Verificar se data_revisao existe antes de usar
            if 'data_revisao' in revisao_data:
                try:
                    df_updated.loc[mask, 'Data_Revisao'] = pd.to_datetime(revisao_data['data_revisao'])
                except:
                    pass  # Se não conseguir converter a data, ignore
            
            # Verificar se gc existe antes de usar
            if 'gc' in revisao_data:
                df_updated.loc[mask, 'Revisado_Por'] = revisao_data['gc']
            
            if revisao_data.get('nova_data'):
                df_updated.loc[mask, 'Data_Original_Alterada'] = True
                try:
                    df_updated.loc[mask, 'Nova_Data_Entrega'] = pd.to_datetime(revisao_data['nova_data'])
                except:
                    pass  # Se não conseguir converter a data, ignore
    
    return df_updated

# Função para calcular métricas
def calculate_metrics(df):
    """Calcula métricas principais"""
    total_registros = len(df)
    total_valor = df['Vl.Saldo'].sum() / 1_000_000  # Em milhões
    total_volume = df['Saldo'].sum()
    registros_revisados = df['Revisao_Realizada'].sum()
    registros_alterados = df['Data_Original_Alterada'].sum()
    perc_revisao = (registros_revisados / total_registros * 100) if total_registros > 0 else 0
    perc_alteracao = (registros_alterados / total_registros * 100) if total_registros > 0 else 0
    
    return {
        'total_registros': total_registros,
        'total_valor': total_valor,
        'total_volume': total_volume,
        'registros_revisados': registros_revisados,
        'registros_alterados': registros_alterados,
        'perc_revisao': perc_revisao,
        'perc_alteracao': perc_alteracao
    }

# Função para gerar resumo por grupo para um GC
def get_resumo_por_grupo(df, gc):
    """Gera resumo por grupo para um GC específico"""
    df_gc = df[df['GC'] == gc]
    
    resumo = df_gc.groupby('Grupo').agg({
        'Ord.venda': 'count',
        'Vl.Saldo': 'sum',
        'Saldo': 'sum'
    }).round(2)
    
    resumo.columns = ['Qtd_Pedidos', 'Valor_Total', 'Volume_Total']
    resumo['Valor_MM'] = (resumo['Valor_Total'] / 1_000_000).round(0)
    resumo = resumo.reset_index()
    
    return resumo

# Função para gerar links personalizados
def generate_personalized_links(df, mes, ano):
    """Gera links personalizados para cada GC"""
    gcs = df['GC'].dropna().unique()
    base_url = "https://dash-carteira-review.streamlit.app"  # URL real do Streamlit
    mes_nome = calendar.month_name[mes]
    
    # Gerar hash dos dados para incluir no link
    data_hash = generate_data_hash(df)
    
    # Salvar dados no cache persistente
    save_data_to_persistent_cache(df, data_hash)
    
    links = {}
    for gc in gcs:
        gc_hash = generate_gc_hash(gc, mes, ano)
        df_gc = df[df['GC'] == gc]
        
        # Dados gerais do GC
        pedidos_gc = len(df_gc)
        valor_gc = df_gc['Vl.Saldo'].sum() / 1_000_000
        volume_gc = df_gc['Saldo'].sum()
        
        # Resumo por grupo
        resumo_grupos = get_resumo_por_grupo(df, gc)
        
        # Incluir hash dos dados no link
        link = f"{base_url}?gc={urllib.parse.quote(gc)}&hash={gc_hash}&mes={mes}&ano={ano}&data={data_hash}"
        links[gc] = {
            'link': link,
            'hash': gc_hash,
            'data_hash': data_hash,
            'pedidos': pedidos_gc,
            'valor': valor_gc,
            'volume': volume_gc,
            'grupos': resumo_grupos,
            'mes_nome': mes_nome,
            'ano': ano
        }
    
    return links

# Função para gerar e-mail personalizado
def gerar_email_outlook(gc, info_gc, mes, ano):
    """Gera estrutura de e-mail para um GC específico"""
    mes_nome = calendar.month_name[mes]
    
    # Extrair primeiro nome para personalização
    primeiro_nome = gc.split()[0] if gc else gc
    
    # Montar resumo por grupos
    grupos_texto = ""
    for _, grupo in info_gc['grupos'].iterrows():
        grupos_texto += f"""        📦 {grupo['Grupo']}:
           • Pedidos: {grupo['Qtd_Pedidos']}
           • Valor: R$ {grupo['Valor_MM']:.0f} milhões
        """
    
    # Corpo do e-mail
    corpo_email = f"""Olá {primeiro_nome},

Vamos revisar a sua carteira para {mes_nome}/{ano}!
Com isso, vamos garantir que a gente inicie o próximo mês mais redondos com a carteira que será faturada, evitando cancelamento de pedidos.

📊 RESUMO DA SUA CARTEIRA:
═══════════════════════════════════════════
📈 Total de Pedidos: {info_gc['pedidos']}
💰 Valor Total: R$ {info_gc['valor']:.0f} milhões

📋 DETALHAMENTO POR GRUPO:
═══════════════════════════════════════════
{grupos_texto}

🔗 LINK PARA REVISÃO:
{info_gc['link']}

📝 INSTRUÇÕES:
1. Clique no link acima
2. Para cada pedido, você pode:
   ✅ Confirmar - se a data está correta
   📅 Revisar - se precisa alterar a data
3. No final, baixe o arquivo JSON e responda anexando ele para mim no e-mail ou me envie no Teams. O arquivo JSON é o protocolo da revisão da sua carteira, através dele conseguiremos com o time ADV atualizar as datas corretamente no SAP.

⏰ PRAZO: Até {get_ultimo_dia_mes()}/{mes:02d}/{ano}

Em caso de dúvidas, entre em contato comigo.

Att,
Otávio Monteiro"""
    
    assunto = f"Revisão Carteira {mes_nome}/{ano} - {gc} - {info_gc['pedidos']} pedidos"
    
    return assunto, corpo_email

# Função auxiliar para obter último dia do mês
def get_ultimo_dia_mes():
    """Retorna último dia do mês atual"""
    from calendar import monthrange
    hoje = datetime.now()
    _, ultimo_dia = monthrange(hoje.year, hoje.month)
    return ultimo_dia

# Função para resolver nome no Outlook
def resolver_nome_outlook(outlook, nome):
    """Tentar resolver nome no Outlook"""
    try:
        recipient = outlook.Session.CreateRecipient(nome)
        recipient.Resolve()
        if recipient.Resolved:
            return recipient.Address
        else:
            print(f"Aviso: Não foi possível resolver o nome '{nome}' no Outlook")
            return nome
    except:
        print(f"Erro ao resolver nome '{nome}' no Outlook")
        return nome

# Função para extrair primeiro nome
def extrair_primeiro_nome(nome_completo):
    """Extrair apenas o primeiro nome para deixar o email mais natural"""
    try:
        if pd.isna(nome_completo) or not nome_completo:
            return nome_completo
        # Pegar apenas a primeira palavra (primeiro nome)
        primeiro_nome = str(nome_completo).strip().split()[0]
        return primeiro_nome
    except:
        return nome_completo

# Função para abrir Outlook com e-mail
def abrir_outlook_com_email(destinatario, assunto, corpo):
    """Abre o Outlook com o e-mail pré-preenchido usando COM do Outlook"""
    try:
        # Tentar usar COM do Outlook primeiro (mais confiável)
        try:
            import win32com.client as win32
            outlook = win32.Dispatch('outlook.application')
            
            # Criar novo e-mail
            mail = outlook.CreateItem(0)  # 0 = olMailItem
            
            # Resolver nome do destinatário
            destinatario_resolvido = resolver_nome_outlook(outlook, destinatario)
            
            mail.To = destinatario_resolvido
            mail.Subject = assunto
            mail.Body = corpo
            
            # Exibir o e-mail (não enviar automaticamente)
            mail.Display(True)
            
            return True
            
        except ImportError:
            # Se não tem win32com, usar método mailto
            return abrir_outlook_mailto(destinatario, assunto, corpo)
        except Exception as e:
            print(f"Erro no COM do Outlook: {e}")
            # Fallback para mailto
            return abrir_outlook_mailto(destinatario, assunto, corpo)
            
    except Exception as e:
        print(f"❌ Erro ao abrir Outlook: {e}")
        return False

def abrir_outlook_mailto(destinatario, assunto, corpo):
    """Método de fallback usando mailto URL"""
    try:
        # Codificar para URL
        assunto_encoded = urllib.parse.quote(assunto)
        corpo_encoded = urllib.parse.quote(corpo)
        
        # Criar mailto URL
        mailto_url = f"mailto:{destinatario}?subject={assunto_encoded}&body={corpo_encoded}"
        
        # Abrir baseado no sistema operacional
        sistema = platform.system()
        if sistema == "Windows":
            # Tentar diferentes métodos no Windows
            try:
                # Método 1: usar os.startfile
                import os
                os.startfile(mailto_url)
                return True
            except:
                try:
                    # Método 2: usar subprocess com start
                    subprocess.run(f'start "" "{mailto_url}"', shell=True, check=False)
                    return True
                except:
                    # Método 3: usar webbrowser
                    import webbrowser
                    webbrowser.open(mailto_url)
                    return True
        elif sistema == "Darwin":  # macOS
            subprocess.run(["open", mailto_url])
            return True
        else:  # Linux
            subprocess.run(["xdg-open", mailto_url])
            return True
            
    except Exception as e:
        return False

# Função para formulário de revisão
def formulario_revisao_gc(df, gc_selecionado, mes, ano):
    """Interface de revisão para um GC específico"""
    mes_nome = calendar.month_name[mes]
    st.header(f"📝 Revisão de Carteira - {gc_selecionado}")
    st.subheader(f"Mês de trabalho: {mes_nome}/{ano}")
    
    df_gc = df[df['GC'] == gc_selecionado].copy()
    
    if len(df_gc) == 0:
        st.warning("Nenhum pedido encontrado para este GC no período.")
        return
    
    # Resumo por grupos
    resumo_grupos = get_resumo_por_grupo(df_gc, gc_selecionado)
    
    # Métricas do GC
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total de Pedidos", len(df_gc))
    with col2:
        st.metric("Valor Total", f"R$ {df_gc['Vl.Saldo'].sum()/1_000_000:.0f}M")
    with col3:
        revisados = df_gc['Revisao_Realizada'].sum()
        st.metric("Já Revisados", f"{revisados}/{len(df_gc)}")
    with col4:
        perc_rev = (revisados / len(df_gc) * 100) if len(df_gc) > 0 else 0
        st.metric("% Revisão", f"{perc_rev:.1f}%")
    
    # Mostrar resumo por grupos
    st.subheader("📊 Resumo por Grupo de Produtos")
    st.dataframe(
        resumo_grupos,
        column_config={
            "Grupo": "Grupo de Produto",
            "Qtd_Pedidos": "Qtd. Pedidos",
            "Valor_MM": "Valor (R$ MM)",
            "Volume_Total": "Volume Total"
        },
        use_container_width=True,
        hide_index=True
    )
    
    st.markdown("---")
    
    # Filtros para o GC
    col1, col2 = st.columns(2)
    with col1:
        status_filter = st.selectbox(
            "Filtrar por Status",
            ["Todos", "Pendentes", "Revisados"],
            key="status_filter_gc"
        )
    with col2:
        grupo_filter = st.selectbox(
            "Filtrar por Grupo",
            ["Todos"] + sorted(df_gc['Grupo'].dropna().unique().tolist()),
            key="grupo_filter_gc"
        )
    
    # Aplicar filtros
    df_filtered = df_gc.copy()
    if status_filter == "Pendentes":
        df_filtered = df_filtered[df_filtered['Revisao_Realizada'] == False]
    elif status_filter == "Revisados":
        df_filtered = df_filtered[df_filtered['Revisao_Realizada'] == True]
    
    if grupo_filter != "Todos":
        df_filtered = df_filtered[df_filtered['Grupo'] == grupo_filter]
    
    st.subheader(f"📋 Pedidos para Revisão ({len(df_filtered)} itens)")
    
    # Processar cada pedido
    for idx, row in df_filtered.iterrows():
        ordem = row['Ord.venda']
        material = row['Material'] if 'Material' in row and pd.notna(row['Material']) else 'sem_material'
        # Criar ID único combinando ordem + material para itens múltiplos da mesma ordem
        unique_id = f"{ordem}_{material}_{idx}"
        
        with st.container():
            col1, col2, col3 = st.columns([2, 2, 1])
            
            with col1:
                st.write(f"**Ordem:** {ordem}")
                st.write(f"**Cliente:** {row['Nome Emissor']}")
                st.write(f"**Produto:** {row['Desc. Material']}")
                st.write(f"**Valor:** R$ {row['Vl.Saldo']:,.0f}")
            
            with col2:
                data_trabalho = row['Data_Trabalho'].strftime('%d/%m/%Y') if pd.notna(row['Data_Trabalho']) else 'N/A'
                status_credito = row['Status crédito'] if pd.notna(row['Status crédito']) else 'N/A'
                st.write(f"**Data Prevista:** {data_trabalho}")
                st.write(f"**Volume:** {row['Saldo']:,.2f}")
                st.write(f"**Grupo:** {row['Grupo']}")
                st.write(f"**Status Crédito:** {status_credito}")
            
            with col3:
                # Status atual
                if row['Revisao_Realizada']:
                    st.success("✅ Revisado")
                    if row['Data_Original_Alterada']:
                        st.info("📅 Data alterada")
                else:
                    st.warning("⏳ Pendente")
                
                # Botões de ação
                col_check, col_rev = st.columns(2)
                
                with col_check:
                    if st.button("✅ OK", key=f"check_{unique_id}", help="Data está correta"):
                        # Usar chave única ordem + material para salvar revisão
                        revisao_key = f"{ordem}_{material}"
                        st.session_state.dados_revisao[revisao_key] = {
                            'gc': gc_selecionado,
                            'ordem': ordem,
                            'material': material,
                            'data_revisao': datetime.now().isoformat(),
                            'nova_data': None,
                            'acao': 'check'
                        }
                        st.rerun()
                
                with col_rev:
                    if st.button("📅 Revisar", key=f"rev_{unique_id}", help="Alterar data"):
                        st.session_state[f'revisar_{unique_id}'] = True
                        st.rerun()
        
        # Formulário para alterar data (aparece quando clica em Revisar)
        if st.session_state.get(f'revisar_{unique_id}', False):
            with st.form(f"form_data_{unique_id}"):
                st.write("**Alterar Data de Entrega:**")
                col1, col2 = st.columns(2)
                
                with col1:
                    nova_data = st.date_input(
                        "Nova Data de Entrega",
                        value=row['Data_Trabalho'].date() if pd.notna(row['Data_Trabalho']) else date.today(),
                        key=f"data_{unique_id}"
                    )
                
                with col2:
                    justificativa = st.text_input(
                        "Justificativa (opcional)",
                        key=f"just_{unique_id}"
                    )
                
                col_save, col_cancel = st.columns(2)
                with col_save:
                    if st.form_submit_button("💾 Salvar"):
                        # Usar chave única ordem + material para salvar revisão
                        revisao_key = f"{ordem}_{material}"
                        st.session_state.dados_revisao[revisao_key] = {
                            'gc': gc_selecionado,
                            'ordem': ordem,
                            'material': material,
                            'data_revisao': datetime.now().isoformat(),
                            'nova_data': nova_data.isoformat(),
                            'justificativa': justificativa,
                            'acao': 'revisao'
                        }
                        st.session_state[f'revisar_{unique_id}'] = False
                        st.success("Data alterada com sucesso!")
                        st.rerun()
                
                with col_cancel:
                    if st.form_submit_button("❌ Cancelar"):
                        st.session_state[f'revisar_{unique_id}'] = False
                        st.rerun()
        
        st.markdown("---")
    
    # Seção de finalização e envio para o GC
    st.header("🎯 Finalizar Revisão")
    
    # Calcular estatísticas de conclusão
    total_pedidos_gc = len(df_gc)
    revisados = df_gc['Revisao_Realizada'].sum()
    perc_conclusao = (revisados / total_pedidos_gc * 100) if total_pedidos_gc > 0 else 0
    
    # Verificar se tem revisões feitas nesta sessão
    revisoes_gc = {k: v for k, v in st.session_state.dados_revisao.items() 
                   if v.get('gc') == gc_selecionado}
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.subheader("📊 Status da sua Revisão")
        
        progress_bar = st.progress(perc_conclusao / 100)
        st.write(f"**Progresso:** {revisados}/{total_pedidos_gc} pedidos revisados ({perc_conclusao:.1f}%)")
        
        if revisoes_gc:
            st.success(f"✅ Você fez {len(revisoes_gc)} revisões nesta sessão!")
        else:
            st.info("ℹ️ Nenhuma revisão feita nesta sessão ainda.")
    
    with col2:
        st.subheader("📤 Enviar Revisões")
        
        # E-mail fixo do administrador
        email_admin = "otavio.monteiro@icl-group.com"
        st.info(f"📧 **Administrador:** {email_admin}")
        
        if revisoes_gc:
            # Gerar nome do arquivo
            timestamp = datetime.now().strftime('%Y%m%d_%H%M')
            nome_arquivo = f"revisoes_{gc_selecionado.replace(' ', '_')}_{mes_nome}_{ano}_{timestamp}.json"
            
            # Preparar dados das revisões para download
            dados_envio = {
                'gc': gc_selecionado,
                'mes': mes,
                'ano': ano,
                'mes_nome': mes_nome,
                'timestamp': datetime.now().isoformat(),
                'total_pedidos': total_pedidos_gc,
                'total_revisados': len(revisoes_gc),
                'revisoes': revisoes_gc
            }
            
            revisoes_json = json.dumps(dados_envio, indent=2, default=str, ensure_ascii=False)
            
            # Botão de download das revisões
            st.download_button(
                "📱 Baixar Backup",
                data=revisoes_json,
                file_name=nome_arquivo,
                mime="application/json",
                help="Baixa suas revisões para enviar ao Otávio",
                type="primary"
            )
            
            # Orientação simples
            st.success("✅ Agora envie o arquivo baixado para:")
            st.info("📧 **E-mail:** otavio.monteiro@icl-group.com")
            st.info("💬 **Teams:** Otávio Monteiro")
            st.caption(f"📎 **Assunto:** Revisão Carteira - {gc_selecionado} - {mes_nome}/{ano}")
        else:
            st.warning("⚠️ Faça pelo menos uma revisão antes de enviar!")
    
    # Instruções para o GC
    with st.expander("📋 Como Finalizar sua Revisão", expanded=False):
        st.markdown(f"""
        ### 🎯 Passos Simples:
        
        **1. ✅ Revise todos os pedidos**
        - Clique "✅ OK" se a data está correta
        - Clique "� Revisar" para alterar a data
        
        **2. 📤 Quando terminar**
        - Clique em "📱 Baixar Backup" acima
        - Salve o arquivo no seu computador
        
        **3. 📧 Envie para o Otávio**
        - **E-mail:** otavio.monteiro@icl-group.com
        - **Teams:** Otávio Monteiro  
        - **Anexe** o arquivo JSON baixado
        - **Assunto:** "Revisão Carteira - [SEU NOME] - {mes_nome}/{ano}"
        
        **🎉 Pronto! Só isso!**
        """)
    
    st.markdown("---")
# Função para gerar e-mail de notificação de conclusão
def gerar_email_conclusao_gc(gc, total_revisados, total_pedidos, mes, ano, dados_revisoes_json):
    """Gera e-mail de notificação quando GC termina revisão"""
    mes_nome = calendar.month_name[mes]
    perc_revisao = (total_revisados / total_pedidos * 100) if total_pedidos > 0 else 0
    
    assunto = f"✅ Revisão Concluída - {gc} - {mes_nome}/{ano}"
    
    corpo_email = f"""Olá,

O GC {gc} concluiu a revisão da carteira de {mes_nome}/{ano}.

📊 RESUMO DA REVISÃO:
═══════════════════════════════════════════
👤 GC: {gc}
📅 Período: {mes_nome}/{ano}
📋 Total de Pedidos: {total_pedidos}
✅ Pedidos Revisados: {total_revisados}
📈 % Conclusão: {perc_revisao:.1f}%
🕐 Data/Hora: {datetime.now().strftime('%d/%m/%Y às %H:%M')}

📎 DADOS DA REVISÃO (JSON):
═══════════════════════════════════════════

{dados_revisoes_json}

═══════════════════════════════════════════

🔄 PRÓXIMOS PASSOS:
1. Copiar o JSON acima e salvar como arquivo .json
2. Importar no dashboard principal
3. Consolidar com outras revisões
4. Gerar relatório final

Att,
{gc} - Sistema de Revisão de Carteira
    """
    
    return assunto, corpo_email

# Interface principal
def main():
    # Verificar se é acesso via link personalizado
    query_params = st.query_params
    gc_from_url = query_params.get("gc", None)
    hash_from_url = query_params.get("hash", None)
    mes_from_url = int(query_params.get("mes", 0)) if query_params.get("mes") else None
    ano_from_url = int(query_params.get("ano", 0)) if query_params.get("ano") else None
    data_hash_from_url = query_params.get("data", None)
    
    if gc_from_url and hash_from_url and mes_from_url and ano_from_url:
        # Modo formulário para GC específico
        mes_nome = calendar.month_name[mes_from_url]
        st.title(f"📋 Revisão de Carteira - {gc_from_url}")
        st.caption(f"Período: {mes_nome}/{ano_from_url}")
        
        # Tentar recuperar dados em ordem de prioridade
        df_original = None
        
        # 1. Tentar cache persistente com hash específico
        if data_hash_from_url:
            cache_result = load_data_from_persistent_cache(data_hash_from_url)
            if cache_result:
                df_original, _, _ = cache_result
        
        # 2. Tentar cache persistente sem hash específico
        if df_original is None:
            cache_result = load_data_from_persistent_cache()
            if cache_result:
                df_original, _, _ = cache_result
        
        # 3. Tentar cache em memória
        if df_original is None and data_hash_from_url:
            df_original = get_data_from_cache(data_hash_from_url)
        
        # 4. Tentar session_state
        if df_original is None:
            df_original = st.session_state.df_original
        
        if df_original is None:
            # Interface limpa para GCs - sem detalhes técnicos
            st.error("📋 Sistema Temporariamente Indisponível")
            
            st.markdown("""
            ### 🔄 Aguarde um momento...
            
            Os dados da carteira estão sendo atualizados pelo sistema.
            
            **O que fazer:**
            - ✅ Aguarde alguns minutos e recarregue a página
            - ✅ Tente novamente em 5-10 minutos
            - ✅ Se o problema persistir, entre em contato com a equipe
            
            **Não é um erro do seu lado** - é apenas uma atualização de rotina do sistema.
            """)
            
            col1, col2 = st.columns(2)
            with col1:
                if st.button("🔄 Recarregar Página", type="primary"):
                    st.rerun()
            
            with col2:
                st.markdown("📧 **Dúvidas?** Entre em contato com a equipe comercial")
            
            st.stop()
            
            with st.expander("� Instruções para Resolver", expanded=True):
                st.markdown("""
                **Como resolver este problema:**
                
                1. **Abra o dashboard principal** em uma nova aba
                2. **Faça upload** do arquivo Excel da carteira
                3. **Gere os links** novamente na seção "Links Personalizados"
                4. **Use o novo link** gerado
                
                **Por que isso acontece?**
                - Os dados não persistem entre sessões diferentes
                - Cada link do GC precisa que os dados tenham sido carregados primeiro
                
                **Solução definitiva:**
                - O administrador deve carregar os dados no dashboard principal
                - Depois disso, os links funcionarão por algumas horas
                """)
            
            col1, col2 = st.columns(2)
            with col1:
                if st.button("🏠 Ir para Dashboard Principal", type="primary"):
                    st.markdown(f"🔗 [Clique aqui para ir ao Dashboard](https://dash-carteira-review.streamlit.app)")
            
            with col2:
                if st.button("🔄 Tentar Novamente"):
                    st.rerun()
            
            st.stop()
        
        # Verificar hash de segurança
        expected_hash = generate_gc_hash(gc_from_url, mes_from_url, ano_from_url)
        if hash_from_url != expected_hash:
            st.error("🔒 Link inválido ou expirado.")
            st.stop()
        
        # Filtrar por mês de trabalho e aplicar revisões
        df_mes = filtrar_por_mes_trabalho(df_original, mes_from_url, ano_from_url)
        df_with_revisoes = apply_revisoes_to_dataframe(df_mes)
        formulario_revisao_gc(df_with_revisoes, gc_from_url, mes_from_url, ano_from_url)
        
    else:
        # Modo dashboard principal
        st.title("📊 Dashboard de Revisão da Carteira de Pedidos")
        
        # Mostrar mês de trabalho atual
        mes_trabalho, ano_trabalho = get_mes_trabalho()
        mes_nome = calendar.month_name[mes_trabalho]
        st.info(f"🗓️ Mês de trabalho atual: **{mes_nome}/{ano_trabalho}**")
        st.markdown("---")
        
        # Sidebar para upload e controles
        with st.sidebar:
            st.header("📁 Upload de Dados")
            uploaded_file = st.file_uploader(
                "Carregar arquivo Excel da carteira",
                type=['xlsx', 'xls'],
                help="Arquivo com a estrutura de dados da carteira de pedidos"
            )
            
            # Seletor de mês de trabalho
            st.header("🗓️ Mês de Trabalho")
            
            col1, col2 = st.columns(2)
            with col1:
                mes_selecionado = st.selectbox(
                    "Mês",
                    range(1, 13),
                    index=mes_trabalho-1,
                    format_func=lambda x: calendar.month_name[x]
                )
            with col2:
                ano_selecionado = st.number_input(
                    "Ano",
                    min_value=2020,
                    max_value=2030,
                    value=ano_trabalho
                )
            
            if uploaded_file is not None:
                df = load_data(uploaded_file)
                
                if df is not None:
                    # Salvar no session state
                    st.session_state.df_original = df
                    
                    # Gerar e salvar hash dos dados
                    data_hash = generate_data_hash(df)
                    st.session_state.data_hash = data_hash
                    
                    # Salvar no cache persistente
                    save_success = save_data_to_persistent_cache(df, data_hash)
                    
                    # Filtrar por mês de trabalho
                    df_mes = filtrar_por_mes_trabalho(df, mes_selecionado, ano_selecionado)
                    
                    # Aplicar revisões existentes
                    df_mes = apply_revisoes_to_dataframe(df_mes)
                    
                    st.success(f"✅ Arquivo carregado")
                    st.info(f"📊 {len(df):,} registros totais")
                    st.info(f"📅 {len(df_mes):,} registros para {calendar.month_name[mes_selecionado]}/{ano_selecionado}")
                    
                    if save_success:
                        st.success(f"🔗 Links personalizados prontos! Cache válido por 30 dias (Hash: {data_hash[:8]}...)")
                    else:
                        st.warning("⚠️ Cache temporário salvo apenas na sessão atual")
                    
                    # Botões para gerenciar revisões
                    col1, col2, col3 = st.columns(3)
                    
                    with col1:
                        if st.button("🗑️ Limpar Revisões"):
                            st.session_state.dados_revisao = {}
                            st.rerun()
                    
                    with col2:
                        # Download das revisões
                        if st.session_state.dados_revisao:
                            revisoes_json = json.dumps(st.session_state.dados_revisao, indent=2, default=str)
                            st.download_button(
                                "💾 Salvar Revisões",
                                data=revisoes_json,
                                file_name=f"revisoes_{mes_selecionado}_{ano_selecionado}_{datetime.now().strftime('%Y%m%d_%H%M')}.json",
                                mime="application/json",
                                help="Baixa as revisões para não perder os dados"
                            )
                    
                    with col3:
                        # Upload de revisões anteriores
                        uploaded_revisoes = st.file_uploader(
                            "📂 Carregar Revisões",
                            type=['json'],
                            help="Carrega revisões salvas anteriormente",
                            key="upload_revisoes"
                        )
                        
                        if uploaded_revisoes is not None:
                            try:
                                revisoes_carregadas = json.load(uploaded_revisoes)
                                st.session_state.dados_revisao.update(revisoes_carregadas)
                                st.success("✅ Revisões carregadas!")
                                st.rerun()
                            except Exception as e:
                                st.error(f"❌ Erro ao carregar: {str(e)}")
                    
                    # Seção para consolidar revisões dos GCs
                    st.header("📥 Consolidar Revisões dos GCs")
                    
                    col1, col2 = st.columns([2, 1])
                    
                    with col1:
                        # Upload múltiplo de arquivos de revisão
                        arquivos_revisoes = st.file_uploader(
                            "📂 Carregar Revisões dos GCs",
                            type=['json'],
                            accept_multiple_files=True,
                            help="Selecione os arquivos JSON enviados pelos GCs",
                            key="upload_revisoes_gcs"
                        )
                        
                        if arquivos_revisoes:
                            st.write(f"**📁 {len(arquivos_revisoes)} arquivo(s) selecionado(s):**")
                            
                            dados_consolidados = {}
                            info_gcs = []
                            
                            for arquivo in arquivos_revisoes:
                                try:
                                    dados_gc = json.load(arquivo)
                                    gc_nome = dados_gc.get('gc', 'GC Desconhecido')
                                    total_revisoes = dados_gc.get('total_revisados', 0)
                                    timestamp = dados_gc.get('timestamp', 'N/A')
                                    
                                    # Consolidar revisões
                                    revisoes_gc = dados_gc.get('revisoes', {})
                                    dados_consolidados.update(revisoes_gc)
                                    
                                    # Informações para exibir
                                    info_gcs.append({
                                        'Arquivo': arquivo.name,
                                        'GC': gc_nome,
                                        'Revisões': total_revisoes,
                                        'Data/Hora': pd.to_datetime(timestamp).strftime('%d/%m/%Y %H:%M') if timestamp != 'N/A' else 'N/A'
                                    })
                                    
                                except Exception as e:
                                    st.error(f"❌ Erro ao processar {arquivo.name}: {str(e)}")
                            
                            if info_gcs:
                                # Mostrar resumo dos arquivos
                                df_info = pd.DataFrame(info_gcs)
                                st.dataframe(df_info, use_container_width=True, hide_index=True)
                                
                                total_revisoes_consolidadas = sum([info['Revisões'] for info in info_gcs])
                                st.success(f"✅ **Total consolidado:** {total_revisoes_consolidadas} revisões de {len(info_gcs)} GC(s)")
                    
                    with col2:
                        if arquivos_revisoes and dados_consolidados:
                            st.subheader("🔄 Ações")
                            
                            # Botão para aplicar todas as revisões
                            if st.button("🔄 Consolidar Todas", type="primary", help="Aplica todas as revisões ao sistema"):
                                # Atualizar session_state com as revisões consolidadas
                                st.session_state.dados_revisao.update(dados_consolidados)
                                st.success(f"✅ {len(dados_consolidados)} revisões consolidadas!")
                                st.balloons()
                                st.rerun()
                            
                            # Botão para baixar consolidado
                            if st.button("💾 Baixar Consolidado", help="Baixa arquivo consolidado de todas as revisões"):
                                timestamp = datetime.now().strftime('%Y%m%d_%H%M')
                                consolidado = {
                                    'consolidacao_timestamp': datetime.now().isoformat(),
                                    'total_gcs': len(info_gcs),
                                    'total_revisoes': len(dados_consolidados),
                                    'gcs_participantes': [info['GC'] for info in info_gcs],
                                    'revisoes': dados_consolidados
                                }
                                
                                json_consolidado = json.dumps(consolidado, indent=2, default=str, ensure_ascii=False)
                                
                                st.download_button(
                                    "📥 Download Consolidado",
                                    data=json_consolidado,
                                    file_name=f"revisoes_consolidadas_{mes_selecionado}_{ano_selecionado}_{timestamp}.json",
                                    mime="application/json"
                                )
                        else:
                            st.info("👆 Carregue arquivos de revisão para ver as opções de consolidação")
                    
                    # Instruções para consolidação
                    with st.expander("📋 Como Consolidar Revisões dos GCs", expanded=False):
                        st.markdown("""
                        ### 🎯 Processo de Consolidação:
                        
                        **1. 📧 Receba os e-mails dos GCs**
                        - Cada GC enviará um e-mail com o arquivo JSON anexo
                        - Salve todos os arquivos em uma pasta
                        
                        **2. 📂 Carregue os arquivos**
                        - Use "Carregar Revisões dos GCs"
                        - Selecione múltiplos arquivos de uma vez
                        - O sistema mostrará um resumo de cada GC
                        
                        **3. 🔄 Consolide tudo**
                        - Clique em "Consolidar Todas"
                        - Todas as revisões serão aplicadas ao dashboard
                        - As métricas serão atualizadas automaticamente
                        
                        **4. 💾 Salve o resultado**
                        - Use "Baixar Consolidado" para ter um backup
                        - Exporte as métricas finais
                        
                        ---
                        
                        **✅ Vantagens:**
                        - ✅ Cada GC trabalha independentemente
                        - ✅ Consolidação centralizada e controlada
                        - ✅ Rastreabilidade completa
                        - ✅ Backup automático de todas as etapas
                        """)
                    
                    # Alerta sobre persistência
                    st.warning("⚠️ **IMPORTANTE**: As revisões não persistem entre sessões. Use 'Salvar Revisões' regularmente!")
                    
                    # Informações do cache
                    cache_info = get_cache_info()
                    if cache_info and cache_info['exists']:
                        st.header("💾 Status do Cache")
                        if not cache_info['expired']:
                            st.success(f"✅ Cache ativo - {cache_info['records']:,} registros")
                            st.info(f"📅 Expira em: {cache_info['expires_at'].strftime('%d/%m/%Y %H:%M')}")
                        else:
                            st.error("❌ Cache expirado")
                            if st.button("🔄 Recarregar Cache"):
                                # Força recarga se há dados no session_state
                                if st.session_state.df_original is not None:
                                    data_hash = generate_data_hash(st.session_state.df_original)
                                    save_data_to_persistent_cache(st.session_state.df_original, data_hash)
                                    st.rerun()
                    else:
                        # Tentar carregar cache existente na inicialização
                        cache_result = load_data_from_persistent_cache()
                        if cache_result:
                            df_cache, hash_cache, timestamp_cache = cache_result
                            st.header("💾 Cache Carregado")
                            st.success(f"✅ Dados carregados do cache ({len(df_cache):,} registros)")
                            st.info(f"📅 Carregado em: {timestamp_cache.strftime('%d/%m/%Y %H:%M')}")
                            
                            # Atualizar session state com dados do cache
                            st.session_state.df_original = df_cache
                            st.session_state.data_hash = hash_cache
                    
                    # Filtros adicionais
                    st.header("🔍 Filtros")
                    
                    if len(df_mes) > 0:
                        # Filtro de Status de Crédito
                        status_credito_disponiveis = ['Todos'] + sorted(df_mes['Status crédito'].dropna().unique().tolist())
                        status_credito_selecionado = st.selectbox("Status de Crédito", status_credito_disponiveis, key="status_credito_filter")
                        
                        diretorias_disponiveis = ['Todas'] + sorted(df_mes['DIRETORIA'].dropna().unique().tolist())
                        diretoria_selecionada = st.selectbox("Diretoria", diretorias_disponiveis)
                        
                        grupos_disponiveis = ['Todos'] + sorted(df_mes['Grupo'].dropna().unique().tolist())
                        grupo_selecionado = st.selectbox("Grupo de Produto", grupos_disponiveis)
                        
                        status_revisao = st.selectbox(
                            "Status da Revisão", 
                            ['Todos', 'Revisados', 'Pendentes', 'Com Data Alterada']
                        )
        
        # Conteúdo principal
        if uploaded_file is not None and st.session_state.df_original is not None:
            # Filtrar por mês de trabalho
            df_mes = filtrar_por_mes_trabalho(st.session_state.df_original, mes_selecionado, ano_selecionado)
            df = apply_revisoes_to_dataframe(df_mes)
            
            if len(df) == 0:
                st.warning(f"⚠️ Nenhum registro encontrado para {calendar.month_name[mes_selecionado]}/{ano_selecionado}")
                st.stop()
            
            # Aplicar filtros adicionais
            df_filtrado = df.copy()
            
            # Filtro por status de crédito
            if status_credito_selecionado != 'Todos':
                df_filtrado = df_filtrado[df_filtrado['Status crédito'] == status_credito_selecionado]
            
            if diretoria_selecionada != 'Todas':
                df_filtrado = df_filtrado[df_filtrado['DIRETORIA'] == diretoria_selecionada]
            
            if grupo_selecionado != 'Todos':
                df_filtrado = df_filtrado[df_filtrado['Grupo'] == grupo_selecionado]
            
            if status_revisao == 'Revisados':
                df_filtrado = df_filtrado[df_filtrado['Revisao_Realizada'] == True]
            elif status_revisao == 'Pendentes':
                df_filtrado = df_filtrado[df_filtrado['Revisao_Realizada'] == False]
            elif status_revisao == 'Com Data Alterada':
                df_filtrado = df_filtrado[df_filtrado['Data_Original_Alterada'] == True]
            
            # Métricas principais - Carteira Total vs Filtrada
            metricas = calculate_metrics(df_filtrado)
            metricas_geral = calculate_metrics(df)
            
            # Header com informação do mês
            st.header(f"📈 Métricas da Carteira - {calendar.month_name[mes_selecionado]}/{ano_selecionado}")
            
            # Métricas da carteira total (sem filtros)
            st.subheader("📊 Visão Geral da Carteira")
            col1, col2, col3, col4, col5 = st.columns(5)
            
            with col1:
                st.metric("Total Geral", f"{metricas_geral['total_registros']:,}")
            
            with col2:
                st.metric("Valor Total (R$ MM)", f"R$ {metricas_geral['total_valor']:.0f}")
            
            with col3:
                st.metric("Volume Total", f"{metricas_geral['total_volume']:,.0f}")
            
            with col4:
                st.metric("% Revisão Geral", f"{metricas_geral['perc_revisao']:.1f}%")
            
            with col5:
                st.metric("% Alterações", f"{metricas_geral['perc_alteracao']:.1f}%")
            
            # Métricas com filtros aplicados (se houver)
            if (status_credito_selecionado != 'Todos' or diretoria_selecionada != 'Todas' or 
                grupo_selecionado != 'Todos' or status_revisao != 'Todos'):
                
                st.subheader("🔍 Visão Filtrada")
                col1, col2, col3, col4, col5 = st.columns(5)
                
                with col1:
                    delta_registros = metricas['total_registros'] - metricas_geral['total_registros']
                    st.metric("Registros Filtrados", f"{metricas['total_registros']:,}", 
                             f"{delta_registros:+,}")
                
                with col2:
                    delta_valor = metricas['total_valor'] - metricas_geral['total_valor']
                    st.metric("Valor Filtrado (R$ MM)", f"R$ {metricas['total_valor']:.0f}",
                             f"R$ {delta_valor:+.0f}")
                
                with col3:
                    delta_volume = metricas['total_volume'] - metricas_geral['total_volume']
                    st.metric("Volume Filtrado", f"{metricas['total_volume']:,.0f}",
                             f"{delta_volume:+,.0f}")
                
                with col4:
                    delta_revisao = metricas['perc_revisao'] - metricas_geral['perc_revisao']
                    st.metric("% Revisão Filtrada", f"{metricas['perc_revisao']:.1f}%",
                             f"{delta_revisao:+.1f}%")
                
                with col5:
                    delta_alteracao = metricas['perc_alteracao'] - metricas_geral['perc_alteracao']
                    st.metric("% Alterações Filtrada", f"{metricas['perc_alteracao']:.1f}%",
                             f"{delta_alteracao:+.1f}%")
            
            # Análise específica por Status de Crédito
            st.header("💳 Análise por Status de Crédito")
            
            # Métricas de crédito
            credito_stats = df.groupby('Status crédito').agg({
                'Ord.venda': 'count',
                'Vl.Saldo': 'sum',
                'Saldo': 'sum',
                'Revisao_Realizada': ['sum', 'count'],
                'Data_Original_Alterada': 'sum'
            }).round(2)
            
            credito_stats.columns = ['Qtd_Pedidos', 'Valor_Total', 'Volume_Total', 'Revisados', 'Total_Rev', 'Alterados']
            credito_stats['Valor_MM'] = (credito_stats['Valor_Total'] / 1_000_000).round(0)
            credito_stats['Perc_Revisao'] = (credito_stats['Revisados'] / credito_stats['Total_Rev'] * 100).round(1)
            credito_stats['Perc_Alteracao'] = (credito_stats['Alterados'] / credito_stats['Total_Rev'] * 100).round(1)
            credito_stats = credito_stats.reset_index()
            
            col1, col2 = st.columns(2)
            
            with col1:
                # Tabela resumo por status de crédito
                st.subheader("📋 Resumo por Status de Crédito")
                st.dataframe(
                    credito_stats[['Status crédito', 'Qtd_Pedidos', 'Valor_MM', 'Volume_Total', 'Perc_Revisao', 'Perc_Alteracao']],
                    column_config={
                        "Status crédito": "Status de Crédito",
                        "Qtd_Pedidos": "Qtd. Pedidos",
                        "Valor_MM": "Valor (R$ MM)",
                        "Volume_Total": "Volume Total",
                        "Perc_Revisao": "% Revisão",
                        "Perc_Alteracao": "% Alteração"
                    },
                    use_container_width=True,
                    hide_index=True
                )
            
            with col2:
                # Gráfico de distribuição por status de crédito
                fig_credito = px.pie(
                    credito_stats,
                    values='Valor_MM',
                    names='Status crédito',
                    title='Distribuição de Valor por Status de Crédito (R$ MM)',
                    color_discrete_map={
                        'Liberados': '#28a745',
                        'Não liberado': '#dc3545',
                        'Bloqueados': '#ffc107'
                    }
                )
                fig_credito.update_layout(height=400)
                st.plotly_chart(fig_credito, use_container_width=True)
            
            # Gráficos de análise
            st.header("📊 Análise por Diretoria")
            
            col1, col2 = st.columns(2)
            
            with col1:
                # Gráfico de % de revisão por diretoria
                revisao_diretoria = df.groupby('DIRETORIA').agg({
                    'Revisao_Realizada': ['count', 'sum'],
                    'Data_Original_Alterada': 'sum'
                }).round(2)
                revisao_diretoria.columns = ['Total', 'Revisados', 'Alterados']
                revisao_diretoria['Perc_Revisao'] = (revisao_diretoria['Revisados'] / revisao_diretoria['Total'] * 100).round(1)
                revisao_diretoria['Perc_Alteracao'] = (revisao_diretoria['Alterados'] / revisao_diretoria['Total'] * 100).round(1)
                revisao_diretoria = revisao_diretoria.reset_index()
                
                fig_revisao = px.bar(
                    revisao_diretoria,
                    x='DIRETORIA',
                    y=['Perc_Revisao', 'Perc_Alteracao'],
                    title='% Revisão e % Alteração por Diretoria',
                    labels={'value': '% ', 'DIRETORIA': 'Diretoria'},
                    barmode='group'
                )
                fig_revisao.update_layout(height=400)
                st.plotly_chart(fig_revisao, use_container_width=True)
            
            with col2:
                # Gráfico de valor por diretoria
                valor_diretoria = df.groupby('DIRETORIA')['Vl.Saldo'].sum() / 1_000_000
                valor_diretoria = valor_diretoria.reset_index()
                
                fig_valor = px.pie(
                    valor_diretoria,
                    values='Vl.Saldo',
                    names='DIRETORIA',
                    title='Distribuição de Valor por Diretoria (R$ MM)'
                )
                fig_valor.update_layout(height=400)
                st.plotly_chart(fig_valor, use_container_width=True)
            
            # Seção de links personalizados e e-mails
            st.header("📧 Geração de E-mails e Links Personalizados")
            
            # Status de conclusão por GC
            st.subheader("📊 Status de Conclusão por GC")
            
            # Calcular estatísticas de cada GC
            status_gcs = []
            for gc in df['GC'].dropna().unique():
                df_gc = df[df['GC'] == gc]
                total_gc = len(df_gc)
                revisados_gc = df_gc['Revisao_Realizada'].sum()
                perc_gc = (revisados_gc / total_gc * 100) if total_gc > 0 else 0
                
                # Verificar se GC tem revisões na sessão atual
                revisoes_sessao = len([k for k, v in st.session_state.dados_revisao.items() 
                                     if v.get('gc') == gc])
                
                status = "🟢 Completo" if perc_gc >= 100 else "🟡 Em Andamento" if perc_gc > 0 else "🔴 Pendente"
                
                status_gcs.append({
                    'GC': gc,
                    'Status': status,
                    'Revisados': f"{revisados_gc}/{total_gc}",
                    'Progresso': f"{perc_gc:.1f}%",
                    'Revisões Sessão': revisoes_sessao
                })
            
            df_status = pd.DataFrame(status_gcs)
            
            # Mostrar em colunas para melhor visualização
            col1, col2 = st.columns([2, 1])
            
            with col1:
                st.dataframe(
                    df_status,
                    column_config={
                        "Status": st.column_config.TextColumn("Status"),
                        "Progresso": st.column_config.ProgressColumn(
                            "% Progresso",
                            help="Percentual de pedidos revisados",
                            min_value=0,
                            max_value=100
                        )
                    },
                    use_container_width=True,
                    hide_index=True
                )
            
            with col2:
                # Resumo geral
                total_gcs = len(status_gcs)
                completos = len([s for s in status_gcs if s['Status'] == '🟢 Completo'])
                em_andamento = len([s for s in status_gcs if s['Status'] == '🟡 Em Andamento'])
                pendentes = len([s for s in status_gcs if s['Status'] == '🔴 Pendente'])
                
                st.metric("Total GCs", total_gcs)
                st.metric("✅ Completos", completos)
                st.metric("🟡 Em Andamento", em_andamento)
                st.metric("🔴 Pendentes", pendentes)
            
            st.markdown("---")
            
            links_gc = generate_personalized_links(df, mes_selecionado, ano_selecionado)
            
            # Tabela com informações dos GCs e ações
            dados_links = []
            for gc, info in links_gc.items():
                revisados = df[(df['GC'] == gc) & (df['Revisao_Realizada'] == True)].shape[0]
                total_gc = df[df['GC'] == gc].shape[0]
                perc_rev = (revisados / total_gc * 100) if total_gc > 0 else 0
                
                dados_links.append({
                    'GC': gc,
                    'Total_Pedidos': info['pedidos'],
                    'Valor_MM': f"R$ {info['valor']:.0f}",
                    'Volume': f"{info['volume']:,.0f}",
                    'Revisados': f"{revisados}/{total_gc}",
                    'Perc_Revisao': f"{perc_rev:.1f}%",
                    'Link': info['link']
                })
            
            df_links = pd.DataFrame(dados_links)
            
            # Mostrar tabela com links
            st.subheader("🔗 Links e Informações por GC")
            st.dataframe(
                df_links,
                column_config={
                    "Link": st.column_config.LinkColumn(
                        "Link Personalizado",
                        help="Link direto para o GC fazer a revisão"
                    ),
                    "GC": "Gerente Comercial",
                    "Total_Pedidos": "Qtd. Pedidos",
                    "Valor_MM": "Valor (MM)",
                    "Volume": "Volume Total",
                    "Revisados": "Revisados",
                    "Perc_Revisao": "% Revisão"
                },
                use_container_width=True,
                hide_index=True
            )
            
            # Seção para geração de e-mails
            st.subheader("📧 Geração de E-mails Personalizados")
            
            col1, col2 = st.columns([2, 1])
            
            with col1:
                gc_para_email = st.selectbox(
                    "Selecione o GC para gerar e-mail:",
                    list(links_gc.keys()),
                    key="gc_email_select"
                )
                
                email_gc = st.text_input(
                    "E-mail do GC:",
                    placeholder="exemplo@empresa.com",
                    key="email_input"
                )
            
            with col2:
                st.write("")
                st.write("")
                if st.button("📧 Gerar E-mail no Outlook", type="primary"):
                    if email_gc and gc_para_email:
                        info_gc = links_gc[gc_para_email]
                        assunto, corpo = gerar_email_outlook(gc_para_email, info_gc, mes_selecionado, ano_selecionado)
                        
                        sucesso = abrir_outlook_com_email(email_gc, assunto, corpo)
                        if sucesso:
                            st.success("✅ E-mail aberto no Outlook! Revise e envie.")
                        else:
                            st.error("❌ Erro ao abrir Outlook. Verifique se está instalado.")
                    else:
                        st.warning("⚠️ Selecione um GC e informe o e-mail.")
            
            # Botão para gerar todos os e-mails
            st.subheader("📬 Gerar Todos os E-mails")
            
            col1, col2 = st.columns([3, 1])
            with col1:
                st.write("Gera e-mails para todos os GCs de uma vez (abrirá várias janelas do Outlook)")
                
            with col2:
                if st.button("📬 Gerar Todos", type="secondary"):
                    st.info("💡 Funcionalidade disponível quando você fornecer uma lista de e-mails dos GCs")
                    # Aqui você pode implementar a lógica para carregar e-mails de uma planilha
                    # ou banco de dados e gerar todos de uma vez
            
            # Preview do e-mail
            if gc_para_email:
                with st.expander("👀 Visualizar Preview do E-mail"):
                    info_gc = links_gc[gc_para_email]
                    assunto, corpo = gerar_email_outlook(gc_para_email, info_gc, mes_selecionado, ano_selecionado)
                    
                    st.write("**Assunto:**")
                    st.code(assunto)
                    
                    st.write("**Corpo do E-mail:**")
                    st.text_area("Corpo do E-mail", value=corpo, height=400, disabled=True, label_visibility="collapsed")
            
            # Detalhamento por grupo para cada GC
            st.header("📊 Detalhamento por GC e Grupo")
            
            gc_detalhes = st.selectbox(
                "Selecione um GC para ver detalhes:",
                ["Selecione..."] + list(links_gc.keys()),
                key="gc_detalhes_select"
            )
            
            if gc_detalhes != "Selecione...":
                info_gc = links_gc[gc_detalhes]
                
                col1, col2 = st.columns(2)
                
                with col1:
                    st.subheader(f"📋 Resumo - {gc_detalhes}")
                    st.metric("Pedidos", info_gc['pedidos'])
                    st.metric("Valor", f"R$ {info_gc['valor']:.0f}M")
                    st.metric("Volume", f"{info_gc['volume']:,.0f}")
                
                with col2:
                    st.subheader("📦 Por Grupo de Produto")
                    st.dataframe(
                        info_gc['grupos'],
                        column_config={
                            "Grupo": "Grupo de Produto",
                            "Qtd_Pedidos": "Qtd. Pedidos",
                            "Valor_MM": "Valor (R$ MM)",
                            "Volume_Total": "Volume Total"
                        },
                        use_container_width=True,
                        hide_index=True
                    )
                
                # Gráfico específico do GC
                fig_gc = px.bar(
                    info_gc['grupos'],
                    x='Grupo',
                    y='Valor_MM',
                    title=f'Valor por Grupo - {gc_detalhes}',
                    labels={'Valor_MM': 'Valor (R$ MM)', 'Grupo': 'Grupo de Produto'}
                )
                fig_gc.update_xaxes(tickangle=45)
                st.plotly_chart(fig_gc, use_container_width=True)
            
            # Resumo de revisões realizadas
            if st.session_state.dados_revisao:
                st.header("📋 Resumo das Revisões Realizadas")
                
                revisoes_df = []
                for revisao_key, dados in st.session_state.dados_revisao.items():
                    # Determinar ordem e material baseado no formato da chave
                    if '_' in revisao_key and 'ordem' in dados and 'material' in dados:
                        # Formato novo: ordem_material
                        ordem = dados['ordem']
                        material = dados['material']
                        ordem_info = df[(df['Ord.venda'] == ordem) & (df['Material'] == material)]
                    else:
                        # Formato antigo: só ordem (compatibilidade)
                        ordem = revisao_key if isinstance(revisao_key, (int, str)) else dados.get('ordem', revisao_key)
                        material = 'N/A'
                        ordem_info = df[df['Ord.venda'] == ordem]
                    
                    # Buscar informações da ordem/material no dataframe
                    if not ordem_info.empty:
                        cliente = ordem_info['Nome Emissor'].iloc[0]
                        grupo = ordem_info['Grupo'].iloc[0]
                        produto = ordem_info['Desc. Material'].iloc[0]
                    else:
                        cliente = 'N/A'
                        grupo = 'N/A'
                        produto = 'N/A'
                    
                    revisoes_df.append({
                        'Ordem': ordem,
                        'Material': material if material != 'sem_material' else 'N/A',
                        'GC': dados['gc'],
                        'Cliente': cliente,
                        'Produto': produto,
                        'Grupo': grupo,
                        'Data_Revisao': pd.to_datetime(dados['data_revisao']).strftime('%d/%m/%Y %H:%M'),
                        'Acao': 'Data Alterada' if dados.get('nova_data') else 'Confirmado',
                        'Nova_Data': pd.to_datetime(dados['nova_data']).strftime('%d/%m/%Y') if dados.get('nova_data') else '-',
                        'Justificativa': dados.get('justificativa', '-')
                    })
                
                if revisoes_df:
                    df_revisoes = pd.DataFrame(revisoes_df)
                    
                    # Filtros para revisões
                    col1, col2 = st.columns(2)
                    with col1:
                        gc_filtro_rev = st.selectbox(
                            "Filtrar por GC:",
                            ["Todos"] + sorted(df_revisoes['GC'].unique().tolist()),
                            key="gc_filtro_revisoes"
                        )
                    with col2:
                        acao_filtro_rev = st.selectbox(
                            "Filtrar por Ação:",
                            ["Todas", "Confirmado", "Data Alterada"],
                            key="acao_filtro_revisoes"
                        )
                    
                    # Aplicar filtros
                    df_rev_filtrado = df_revisoes.copy()
                    if gc_filtro_rev != "Todos":
                        df_rev_filtrado = df_rev_filtrado[df_rev_filtrado['GC'] == gc_filtro_rev]
                    if acao_filtro_rev != "Todas":
                        df_rev_filtrado = df_rev_filtrado[df_rev_filtrado['Acao'] == acao_filtro_rev]
                    
                    st.dataframe(df_rev_filtrado, use_container_width=True, hide_index=True)
                    
                    # Botão para exportar revisões
                    if st.button("📊 Exportar Revisões (CSV)"):
                        csv = df_rev_filtrado.to_csv(index=False)
                        st.download_button(
                            label="💾 Baixar CSV",
                            data=csv,
                            file_name=f"revisoes_carteira_{mes_selecionado}_{ano_selecionado}.csv",
                            mime="text/csv"
                        )
        
        else:
            # Tela inicial
            st.info("👆 Faça upload do arquivo Excel da carteira na barra lateral para começar")
            
            st.markdown(f"""
            ### 📋 Sistema de Revisão de Carteira - {calendar.month_name[mes_trabalho]}/{ano_trabalho}
            
            **🎯 Funcionalidades:**
            
            **1. Dashboard Principal (Admin):**
            - Upload do arquivo Excel da carteira
            - Filtro automático por mês de trabalho (coluna `Revisão Data Faturamento`)
            - Geração de links personalizados para cada GC
            - Criação automática de e-mails via Outlook
            - Métricas em tempo real de revisão
            
            **2. Links Personalizados (GCs):**
            - Acesso direto com link único e seguro
            - Visualização da carteira filtrada por mês
            - Resumo por grupo de produtos
            - Duas ações: ✅ Confirmar ou 📅 Alterar data
            
            **3. E-mails Automáticos:**
            - Geração automática de e-mail personalizado
            - Resumo detalhado por grupo de produto
            - Link direto para revisão
            - Abertura automática no Outlook
            
            **4. Métricas Acompanhadas:**
            - % de pedidos revisados
            - % de pedidos com data alterada
            - Valor e volume por diretoria e grupo
            - Controle individual por GC
            
            **📅 Lógica de Mês de Trabalho:**
            - Julho: trabalha Agosto (xx/08/2025)
            - Agosto: trabalha Setembro (xx/09/2025)
            - E assim por diante...
            
            **📧 Processo de E-mail:**
            1. Selecione o GC na lista
            2. Informe o e-mail do gerente
            3. Clique em "Gerar E-mail no Outlook"
            4. Revise o e-mail e clique em enviar
            """)

if __name__ == "__main__":
    main()
