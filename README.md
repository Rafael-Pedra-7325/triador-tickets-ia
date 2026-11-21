[![Live Demo](https://img.shields.io/badge/Live_Demo-Streamlit-FF4B4B?style=for-the-badge&logo=streamlit&logoColor=white)](https://api-health-monitor-ia.streamlit.app/)
# 🎯 Triador Inteligente de Tickets de Atendimento (IA + SQL)

Sistema full-stack em Python para triagem automatizada de mensagens de clientes utilizando **Inteligência Artificial via API REST**, persistência relacional em **SQL (SQLite)** e painel operacional interativo em **Streamlit**.

## 💡 Dor Real Resolvida
Equipes de atendimento e operações recebem mensagens não estruturadas em alto volume e perdem tempo lendo, classificando e priorizando chamados manualmente. Esta aplicação transforma texto livre em dados estruturados (categoria, urgência, sentimento, resumo da dor real e sugestão de resposta) e organiza a fila via consultas SQL.

## 🛠️ Tecnologias Utilizadas
- **Python 3**: lógica da aplicação e telemetria de latência.
- **API REST (`requests` + JSON)**: integração direta HTTP POST com LLM (Gemini 2.5 Flash) com fallback determinístico automático.
- **SQL (SQLite)**: modelagem relacional (`DDL`), inserção e atualização de status (`DML`) e filtros/agregações com `WHERE` e `GROUP BY` (`DQL`).
- **Streamlit & Pandas**: interface interativa com exemplos em 1 clique e inspeção transparente das queries SQL e payloads JSON executados.

## 🚀 Como Executar Localmente

```bash
git clone [https://github.com/Rafael-Pedra-7325/triador-tickets-ia.git](https://github.com/Rafael-Pedra-7325/triador-tickets-ia.git)
cd triador-tickets-ia
pip install -r requirements.txt
streamlit run app.py
