import sqlite3
from datetime import datetime
from pathlib import Path
import pandas as pd

DB_PATH = Path(__file__).parent / "tickets.db"


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """Cria a tabela de tickets (DDL) e popula dados iniciais caso esteja vazia."""
    ddl = """
    CREATE TABLE IF NOT EXISTS tickets (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        cliente TEXT NOT NULL,
        mensagem TEXT NOT NULL,
        categoria TEXT NOT NULL,
        urgencia TEXT NOT NULL,
        sentimento TEXT NOT NULL,
        resumo TEXT NOT NULL,
        resposta_sugerida TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'Aberto',
        criado_em TEXT NOT NULL
    );
    """
    with get_connection() as conn:
        conn.execute(ddl)
        total = conn.execute("SELECT COUNT(*) FROM tickets").fetchone()[0]

        if total == 0:
            exemplos_iniciais = [
                (
                    "Mariana Costa",
                    "Meu boleto venceu ontem e hoje o sistema bloqueou o acesso da equipe inteira. Preciso liberar urgente!",
                    "Financeiro",
                    "Alta",
                    "Negativo",
                    "Bloqueio de acesso por atraso de 1 dia no pagamento do boleto.",
                    "Olá, Mariana! Entendemos a urgência. Já encaminhamos seu caso com prioridade ao time financeiro para liberação provisória e envio da segunda via atualizada.",
                    "Aberto",
                    "2026-11-18 09:15:00",
                ),
                (
                    "Carlos Eduardo",
                    "A API de webhooks parou de enviar notificações desde as 8h da manhã, retornando erro 502.",
                    "Suporte Técnico",
                    "Alta",
                    "Negativo",
                    "Falha na entrega de webhooks com retorno HTTP 502 desde 08h00.",
                    "Olá, Carlos! Identificamos sua ocorrência técnica (HTTP 502 nos webhooks) e já acionamos a engenharia de plantão para estabilizar o serviço.",
                    "Aberto",
                    "2026-11-18 10:02:00",
                ),
                (
                    "Fernanda Lima",
                    "Gostaria de cancelar minha assinatura atual pois reduzimos o tamanho da operação este mês.",
                    "Cancelamento",
                    "Alta",
                    "Neutro",
                    "Solicitação de cancelamento de assinatura por redução operacional.",
                    "Olá, Fernanda! Lamentamos saber disso. Antes de prosseguir com o cancelamento, podemos apresentar um plano enxuto adequado ao seu momento atual?",
                    "Aberto",
                    "2026-11-18 11:30:00",
                ),
                (
                    "João Pedro",
                    "Vocês têm integração nativa com HubSpot e WhatsApp Business API no plano Pro?",
                    "Comercial",
                    "Média",
                    "Positivo",
                    "Dúvida sobre disponibilidade de integração com HubSpot e WhatsApp no plano Pro.",
                    "Olá, João! Sim, o plano Pro contempla integração nativa com WhatsApp Business API e conectores para HubSpot. Posso agendar uma demonstração rápida?",
                    "Resolvido",
                    "2026-11-18 14:10:00",
                ),
                (
                    "Beatriz Almeida",
                    "Preciso alterar o e-mail do administrador principal da nossa conta.",
                    "Suporte Técnico",
                    "Baixa",
                    "Neutro",
                    "Solicitação de troca de e-mail do usuário administrador.",
                    "Olá, Beatriz! Você pode alterar o e-mail do administrador em Configurações > Usuários, ou confirmar por aqui o novo endereço para ajustarmos.",
                    "Resolvido",
                    "2026-11-19 08:45:00",
                ),
                (
                    "Rafael Mendes",
                    "Fui cobrado duas vezes na fatura do cartão este mês. Preciso do estorno.",
                    "Financeiro",
                    "Alta",
                    "Negativo",
                    "Cobrança duplicada identificada na fatura do cartão de crédito.",
                    "Olá, Rafael! Pedimos desculpas pelo transtorno. Já sinalizamos a cobrança duplicada ao financeiro para processar o estorno imediatamente.",
                    "Aberto",
                    "2026-11-19 09:50:00",
                ),
                (
                    "Lucas Rocha",
                    "Como faço para exportar os relatórios de atendimento em formato CSV?",
                    "Suporte Técnico",
                    "Baixa",
                    "Neutro",
                    "Dúvida operacional sobre exportação de relatórios em CSV.",
                    "Olá, Lucas! Acesse Relatórios > Histórico de Atendimentos e clique no botão 'Exportar CSV' no canto superior direito.",
                    "Resolvido",
                    "2026-11-19 13:20:00",
                ),
                (
                    "Amanda Souza",
                    "Estamos avaliando contratar 50 licenças para o próximo trimestre. Conseguem proposta personalizada?",
                    "Comercial",
                    "Média",
                    "Positivo",
                    "Cotação comercial para aquisição de 50 licenças corporativas.",
                    "Olá, Amanda! Com certeza. Um especialista de contas corporativas entrará em contato hoje com uma proposta sob medida para 50 licenças.",
                    "Aberto",
                    "2026-11-19 16:05:00",
                ),
            ]
            conn.executemany(
                """
                INSERT INTO tickets (
                    cliente, mensagem, categoria, urgencia, sentimento,
                    resumo, resposta_sugerida, status, criado_em
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                exemplos_iniciais,
            )


def inserir_ticket(
    cliente: str,
    mensagem: str,
    categoria: str,
    urgencia: str,
    sentimento: str,
    resumo: str,
    resposta_sugerida: str,
) -> tuple[int, str]:
    """Insere um novo ticket classificado (DML) e retorna o ID e a query executada."""
    agora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    sql = """
    INSERT INTO tickets (
        cliente, mensagem, categoria, urgencia, sentimento,
        resumo, resposta_sugerida, status, criado_em
    ) VALUES (?, ?, ?, ?, ?, ?, ?, 'Aberto', ?)
    """
    with get_connection() as conn:
        cursor = conn.execute(
            sql,
            (
                cliente.strip() or "Cliente Anônimo",
                mensagem.strip(),
                categoria,
                urgencia,
                sentimento,
                resumo,
                resposta_sugerida,
                agora,
            ),
        )
        ticket_id = cursor.lastrowid

    sql_formatado = (
        f"INSERT INTO tickets (cliente, categoria, urgencia, sentimento, status, criado_em)\n"
        f"VALUES ('{cliente}', '{categoria}', '{urgencia}', '{sentimento}', 'Aberto', '{agora}');"
    )
    return ticket_id, sql_formatado


def listar_tickets(
    urgencia: str = "Todas", status: str = "Todos"
) -> tuple[pd.DataFrame, str]:
    """Consulta tickets com filtros dinâmicos (DQL)."""
    condicoes = []
    params = []

    if urgencia != "Todas":
        condicoes.append("urgencia = ?")
        params.append(urgencia)
    if status != "Todos":
        condicoes.append("status = ?")
        params.append(status)

    where_clause = f"WHERE {' AND '.join(condicoes)}" if condicoes else ""
    sql = f"""
    SELECT id, criado_em, cliente, categoria, urgencia, sentimento, resumo, status, mensagem, resposta_sugerida
    FROM tickets
    {where_clause}
    ORDER BY id DESC
    """
    with get_connection() as conn:
        df = pd.read_sql_query(sql, conn, params=params)

    sql_exibicao = sql.strip()
    for p in params:
        sql_exibicao = sql_exibicao.replace("?", f"'{p}'", 1)

    return df, sql_exibicao


def obter_resumo_sql() -> tuple[pd.DataFrame, str]:
    """Agrega volume de chamados por categoria e urgência via GROUP BY (DQL)."""
    sql = """
    SELECT
        categoria AS Categoria,
        urgencia AS Urgencia,
        COUNT(*) AS Total
    FROM tickets
    GROUP BY categoria, urgencia
    ORDER BY Total DESC;
    """
    with get_connection() as conn:
        df = pd.read_sql_query(sql, conn)
    return df, sql.strip()


def atualizar_status_ticket(ticket_id: int, novo_status: str) -> str:
    """Atualiza o status de um ticket (DML - UPDATE)."""
    sql = "UPDATE tickets SET status = ? WHERE id = ?"
    with get_connection() as conn:
        conn.execute(sql, (novo_status, ticket_id))
    return f"UPDATE tickets SET status = '{novo_status}' WHERE id = {ticket_id};"
