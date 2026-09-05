import { fireEvent, render, screen } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'
import App from '../App.jsx'

afterEach(() => vi.restoreAllMocks())

test('opens the Internal Documents library from the sidebar', async () => {
  vi.spyOn(globalThis, 'fetch')
    .mockResolvedValueOnce({ ok: true, json: async () => [] })
    .mockResolvedValueOnce({ ok: true, json: async () => [{
      id: 'doc-1', title: 'Incident Policy', filename: 'incident.pdf',
      size_bytes: 1200, chunk_count: 3, status: 'indexed',
      created_at: '2026-09-06T00:00:00Z',
    }] })

  render(<App />)
  fireEvent.click(screen.getByRole('button', { name: 'Internal Documents' }))

  expect(await screen.findByText('Incident Policy')).toBeInTheDocument()
  expect(screen.getByText('incident.pdf')).toBeInTheDocument()
  expect(screen.getByRole('button', { name: /Open Incident Policy/i })).toBeInTheDocument()
})

test('makes choosing a PDF the obvious first upload action', async () => {
  vi.spyOn(globalThis, 'fetch')
    .mockResolvedValueOnce({ ok: true, json: async () => [] })
    .mockResolvedValueOnce({ ok: true, json: async () => [] })
  render(<App />)
  fireEvent.click(screen.getByRole('button', { name: 'Internal Documents' }))

  expect(await screen.findByRole('button', { name: 'Choose PDF' })).toBeInTheDocument()
  expect(screen.getByText('or drag and drop it here')).toBeInTheDocument()
  expect(screen.queryByRole('button', { name: 'Upload and index' })).not.toBeInTheDocument()

  fireEvent.change(screen.getByLabelText('Choose a PDF'), {
    target: { files: [new File(['pdf'], 'policy.pdf', { type: 'application/pdf' })] },
  })

  expect(screen.getByText('policy.pdf')).toBeInTheDocument()
  expect(screen.getByRole('button', { name: 'Upload and index' })).toBeEnabled()
  expect(screen.getByRole('button', { name: 'Change file' })).toBeInTheDocument()
})
