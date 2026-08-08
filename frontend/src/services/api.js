const CHAT_ENDPOINT = '/api/chat'
const REQUEST_TIMEOUT_MS = 90_000

export async function sendMessage(message) {
  const controller = new AbortController()
  const timeoutId = window.setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS)

  try {
    const response = await fetch(CHAT_ENDPOINT, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ message }),
      signal: controller.signal,
    })

    if (!response.ok) {
      throw new Error(`O backend respondeu com HTTP ${response.status}`)
    }

    const data = await response.json()
    if (typeof data.response !== 'string' || !data.response.trim()) {
      throw new Error('O backend retornou uma resposta inválida')
    }

    return data.response
  } finally {
    window.clearTimeout(timeoutId)
  }
}
