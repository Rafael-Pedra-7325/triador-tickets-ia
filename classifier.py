import json
import os
import time
import requests

GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta"
GROQ_ENDPOINT = "https://api.groq.com/openai/v1/chat/completions"


def _fallback_heuristico(mensagem: str) -> dict:
    """Classificador determinístico usado se nenhuma API Key estiver configurada ou todas falharem."""
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


def _montar_prompt(mensagem: str) -> str:
    return f"""
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


def _normalizar_saida(parsed: dict) -> dict:
    return {
        "categoria": parsed.get("categoria", "Suporte Técnico"),
        "urgencia": parsed.get("urgencia", "Média"),
        "sentimento": parsed.get("sentimento", "Neutro"),
        "resumo": parsed.get("resumo", "Solicitação registrada pelo cliente."),
        "resposta_sugerida": parsed.get(
            "resposta_sugerida",
            "Olá! Recebemos sua mensagem e nossa equipe já está verificando.",
        ),
    }


def _listar_modelos_gemini(chave: str) -> list[str]:
    """Lista os modelos Gemini compatíveis com generateContent ordenados por maior chance de cota gratuita."""
    resp = requests.get(f"{GEMINI_BASE_URL}/models", params={"key": chave}, timeout=10)
    resp.raise_for_status()

    modelos = resp.json().get("models", [])
    bloqueados = ("embedding", "imagen", "veo", "tts", "audio", "image", "robotics", "computer-use", "deep-research")

    ranqueados = []
    for m in modelos:
        nome = m.get("name", "")
        metodos = m.get("supportedGenerationMethods", [])
        nome_lower = nome.lower()

        if (
            "generateContent" in metodos
            and "gemini" in nome_lower
            and not any(b in nome_lower for b in bloqueados)
        ):
            # Prioriza modelos Flash e Flash-Lite estáveis (maiores limites no Free Tier)
            score = 0
            if "flash" in nome_lower:
                score += 100
            if "lite" in nome_lower:
                score += 30
            if "2.5" in nome_lower:
                score += 20
            elif "2.0" in nome_lower:
                score += 10
            if "exp" in nome_lower or "preview" in nome_lower:
                score -= 25

            ranqueados.append((score, nome))

    ranqueados.sort(reverse=True)
    return [nome for _, nome in ranqueados]


def _chamar_groq(mensagem: str, chave: str, inicio: float) -> dict:
    """Suporte opcional para chaves gratuitas da Groq (prefixo gsk_)."""
    payload = {
        "model": "llama-3.3-70b-versatile",
        "messages": [{"role": "user", "content": _montar_prompt(mensagem)}],
        "temperature": 0.1,
        "response_format": {"type": "json_object"},
    }
    response = requests.post(
        GROQ_ENDPOINT,
        headers={
            "Authorization": f"Bearer {chave}",
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=15,
    )
    latencia_ms = round((time.perf_counter() - inicio) * 1000, 1)
    response.raise_for_status()

    texto_json = response.json()["choices"][0]["message"]["content"]
    dados = _normalizar_saida(json.loads(texto_json))

    return {
        "dados": dados,
        "telemetria": {
            "modo": "API REST Groq llama-3.3-70b-versatile (Live)",
            "status_http": response.status_code,
            "latencia_ms": latencia_ms,
            "endpoint": GROQ_ENDPOINT,
        },
    }


def classificar_ticket(mensagem: str, api_key: str | None = None) -> dict:
    """Envia a mensagem para a API REST de LLM com failover automático entre modelos."""
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

    try:
        # Se o usuário informar uma chave Groq (gsk_...), usa o endpoint OpenAI-compatible da Groq
        if chave.startswith("gsk_"):
            return _chamar_groq(mensagem, chave, inicio)

        candidatos = _listar_modelos_gemini(chave)
        if not candidatos:
            raise ValueError("Nenhum modelo Gemini compatível encontrado para esta chave.")

        payload = {
            "contents": [{"parts": [{"text": _montar_prompt(mensagem)}]}],
            "generationConfig": {
                "temperature": 0.1,
                "responseMimeType": "application/json",
            },
        }

        erros_tentativas = []
        ultimo_status = 500
        ultimo_endpoint = f"{GEMINI_BASE_URL}/models"

        # Tenta até 6 modelos em cascata caso algum retorne 429 (cota zerada) ou 404
        for modelo_recurso in candidatos[:6]:
            ultimo_endpoint = f"{GEMINI_BASE_URL}/{modelo_recurso}:generateContent"
            response = requests.post(
                ultimo_endpoint,
                params={"key": chave},
                headers={"Content-Type": "application/json"},
                json=payload,
                timeout=15,
            )
            ultimo_status = response.status_code

            if response.status_code == 200:
                latencia_ms = round((time.perf_counter() - inicio) * 1000, 1)
                texto_json = response.json()["candidates"][0]["content"]["parts"][0]["text"]
                dados = _normalizar_saida(json.loads(texto_json))

                return {
                    "dados": dados,
                    "telemetria": {
                        "modo": f"API REST {modelo_recurso} (Live)",
                        "status_http": 200,
                        "latencia_ms": latencia_ms,
                        "endpoint": ultimo_endpoint,
                    },
                }

            if response.status_code in (404, 429):
                erros_tentativas.append(f"{modelo_recurso}: HTTP {response.status_code}")
                continue

            response.raise_for_status()

        raise RuntimeError(f"Todos os modelos testados atingiram limite de cota ({', '.join(erros_tentativas)})")

    except Exception as exc:
        latencia_ms = round((time.perf_counter() - inicio) * 1000, 1)
        resp_erro = getattr(exc, "response", None)
        status_http = getattr(resp_erro, "status_code", 429 if "429" in str(exc) else 500)

        resultado = _fallback_heuristico(mensagem)
        return {
            "dados": resultado,
            "telemetria": {
                "modo": f"Fallback automático ({str(exc)[:140]})",
                "status_http": status_http,
                "latencia_ms": latencia_ms,
                "endpoint": GEMINI_BASE_URL,
            },
        }
