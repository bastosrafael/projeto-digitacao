import assert from 'node:assert/strict'
import test from 'node:test'

import { getUploadConfig, uploadSpreadsheet } from '../src/services/api.js'

test('consulta o limite configurado pelo backend', async (context) => {
  const originalFetch = globalThis.fetch
  context.after(() => {
    globalThis.fetch = originalFetch
  })

  globalThis.fetch = async (url) => {
    assert.equal(url, '/api/uploads/config')
    return Response.json({ max_upload_size_mb: 200, accepted_extensions: ['.xlsx'] })
  }

  assert.deepEqual(await getUploadConfig(), {
    max_upload_size_mb: 200,
    accepted_extensions: ['.xlsx'],
  })
})

test('envia XLSX como FormData sem definir Content-Type manualmente', async (context) => {
  const originalFetch = globalThis.fetch
  context.after(() => {
    globalThis.fetch = originalFetch
  })

  globalThis.fetch = async (url, options) => {
    assert.equal(url, '/api/uploads')
    assert.equal(options.method, 'POST')
    assert.equal(options.headers, undefined)
    assert.ok(options.body instanceof FormData)
    assert.equal(options.body.get('file').name, 'produtos.xlsx')
    return Response.json({ file_id: '123', status: 'uploaded' }, { status: 201 })
  }

  const file = new File(['xlsx'], 'produtos.xlsx', {
    type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
  })
  assert.deepEqual(await uploadSpreadsheet(file), { file_id: '123', status: 'uploaded' })
})

test('propaga detalhe sanitizado do backend', async (context) => {
  const originalFetch = globalThis.fetch
  context.after(() => {
    globalThis.fetch = originalFetch
  })

  globalThis.fetch = async () =>
    Response.json(
      { detail: 'Arquivo excede o limite permitido de 200 MB.' },
      { status: 413 },
    )

  const file = new File(['xlsx'], 'grande.xlsx')
  await assert.rejects(
    uploadSpreadsheet(file),
    /Arquivo excede o limite permitido de 200 MB\./,
  )
})
