import json
import os
import time
import requests

BASE_API_URL = "https://generativelanguage.googleapis.com/v1beta"


def _fallback_heuristico(mensagem: str) -> dict:
    """Classificador determinístico usado se nenhuma API Key estiver configurada ou houver falha."""
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


def _descobrir_modelo_ativo(chave: str) -> str:
    """Consulta a API REST /models e seleciona o melhor modelo Gemini Flash disponível para a chave."""
    resp = requests.get(f"{BASE_API_URL}/models", params={"key": chave}, timeout=10)
    resp.raise_for_status()

    modelos = resp.json().get("models", [])
    bloqueados = ("embedding", "imagen", "veo", "tts", "audio", "image", "robotics", "computer-use", "deep-research")

    candidatos = []
    for m in modelos:
        nome = m.get("name", "")
        metodos = m.get("supportedGenerationMethods", [])
        nome_lower = nome.lower()

        if (
            "generateContent" in metodos
            and "gemini" in nome_lower
            and not any(b in nome_lower for b in bloqueados)
        ):
            is_flash = 1 if "flash" in nome_lower else 0
            is_estavel = 0 if ("exp" in nome_lower or "preview" in nome_lower) else 1
            is_padrao = 0 if "lite" in nome_lower else 1
            candidatos.append((is_flash, is_estavel, is_padrao, nome))

    if not candidatos:
        raise ValueError("Nenhum modelo Gemini compatível com generateContent encontrado para esta API Key.")

    candidatos.sort(reverse=True)
    return candidatos[0][3]


def classificar_ticket(mensagem: str, api_key: str | None = None) -> dict:
    """Envia a mensagem do cliente para a API REST de LLM e retorna JSON estruturado + telemetria HTTP."""
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

    endpoint_atual = f"{BASE_API_URL}/models"

    try:
        modelo_recurso = _descobrir_modelo_ativo(chave)
        endpoint_atual = f"{BASE_API_URL}/{modelo_recurso}:generateContent"

        response = requests.post(
            endpoint_atual,
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
                "modo": f"API REST {modelo_recurso} (Live)",
                "status_http": response.status_code,
                "latencia_ms": latencia_ms,
                "endpoint": endpoint_atual,
            },
        }

    except Exception as exc:
        latencia_ms = round((time.perf_counter() - inicio) * 1000, 1)
        resp_erro = getattr(exc, "response", None)
        status_http = getattr(resp_erro, "status_code", 500)
        detalhe = ""
        if resp_erro is not None:
            try:
                detalhe = f" — {resp_erro.json().get('error', {}).get('message', '')[:120]}"
            except Exception:
                detalhe = f" — {resp_erro.text[:120]}"

        resultado = _fallback_heuristico(mensagem)
        return {
            "dados": resultado,
            "telemetria": {
                "modo": f"Fallback automático ({type(exc).__name__}{detalhe})",
                "status_http": status_http,
                "latencia_ms": latencia_ms,
                "endpoint": endpoint_atual,
            },
        }
