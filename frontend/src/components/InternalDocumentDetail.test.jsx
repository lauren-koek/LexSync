import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'
import InternalDocumentDetail from './InternalDocumentDetail.jsx'

afterEach(() => vi.restoreAllMocks())

test('shows the PDF beside extracted clauses and suggestions', async () => {
  vi.spyOn(globalThis, 'fetch')
    .mockResolvedValueOnce({ ok: true, json: async () => ({
      id: 'doc-1', title: 'Policy', filename: 'policy.pdf', size_bytes: 100,
      chunk_count: 1, status: 'indexed', created_at: '2026-09-06T00:00:00Z',
      chunks: [{ id: 'chunk-1', clause_reference: 'Clause 1', content: 'Keep records.' }],
      suggestions: [{
        id: 'suggestion-1', regulatory_document_id: 'reg-1', internal_document_id: 'doc-1',
        internal_chunk_id: 'chunk-1', regulation_clause_reference: 'Section 2',
        regulation_content: 'Keep records seven years.', similarity_score: 0.91,
        is_affected: true, impact_score: 8, legal_reasoning: 'Retention changed.',
        proposed_amended_clause: 'Keep records seven years.', statutory_citations: ['Section 2'],
        redline_diff: '[-three years-] {+seven years+}', analysis_source: 'llm', status: 'pending',
      }],
    }) })
    .mockResolvedValueOnce({ ok: true, json: async () => ({ url: 'https://signed.example/policy.pdf' }) })

  render(<InternalDocumentDetail documentId="doc-1" onBack={vi.fn()} onDeleted={vi.fn()} />)

  expect(await screen.findByTitle('Policy PDF')).toHaveAttribute('src', 'https://signed.example/policy.pdf')
  expect(screen.getByText('Clause 1')).toBeInTheDocument()
  expect(screen.getByText('Retention changed.')).toBeInTheDocument()
  expect(screen.getByText('three years')).toBeInTheDocument()
  expect(screen.getByText('seven years')).toBeInTheDocument()
})

test('deletes a document exactly once before returning to the library', async () => {
  const onDeleted = vi.fn()
  vi.spyOn(window, 'confirm').mockReturnValue(true)
  const fetchMock = vi.spyOn(globalThis, 'fetch')
    .mockResolvedValueOnce({ ok: true, json: async () => ({
      id: 'doc-1', title: 'Policy', filename: 'policy.pdf', size_bytes: 100,
      chunk_count: 0, status: 'indexed', created_at: null, chunks: [], suggestions: [],
    }) })
    .mockResolvedValueOnce({ ok: true, json: async () => ({ url: 'signed://pdf' }) })
    .mockResolvedValueOnce({ ok: true, status: 204 })

  render(<InternalDocumentDetail documentId="doc-1" onBack={vi.fn()} onDeleted={onDeleted} />)
  fireEvent.click(await screen.findByRole('button', { name: 'Delete' }))

  await waitFor(() => expect(onDeleted).toHaveBeenCalledWith('doc-1'))
  expect(fetchMock.mock.calls.filter(([url, options]) =>
    url === '/api/v1/internal-documents/doc-1' && options?.method === 'DELETE'
  )).toHaveLength(1)
})
