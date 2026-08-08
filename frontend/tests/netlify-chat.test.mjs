import assert from 'node:assert/strict'
import test from 'node:test'

import handler, { createChatHandler } from '../netlify/functions/chat.mjs'

const endpoint = 'http://localhost/api/chat'

function request(method = 'POST', body = { message: 'Olá' }) {
  const options = { method }
  if (body !== undefined) {
    options.headers = { 'Content-Type': 'application/json' }
    options.body = JSON.stringify(body)
  }
  return new Request(endpoint, options)
}

test('encaminha POST válido somente para /api/chat', async () => {
  let receivedUrl
  let receivedOptions
  const localHandler = createChatHandler({
    getBackendBaseUrl: () => 'https://backend.example/base-ignorada',
    fetchImpl: async (url, options) => {
      receivedUrl = url
      receivedOptions = options
      return Response.json({ response: 'proxy funcionando' })
    },
  })

  const response = await localHandler(request('POST', { message: '  teste  ', url: 'https://evil.example' }))

  assert.equal(response.status, 200)
  assert.deepEqual(await response.json(), { response: 'proxy funcionando' })
  assert.equal(receivedUrl.toString(), 'https://backend.example/api/chat')
  assert.deepEqual(JSON.parse(receivedOptions.body), { message: 'teste' })
})

test('rejeita GET com Allow POST', async () => {
  const response = await handler(new Request(endpoint, { method: 'GET' }))

  assert.equal(response.status, 405)
  assert.equal(response.headers.get('allow'), 'POST')
})

test('rejeita POST sem message', async () => {
  const response = await handler(request('POST', {}))

  assert.equal(response.status, 400)
  assert.match((await response.json()).error, /message/)
})

test('rejeita JSON inválido de forma controlada', async () => {
  const response = await handler(
    new Request(endpoint, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: '{',
    }),
  )

  assert.equal(response.status, 400)
  assert.deepEqual(await response.json(), { error: 'JSON inválido.' })
})

test('trata backend indisponível sem expor detalhes', async () => {
  const localHandler = createChatHandler({
    getBackendBaseUrl: () => 'https://backend.example',
    fetchImpl: async () => {
      throw new Error('detalhe interno sensível')
    },
  })

  const response = await localHandler(request())

  assert.equal(response.status, 502)
  assert.deepEqual(await response.json(), { error: 'Não foi possível conectar ao assistente.' })
})

test('trata timeout de forma controlada', async () => {
  const localHandler = createChatHandler({
    getBackendBaseUrl: () => 'https://backend.example',
    timeoutMs: 5,
    fetchImpl: (_url, { signal }) =>
      new Promise((_resolve, reject) => {
        signal.addEventListener('abort', () => {
          reject(new DOMException('aborted', 'AbortError'))
        })
      }),
  })

  const response = await localHandler(request())

  assert.equal(response.status, 504)
  assert.deepEqual(await response.json(), { error: 'O assistente demorou demais para responder.' })
})
