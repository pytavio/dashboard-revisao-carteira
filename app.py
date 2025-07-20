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

# Função para formatação de valores em milhões
def format_valor_milhoes(valor):
    """Formata valor em milhões com 1 casa decimal (            # Informação sobre sistema de e-mails local
            st.info("📧 **Para envio de e-mails:** Use o arquivo `outlook.py` separado para disparar e-mails automaticamente com integração total ao Outlook corporativo"): 10,2M)"""
    if pd.isna(valor) or valor == 0:
        return "0,0M"
    
    valor_mm = valor / 1_000_000
    return f"{valor_mm:,.1f}M".replace(',', 'X').replace('.', ',').replace('X', '.')

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
    if '1ª.DT.DIV.REM' in df.columns:
        df['Data_Trabalho'] = pd.to_datetime(df['1ª.DT.DIV.REM'], errors='coerce')
        
        # Filtrar pelo mês e ano
        mask = (df['Data_Trabalho'].dt.month == mes) & (df['Data_Trabalho'].dt.year == ano)
        return df[mask].copy()
    
    return df

# Função para gerar hash único do GC
def generate_gc_hash(gc_name, mes, ano):
    """Gera um hash único para o GC para criar link personalizado"""
    unique_string = f"{gc_name}_{mes}_{ano}"
    return hashlib.md5(unique_string.encode()).hexdigest()[:10]

# Função para carregar dados
@st.cache_data
def load_data(uploaded_file):
    """Carrega e processa os dados do Excel"""
    try:
        df = pd.read_excel(uploaded_file)
        
        # Limpeza e tratamento dos dados
        if 'Vl.Saldo' in df.columns:
            df['Vl.Saldo'] = pd.to_numeric(df['Vl.Saldo'].astype(str).str.replace('.', '').str.replace(',', '.'), errors='coerce')
        
        if 'Saldo' in df.columns:
            df['Saldo'] = pd.to_numeric(df['Saldo'].astype(str).str.replace('.', '').str.replace(',', '.'), errors='coerce')
        
        # Converter data de entrega original
        if 'Dt. Dej. Rem.' in df.columns:
            df['Dt. Dej. Rem.'] = pd.to_datetime(df['Dt. Dej. Rem.'], format='%d/%m/%Y', errors='coerce')
        
        # Converter data de trabalho (1ª.DT.DIV.REM)
        if '1ª.DT.DIV.REM' in df.columns:
            df['Data_Trabalho'] = pd.to_datetime(df['1ª.DT.DIV.REM'], errors='coerce')
        
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
    
    for ordem, revisao_data in st.session_state.dados_revisao.items():
        mask = df_updated['Ord.venda'] == ordem
        if mask.any():
            df_updated.loc[mask, 'Revisao_Realizada'] = True
            df_updated.loc[mask, 'Data_Revisao'] = pd.to_datetime(revisao_data['data_revisao'])
            df_updated.loc[mask, 'Revisado_Por'] = revisao_data['gc']
            
            if revisao_data['nova_data']:
                df_updated.loc[mask, 'Data_Original_Alterada'] = True
                df_updated.loc[mask, 'Nova_Data_Entrega'] = pd.to_datetime(revisao_data['nova_data'])
    
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
    resumo['Valor_MM'] = resumo['Valor_Total'].apply(format_valor_milhoes)
    resumo = resumo.reset_index()
    
    return resumo

# Função para gerar links personalizados
def generate_personalized_links(df, mes, ano):
    """Gera links personalizados para cada GC"""
    gcs = df['GC'].dropna().unique()
    base_url = "https://seu-app-streamlit.com"  # Substitua pela URL real
    mes_nome = calendar.month_name[mes]
    
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
        
        link = f"{base_url}?gc={urllib.parse.quote(gc)}&hash={gc_hash}&mes={mes}&ano={ano}"
        links[gc] = {
            'link': link,
            'hash': gc_hash,
            'pedidos': pedidos_gc,
            'valor': valor_gc,
            'volume': volume_gc,
            'grupos': resumo_grupos,
            'mes_nome': mes_nome,
            'ano': ano
        }
    
    return links

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
        valor_gc_formatado = format_valor_milhoes(df_gc['Vl.Saldo'].sum())
        st.metric("Valor Total", valor_gc_formatado)
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
            "Valor_MM": "Valor",
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
        
        with st.container():
            col1, col2, col3 = st.columns([2, 2, 1])
            
            with col1:
                st.write(f"**Ordem:** {ordem}")
                st.write(f"**Cliente:** {row['Nome Emissor']}")
                st.write(f"**Produto:** {row['Desc. Material']}")
                st.write(f"**Valor:** {format_valor_milhoes(row['Vl.Saldo'])}")
            
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
                    if st.button("✅ OK", key=f"check_{ordem}", help="Data está correta"):
                        st.session_state.dados_revisao[ordem] = {
                            'gc': gc_selecionado,
                            'data_revisao': datetime.now().isoformat(),
                            'nova_data': None,
                            'acao': 'check'
                        }
                        st.rerun()
                
                with col_rev:
                    if st.button("📅 Revisar", key=f"rev_{ordem}", help="Alterar data"):
                        st.session_state[f'revisar_{ordem}'] = True
                        st.rerun()
        
        # Formulário para alterar data (aparece quando clica em Revisar)
        if st.session_state.get(f'revisar_{ordem}', False):
            with st.form(f"form_data_{ordem}"):
                st.write("**Alterar Data de Entrega:**")
                col1, col2 = st.columns(2)
                
                with col1:
                    nova_data = st.date_input(
                        "Nova Data de Entrega",
                        value=row['Data_Trabalho'].date() if pd.notna(row['Data_Trabalho']) else date.today(),
                        key=f"data_{ordem}"
                    )
                
                with col2:
                    justificativa = st.text_input(
                        "Justificativa (opcional)",
                        key=f"just_{ordem}"
                    )
                
                col_save, col_cancel = st.columns(2)
                with col_save:
                    if st.form_submit_button("💾 Salvar"):
                        st.session_state.dados_revisao[ordem] = {
                            'gc': gc_selecionado,
                            'data_revisao': datetime.now().isoformat(),
                            'nova_data': nova_data.isoformat(),
                            'justificativa': justificativa,
                            'acao': 'revisao'
                        }
                        st.session_state[f'revisar_{ordem}'] = False
                        st.success("Data alterada com sucesso!")
                        st.rerun()
                
                with col_cancel:
                    if st.form_submit_button("❌ Cancelar"):
                        st.session_state[f'revisar_{ordem}'] = False
                        st.rerun()
        
        st.markdown("---")

# Interface principal
def main():
    # Verificar se é acesso via link personalizado
    query_params = st.query_params
    gc_from_url = query_params.get("gc", None)
    hash_from_url = query_params.get("hash", None)
    mes_from_url = int(query_params.get("mes", 0)) if query_params.get("mes") else None
    ano_from_url = int(query_params.get("ano", 0)) if query_params.get("ano") else None
    
    if gc_from_url and hash_from_url and mes_from_url and ano_from_url:
        # Modo formulário para GC específico
        mes_nome = calendar.month_name[mes_from_url]
        st.title(f"📋 Revisão de Carteira - {gc_from_url}")
        st.caption(f"Período: {mes_nome}/{ano_from_url}")
        
        # Verificar se há dados carregados
        if st.session_state.df_original is None:
            st.error("⚠️ Dados não encontrados. Entre em contato com o administrador.")
            st.stop()
        
        # Verificar hash de segurança
        expected_hash = generate_gc_hash(gc_from_url, mes_from_url, ano_from_url)
        if hash_from_url != expected_hash:
            st.error("🔒 Link inválido ou expirado.")
            st.stop()
        
        # Filtrar por mês de trabalho e aplicar revisões
        df_mes = filtrar_por_mes_trabalho(st.session_state.df_original, mes_from_url, ano_from_url)
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
                    
                    # Filtrar por mês de trabalho
                    df_mes = filtrar_por_mes_trabalho(df, mes_selecionado, ano_selecionado)
                    
                    # Aplicar revisões existentes
                    df_mes = apply_revisoes_to_dataframe(df_mes)
                    
                    st.success(f"✅ Arquivo carregado")
                    st.info(f"📊 {len(df):,} registros totais")
                    st.info(f"📅 {len(df_mes):,} registros para {calendar.month_name[mes_selecionado]}/{ano_selecionado}")
                    
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
                    
                    # Alerta sobre persistência
                    st.warning("⚠️ **IMPORTANTE**: As revisões não persistem entre sessões. Use 'Salvar Revisões' regularmente!")
                    
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
                valor_formatado = format_valor_milhoes(metricas_geral['total_valor'] * 1_000_000)
                st.metric("Valor Total", valor_formatado)
            
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
                    valor_filtrado = format_valor_milhoes(metricas['total_valor'] * 1_000_000)
                    valor_delta = format_valor_milhoes((metricas['total_valor'] - metricas_geral['total_valor']) * 1_000_000)
                    st.metric("Valor Filtrado", valor_filtrado, valor_delta)
                
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
            credito_stats['Valor_MM'] = credito_stats['Valor_Total'].apply(format_valor_milhoes)
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
                        "Valor_MM": "Valor",
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
                    title='Distribuição de Valor por Status de Crédito',
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
                    title='Distribuição de Valor por Diretoria'
                )
                fig_valor.update_layout(height=400)
                st.plotly_chart(fig_valor, use_container_width=True)
            
            # Seção de links personalizados
            st.header("🔗 Links Personalizados para GCs")
            
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
                    'Valor_MM': format_valor_milhoes(info['valor']),
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
            
            # Informação sobre sistema de e-mails local
            st.info("� **Para envio de e-mails:** Use o sistema local `outlook.py` para disparar e-mails automaticamente com integração total ao Outlook corporativo")
            
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
                    st.metric("Valor", f"R$ {info_gc['valor']:.2f}M")
                    st.metric("Volume", f"{info_gc['volume']:,.0f}")
                
                with col2:
                    st.subheader("📦 Por Grupo de Produto")
                    st.dataframe(
                        info_gc['grupos'],
                        column_config={
                            "Grupo": "Grupo de Produto",
                            "Qtd_Pedidos": "Qtd. Pedidos",
                            "Valor_MM": "Valor",
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
                    labels={'Valor_MM': 'Valor', 'Grupo': 'Grupo de Produto'}
                )
                fig_gc.update_xaxes(tickangle=45)
                st.plotly_chart(fig_gc, use_container_width=True)
            
            # Resumo de revisões realizadas
            if st.session_state.dados_revisao:
                st.header("📋 Resumo das Revisões Realizadas")
                
                revisoes_df = []
                for ordem, dados in st.session_state.dados_revisao.items():
                    # Buscar informações da ordem no dataframe
                    ordem_info = df[df['Ord.venda'] == ordem]
                    cliente = ordem_info['Nome Emissor'].iloc[0] if not ordem_info.empty else 'N/A'
                    grupo = ordem_info['Grupo'].iloc[0] if not ordem_info.empty else 'N/A'
                    
                    revisoes_df.append({
                        'Ordem': ordem,
                        'GC': dados['gc'],
                        'Cliente': cliente,
                        'Grupo': grupo,
                        'Data_Revisao': pd.to_datetime(dados['data_revisao']).strftime('%d/%m/%Y %H:%M'),
                        'Acao': 'Data Alterada' if dados['nova_data'] else 'Confirmado',
                        'Nova_Data': pd.to_datetime(dados['nova_data']).strftime('%d/%m/%Y') if dados['nova_data'] else '-',
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
            - Filtro automático por mês de trabalho (coluna `1ª.DT.DIV.REM`)
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
