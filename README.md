# 📊 Dashboard de Revisão de Dados

> Sistema web para controle e acompanhamento de processos de revisão colaborativa

[![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.28+-red.svg)](https://streamlit.io/)
[![Status](https://img.shields.io/badge/Status-Ativo-green.svg)]()

## 🎯 **Visão Geral**

Dashboard interativo desenvolvido em Streamlit para gerenciar processos de revisão de dados de forma colaborativa. O sistema oferece uma interface administrativa para controle geral e links personalizados para usuários específicos realizarem suas revisões de forma independente.

### ✨ **Principais Características**

- 🔄 **Processo automatizado** de revisão
- 📧 **Geração de notificações** personalizadas
- 🔗 **Links únicos e seguros** para cada usuário
- 📈 **Métricas em tempo real** de progresso
- 🎨 **Interface moderna** e responsiva
- 💾 **Persistência de dados** durante a sessão
- 📊 **Visualizações interativas**

## 🚀 **Funcionalidades**

### 📋 **Para Administradores**
- **Upload de dados**: Importação de arquivos Excel
- **Filtros dinâmicos**: Por período, categoria e status
- **Dashboard completo**: Métricas, gráficos e análises
- **Geração de links**: Links personalizados para usuários
- **Sistema de notificação**: Integração com aplicativos de e-mail
- **Acompanhamento**: Progresso individual e geral

### 👤 **Para Usuários**
- **Acesso direto**: Via link personalizado
- **Interface simplificada**: Foco na tarefa específica
- **Ações simples**: Confirmar ou revisar dados
- **Resumo personalizado**: Dados específicos do usuário
- **Progresso individual**: Acompanhamento de tarefas realizadas

### 📊 **Análises Disponíveis**
- **Por Status**: Diferentes categorias de dados
- **Por Categoria**: Distribuição e segmentação
- **Por Usuário**: Performance individual
- **Progresso Geral**: Percentual de conclusão
- **Métricas Personalizadas**: Valores e quantidades

## 🛠️ **Tecnologias Utilizadas**

- **[Python 3.8+](https://python.org/)** - Linguagem principal
- **[Streamlit](https://streamlit.io/)** - Framework web interativo
- **[Pandas](https://pandas.pydata.org/)** - Manipulação de dados
- **[Plotly](https://plotly.com/)** - Visualizações interativas
- **[openpyxl](https://openpyxl.readthedocs.io/)** - Leitura de arquivos Excel

## 📦 **Instalação**

### Pré-requisitos
- Python 3.8 ou superior
- Aplicativo de e-mail configurado (opcional)

### 1. Clone o projeto
```bash
git clone https://github.com/usuario/dashboard-revisao-dados.git
cd dashboard-revisao-dados
```

### 2. Instale as dependências
```bash
pip install -r requirements.txt
```

## 🚀 **Como Usar**

### 1. Inicie a aplicação
```bash
streamlit run app.py
```

### 2. Acesse o dashboard
Abra seu navegador em: `http://localhost:8501`

### 3. Workflow básico

1. **📁 Upload**: Carregue arquivo Excel com os dados
2. **🔍 Filtros**: Aplique filtros conforme necessário
3. **📊 Análise**: Visualize métricas e gráficos
4. **🔗 Links**: Gere links para usuários específicos
5. **📧 Notificação**: Envie links via e-mail
6. **📈 Acompanhamento**: Monitore o progresso

## ⚙️ **Configurações**

### URL de Deploy
Para uso em produção, altere a URL base no código:

```python
base_url = "https://sua-aplicacao.streamlit.app"
```

### Personalização
- Filtros podem ser adaptados conforme necessidade
- Métricas são configuráveis via código
- Interface pode ser personalizada com CSS

## 🔒 **Segurança**

- **Links únicos**: Hash baseado em usuário e período
- **Validação**: Verificação de acesso antes de exibir dados
- **Isolamento**: Dados separados por sessão
- **Temporalidade**: Links válidos apenas para período específico

## 📊 **Métricas Padrão**

### KPIs Principais
- **Total de Registros**: Quantidade total de itens
- **Valores**: Somas e médias personalizáveis
- **Progresso**: Percentual de conclusão
- **Performance**: Análise por usuário/categoria

### Visualizações
- **Gráficos de barras**: Comparações por categoria
- **Gráficos de pizza**: Distribuições percentuais
- **Métricas**: Cards com valores principais
- **Tabelas**: Dados detalhados e editáveis

## 🔄 **Arquitetura**

```
Dashboard Principal (Admin)
    ↓
Upload de Dados
    ↓
Processamento e Filtros
    ↓
Geração de Links Personalizados
    ↓
Interface de Usuário (Links)
    ↓
Coleta de Revisões
    ↓
Consolidação e Relatórios
```

## 📁 **Estrutura do Projeto**

```
dashboard-revisao-dados/
├── app.py                 # Aplicação principal
├── requirements.txt       # Dependências Python
├── README.md             # Este arquivo
└── .streamlit/           # Configurações (opcional)
    └── config.toml
```

## 🚀 **Deploy**

### Streamlit Cloud
1. Faça push para um repositório público no GitHub
2. Conecte com Streamlit Cloud
3. Configure as variáveis de ambiente necessárias
4. Deploy automático a cada commit

### Outras opções
- **Heroku**: Para maior controle de recursos
- **Docker**: Para ambientes containerizados
- **Local**: Para uso interno em rede local

## 📝 **Contribuição**

Este é um projeto de uso específico, mas contribuições são bem-vindas:

1. Fork o projeto
2. Crie uma branch para sua feature
3. Commit suas mudanças
4. Push para a branch
5. Abra um Pull Request

## 📄 **Licença**

Este projeto está sob licença MIT. Veja o arquivo `LICENSE` para mais detalhes.

## 🆘 **Suporte**

Para dúvidas ou problemas:
- Abra uma issue no GitHub
- Consulte a documentação do Streamlit
- Verifique os logs da aplicação

---

**Dashboard desenvolvido com Streamlit - Framework Python para aplicações web interativas**
