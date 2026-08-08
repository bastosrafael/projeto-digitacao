const MAX_BODY_BYTES = 16_384
const MAX_MESSAGE_LENGTH = 4_000
const DEFAULT_TIMEOUT_MS = 25_000

function jsonResponse(body, status, extraHeaders = {}) {
  return new Response(JSON.stringify(body), {
    status,
    headers: {
      'Content-Type': 'application/json; charset=utf-8',
      ...extraHeaders,
    },
  })
}

function resolveChatUrl(baseUrl) {
  if (!baseUrl) {
    throw new Error('BACKEND_BASE_URL não configurada')
  }

  const url = new URL(baseUrl)
  if (!['http:', 'https:'].includes(url.protocol) || url.username || url.password) {
    throw new Error('BACKEND_BASE_URL inválida')
  }

  url.pathname = '/api/chat'
  url.search = ''
  url.hash = ''
  return url
}

async function readPayload(request) {
  const declaredLength = Number(request.headers.get('content-length'))
  if (Number.isFinite(declaredLength) && declaredLength > MAX_BODY_BYTES) {
    return { error: jsonResponse({ error: 'Corpo da requisição muito grande.' }, 413) }
  }

  const rawBody = await request.text()
  if (new TextEncoder().encode(rawBody).byteLength > MAX_BODY_BYTES) {
    return { error: jsonResponse({ error: 'Corpo da requisição muito grande.' }, 413) }
  }

  let payload
  try {
    payload = JSON.parse(rawBody)
  } catch {
    return { error: jsonResponse({ error: 'JSON inválido.' }, 400) }
  }

  if (!payload || typeof payload !== 'object' || Array.isArray(payload)) {
    return { error: jsonResponse({ error: 'O corpo deve ser um objeto JSON.' }, 400) }
  }

  if (typeof payload.message !== 'string') {
    return { error: jsonResponse({ error: 'O campo message deve ser uma string.' }, 400) }
  }

  const message = payload.message.trim()
  if (!message) {
    return { error: jsonResponse({ error: 'O campo message não pode estar vazio.' }, 400) }
  }

  if (message.length > MAX_MESSAGE_LENGTH) {
    return {
      error: jsonResponse(
        { error: `O campo message deve ter no máximo ${MAX_MESSAGE_LENGTH} caracteres.` },
        413,
      ),
    }
  }

  return { message }
}

export function createChatHandler({
  fetchImpl = globalThis.fetch,
  getBackendBaseUrl = () => process.env.BACKEND_BASE_URL,
  timeoutMs = DEFAULT_TIMEOUT_MS,
} = {}) {
  return async function chatHandler(request) {
    if (request.method !== 'POST') {
      return jsonResponse({ error: 'Método não permitido.' }, 405, { Allow: 'POST' })
    }

    const contentType = request.headers.get('content-type') || ''
    if (!contentType.toLowerCase().includes('application/json')) {
      return jsonResponse({ error: 'Content-Type deve ser application/json.' }, 415)
    }

    let parsed
    try {
      parsed = await readPayload(request)
    } catch {
      return jsonResponse({ error: 'Não foi possível ler a requisição.' }, 400)
    }

    if (parsed.error) {
      return parsed.error
    }

    let chatUrl
    try {
      chatUrl = resolveChatUrl(getBackendBaseUrl())
    } catch {
      return jsonResponse({ error: 'Proxy do assistente não configurado.' }, 500)
    }

    const controller = new AbortController()
    const timeoutId = setTimeout(() => controller.abort(), timeoutMs)

    try {
      const upstream = await fetchImpl(chatUrl, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: parsed.message }),
        redirect: 'error',
        signal: controller.signal,
      })

      let data
      try {
        data = await upstream.json()
      } catch {
        return jsonResponse({ error: 'O assistente retornou uma resposta inválida.' }, 502)
      }

      if (!upstream.ok) {
        const status = upstream.status >= 400 && upstream.status <= 599 ? upstream.status : 502
        return jsonResponse({ error: 'O assistente não conseguiu processar a solicitação.' }, status)
      }

      if (typeof data.response !== 'string' || !data.response.trim()) {
        return jsonResponse({ error: 'O assistente retornou uma resposta inválida.' }, 502)
      }

      return jsonResponse({ response: data.response }, 200)
    } catch (error) {
      if (error?.name === 'AbortError') {
        return jsonResponse({ error: 'O assistente demorou demais para responder.' }, 504)
      }

      return jsonResponse({ error: 'Não foi possível conectar ao assistente.' }, 502)
    } finally {
      clearTimeout(timeoutId)
    }
  }
}

export default createChatHandler()

