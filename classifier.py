import json
import os
import time
import requests


GEMINI_ENDPOINT = (
    "https://generativelanguage.googleapis.com/v1beta/models/"
    "gemini-2.5-flash:generateContent"
)


def _fallback_heuristico(mensagem: str) -> dict:
    """Classificador determinístico usado apenas se nenhuma API Key estiver configurada."""
    texto = mensagem.lower()

    if any(p in texto for p in ["boleto", "fatura", "cobrança", "cobranca", "pagamento", "estorno", "nota fiscal"]):
        categoria = "Financeiro"
    elif any(p in texto for p in ["cancelar", "cancelamento", "encerrar conta", "desistir"]):
        categoria = "Cancelamento"
    elif any(p in texto for p in ["preço", "plano", "licença", "licenca", "contratar", "proposta", "integração"]):
        categoria = "Comercial"
    else:
        categoria = "Suporte Técnico"

    if any(p in texto for p in ["urgente", "bloqueou", "parou", "erro 500", "erro 502", "fora do ar", "duplicada", "cancelar"]):
        urgencia = "Alta"
        sentimento = "Negativo"
    elif any(p in texto for p in ["plano", "contratar", "proposta", "gostaria de saber"]):
        urgencia = "Média"
        sentimento = "Positivo"
    else:
        urgencia = "Baixa"
        sentimento = "Neutro"

    resumo = mensagem.strip()[:110] + ("..." if len(mensagem.strip()) > 110 else "")
    resposta = (
        f"Olá! Recebemos sua solicitação na fila de {categoria} com prioridade {urgencia}. "
        "Nossa equipe já está analisando o caso e retornará em breve."
    )

    return {
        "categoria": categoria,
        "urgencia": urgencia,
        "sentimento": sentimento,
        "resumo": resumo,
        "resposta_sugerida": resposta,
    }


def classificar_ticket(mensagem: str, api_key: str | None = None) -> dict:
    """
    Envia a mensagem do cliente para a API REST de LLM e retorna JSON estruturado + telemetria HTTP.
    """
    chave = (api_key or os.getenv("GEMINI_API_KEY") or "").strip()
    inicio = time.perf_counter()

    if not chave:
        resultado = _fallback_heuristico(mensagem)
        latencia_ms = round((time.perf_counter() - inicio) * 1000, 1)
        return {
            "dados": resultado,
            "telemetria": {
                "modo": "Simulado Local (configure GEMINI_API_KEY para chamada REST real)",
                "status_http": 200,
                "latencia_ms": latencia_ms,
                "endpoint": "local://fallback-heuristico",
            },
        }

    prompt = f"""
    Você é um sistema especialista de triagem de atendimento ao cliente.
    Analise a mensagem abaixo e retorne APENAS um objeto JSON válido com as chaves exatas:
    - "categoria": escolha estritamente entre "Financeiro", "Suporte Técnico", "Cancelamento" ou "Comercial"
    - "urgencia": escolha estritamente entre "Alta", "Média" ou "Baixa"
    - "sentimento": escolha estritamente entre "Negativo", "Neutro" ou "Positivo"
    - "resumo": frase curta (máximo 15 palavras) descrevendo a dor real do cliente
    - "resposta_sugerida": primeira resposta cordial, empática e objetiva em português (máximo 2 frases)

    Mensagem do cliente:
    \"\"\"{mensagem}\"\"\"
    """

    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.1,
            "responseMimeType": "application/json",
        },
    }

    try:
        response = requests.post(
            GEMINI_ENDPOINT,
            params={"key": chave},
            headers={"Content-Type": "application/json"},
            json=payload,
            timeout=15,
        )
        latencia_ms = round((time.perf_counter() - inicio) * 1000, 1)
        response.raise_for_status()

        body = response.json()
        texto_json = body["candidates"][0]["content"]["parts"][0]["text"]
        parsed = json.loads(texto_json)

        resultado_validado = {
            "categoria": parsed.get("categoria", "Suporte Técnico"),
            "urgencia": parsed.get("urgencia", "Média"),
            "sentimento": parsed.get("sentimento", "Neutro"),
            "resumo": parsed.get("resumo", "Solicitação registrada pelo cliente."),
            "resposta_sugerida": parsed.get(
                "resposta_sugerida",
                "Olá! Recebemos sua mensagem e nossa equipe já está verificando.",
            ),
        }

        return {
            "dados": resultado_validado,
            "telemetria": {
                "modo": "API REST Gemini 2.5 Flash (Live)",
                "status_http": response.status_code,
                "latencia_ms": latencia_ms,
                "endpoint": GEMINI_ENDPOINT,
            },
        }

    except Exception as exc:
        latencia_ms = round((time.perf_counter() - inicio) * 1000, 1)
        resultado = _fallback_heuristico(mensagem)
        return {
            "dados": resultado,
            "telemetria": {
                "modo": f"Fallback automático após erro na API ({type(exc).__name__})",
                "status_http": getattr(getattr(exc, "response", None), "status_code", 500),
                "latencia_ms": latencia_ms,
                "endpoint": GEMINI_ENDPOINT,
            },
        }
