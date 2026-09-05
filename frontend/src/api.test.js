import { afterEach, expect, test, vi } from 'vitest'

import { runAnalysis, uploadInternalDocument } from './api.js'

afterEach(() => vi.restoreAllMocks())

test('uploads an internal PDF as multipart data', async () => {
  const file = new File(['pdf'], 'policy.pdf', { type: 'application/pdf' })
  const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue({
    ok: true,
    status: 201,
    json: async () => ({ id: 'doc-1' }),
  })

  await uploadInternalDocument(file, 'Policy')

  const [url, options] = fetchMock.mock.calls[0]
  expect(url).toBe('/api/v1/internal-documents')
  expect(options.method).toBe('POST')
  expect(options.headers).toBeUndefined()
  expect(options.body.get('file')).toBe(file)
  expect(options.body.get('title')).toBe('Policy')
})

test('runAnalysis sends text and uploaded files as multipart data', async () => {
  const regulationFile = new File(['reg'], 'regulation.txt')
  const assetFile = new File(['asset'], 'asset.txt')
  const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue({
    ok: true,
    status: 200,
    json: async () => ({ report: [] }),
  })

  await runAnalysis({
    regulationText: 'pasted reg', internalAssetText: 'pasted asset',
    regulationFile, internalAssetFile: assetFile,
  })

  const [url, options] = fetchMock.mock.calls[0]
  expect(url).toBe('/api/v1/analysis/upload')
  expect(options.method).toBe('POST')
  expect(options.headers).toBeUndefined()
  expect(options.body.get('regulation_text')).toBe('pasted reg')
  expect(options.body.get('internal_asset_text')).toBe('pasted asset')
  expect(options.body.get('regulation_file')).toBe(regulationFile)
  expect(options.body.get('internal_asset_file')).toBe(assetFile)
})

test('reports a readable error when the server does not return JSON', async () => {
  vi.spyOn(globalThis, 'fetch').mockResolvedValue({
    ok: false,
    status: 502,
    json: async () => { throw new SyntaxError('invalid') },
  })

  await expect(runAnalysis({
    regulationText: 'reg', internalAssetText: 'asset',
    regulationFile: null, internalAssetFile: null,
  })).rejects.toThrow('Server returned an invalid response (502)')
})
