import json
import os
import streamlit as st
from classifier import classificar_ticket
from database import (
    atualizar_status_ticket,
    init_db,
    inserir_ticket,
    listar_tickets,
    obter_resumo_sql,
)

st.set_page_config(
    page_title="Triador Inteligente de Tickets | IA + SQL",
    page_icon="🎯",
    layout="wide",
)

init_db()

EXEMPLOS = {
    "💳 Boleto e Bloqueio": (
        "Patricia Oliveira",
        "Pagamos o boleto ontem à tarde, mas a plataforma continua bloqueada e nossa operação de atendimento está parada!",
    ),
    "⚙️ Erro na API": (
        "Tiago Nascimento",
        "Desde as 14h nossa integração via API REST está recebendo timeout e erro 503 ao tentar consultar pedidos.",
    ),
    "📉 Pedido de Cancelamento": (
        "Renata Vasconcelos",
        "Quero cancelar nossa assinatura ainda hoje porque não estamos conseguindo configurar os fluxos.",
    ),
}


def carregar_exemplo(nome_cliente: str, texto_msg: str) -> None:
    st.session_state["cliente_input"] = nome_cliente
    st.session_state["mensagem_input"] = texto_msg


if "cliente_input" not in st.session_state:
    st.session_state["cliente_input"] = ""
if "mensagem_input" not in st.session_state:
    st.session_state["mensagem_input"] = ""

# Recupera chave de API do Streamlit Secrets ou variável de ambiente (opcional na barra lateral)
api_key_padrao = ""
try:
    api_key_padrao = st.secrets.get("GEMINI_API_KEY", "")
except Exception:
    api_key_padrao = os.getenv("GEMINI_API_KEY", "")

with st.sidebar:
    st.header("⚙️ Configuração da API")
    api_key_usuario = st.text_input(
        "Gemini API Key (opcional)",
        value=api_key_padrao,
        type="password",
        help="Se deixado em branco, o sistema opera em modo simulado local sem falhar.",
    )
    st.markdown("---")
    st.markdown(
        "**Arquitetura do Projeto**\n"
        "- **Back-end:** Python 3\n"
        "- **Integração:** API REST (`requests` + JSON)\n"
        "- **Banco de Dados:** SQLite (DDL, DML, DQL)\n"
        "- **Interface:** Streamlit"
    )

st.title("🎯 Triador Inteligente de Tickets de Atendimento")
st.caption(
    "Classificação automática de chamados com IA via API REST, persistência relacional em SQL e fila priorizada em tempo real."
)

# --- SEÇÃO 1: NOVA TRIAGEM ---
st.subheader("1. Simular Entrada de Novo Chamado")
st.write("Teste com 1 clique usando um exemplo pronto ou digite uma mensagem livre:")

cols_ex = st.columns(3)
for idx, (label, (cli, msg)) in enumerate(EXEMPLOS.items()):
    cols_ex[idx].button(
        label,
        use_container_width=True,
        on_click=carregar_exemplo,
        args=(cli, msg),
    )

with st.form("form_triagem"):
    col_cli, col_msg = st.columns([1, 3])
    cliente = col_cli.text_input("Nome do Cliente", key="cliente_input", placeholder="Ex: Ana Paula")
    mensagem = col_msg.text_area(
        "Mensagem do Cliente",
        key="mensagem_input",
        height=90,
        placeholder="Descreva o problema, dúvida ou solicitação do cliente...",
    )
    enviado = st.form_submit_button("🚀 Classificar com IA e Salvar no SQL", type="primary")

if enviado:
    if not mensagem.strip():
        st.warning("Digite ou selecione uma mensagem de exemplo antes de classificar.")
    else:
        with st.spinner("Consultando API REST de IA e gravando no banco SQL..."):
            resposta_ia = classificar_ticket(mensagem, api_key=api_key_usuario)
            dados = resposta_ia["dados"]
            telemetria = resposta_ia["telemetria"]

            ticket_id, sql_insert = inserir_ticket(
                cliente=cliente,
                mensagem=mensagem,
                categoria=dados["categoria"],
                urgencia=dados["urgencia"],
                sentimento=dados["sentimento"],
                resumo=dados["resumo"],
                resposta_sugerida=dados["resposta_sugerida"],
            )

        st.success(f"Ticket #{ticket_id} classificado e salvo no banco de dados!")

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Categoria", dados["categoria"])
        c2.metric("Urgência", dados["urgencia"])
        c3.metric("Sentimento", dados["sentimento"])
        c4.metric("Latência REST API", f"{telemetria['latencia_ms']} ms")

        st.info(f"**Dor real identificada:** {dados['resumo']}")
        st.success(f"**Sugestão de 1ª resposta:** {dados['resposta_sugerida']}")

        with st.expander("🔍 Por baixo dos panos (Resposta JSON da API REST & SQL INSERT)"):
            st.markdown(f"**Modo de execução:** `{telemetria['modo']}` | **HTTP Status:** `{telemetria['status_http']}`")
            st.code(json.dumps(dados, indent=2, ensure_ascii=False), language="json")
            st.code(sql_insert, language="sql")

st.markdown("---")

# --- SEÇÃO 2: DASHBOARD E FILA SQL ---
st.subheader("2. Fila Operacional e Indicadores (Consultas SQL)")

df_todos, _ = listar_tickets()
total_tickets = len(df_todos)
alta_urgencia = int((df_todos["urgencia"] == "Alta").sum()) if total_tickets else 0
abertos = int((df_todos["status"] == "Aberto").sum()) if total_tickets else 0
resolvidos = int((df_todos["status"] == "Resolvido").sum()) if total_tickets else 0

m1, m2, m3, m4 = st.columns(4)
m1.metric("Total de Chamados", total_tickets)
m2.metric("Urgência Alta", alta_urgencia)
m3.metric("Em Aberto", abertos)
m4.metric("Resolvidos", resolvidos)

col_grafico, col_tabela = st.columns([1, 2])

with col_grafico:
    st.markdown("**Distribuição por Categoria (SQL GROUP BY)**")
    df_agrupado, sql_group = obter_resumo_sql()
    if not df_agrupado.empty:
        chart_data = df_agrupado.groupby("Categoria")["Total"].sum()
        st.bar_chart(chart_data)

with col_tabela:
    f1, f2 = st.columns(2)
    filtro_urg = f1.selectbox("Filtrar por Urgência", ["Todas", "Alta", "Média", "Baixa"])
    filtro_sta = f2.selectbox("Filtrar por Status", ["Todos", "Aberto", "Resolvido"])

    df_filtrado, sql_select = listar_tickets(urgencia=filtro_urg, status=filtro_sta)
    st.dataframe(
        df_filtrado[["id", "criado_em", "cliente", "categoria", "urgencia", "resumo", "status"]],
        use_container_width=True,
        hide_index=True,
    )

    abertos_ids = df_filtrado[df_filtrado["status"] == "Aberto"]["id"].tolist()
    if abertos_ids:
        col_id, col_btn = st.columns([1, 2])
        id_para_resolver = col_id.selectbox("ID do Ticket", abertos_ids, label_visibility="collapsed")
        if col_btn.button("✅ Marcar Ticket como Resolvido (SQL UPDATE)"):
            sql_upd = atualizar_status_ticket(int(id_para_resolver), "Resolvido")
            st.toast(f"Executado: {sql_upd}")
            st.rerun()

with st.expander("🗄️ Ver Queries SQL Executadas nesta Tela (DQL)"):
    st.markdown("**Consulta da Fila Filtrada:**")
    st.code(sql_select, language="sql")
    st.markdown("**Consulta Agregada do Gráfico:**")
    st.code(sql_group, language="sql")
