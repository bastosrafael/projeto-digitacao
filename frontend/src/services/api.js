const CHAT_ENDPOINT = '/api/chat'
const REQUEST_TIMEOUT_MS = 90_000
const UPLOAD_API_BASE_URL = (import.meta.env?.VITE_UPLOAD_API_BASE_URL || '').replace(/\/$/, '')

function uploadEndpoint(path = '') {
  return `${UPLOAD_API_BASE_URL}/api/uploads${path}`
}

async function readError(response, fallback) {
  try {
    const data = await response.json()
    return typeof data.detail === 'string' ? data.detail : fallback
  } catch {
    return fallback
  }
}

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

export async function getUploadConfig() {
  const response = await fetch(uploadEndpoint('/config'))
  if (!response.ok) {
    throw new Error(await readError(response, 'Não foi possível consultar o limite de upload.'))
  }

  const data = await response.json()
  if (!Number.isInteger(data.max_upload_size_mb) || data.max_upload_size_mb <= 0) {
    throw new Error('O backend retornou uma configuração de upload inválida.')
  }

  return data
}

export async function uploadSpreadsheet(file) {
  const formData = new FormData()
  formData.append('file', file, file.name)

  const response = await fetch(uploadEndpoint(), {
    method: 'POST',
    body: formData,
  })

  if (!response.ok) {
    throw new Error(await readError(response, `O upload falhou com HTTP ${response.status}.`))
  }

  return response.json()
}
