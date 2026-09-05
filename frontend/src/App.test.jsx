import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'

import App from './App.jsx'

afterEach(() => vi.restoreAllMocks())

test('loads saved documents when the application opens', async () => {
  vi.spyOn(globalThis, 'fetch').mockResolvedValue({
    ok: true,
    json: async () => [{
      id: 'saved-1',
      title: 'Saved MAS circular',
      date: '2026-09-03',
      doc_type: 'Circular',
      topic: 'AML',
      tags: [],
      applies_to: [],
      source_url: 'https://mas.gov.sg/saved',
      pdf_url: null,
      llm_summary: 'Saved summary',
      llm_categories: [],
      llm_impact_check: null,
    }],
  })

  render(<App />)

  expect((await screen.findAllByText('Saved MAS circular')).length).toBeGreaterThan(0)
  expect(globalThis.fetch).toHaveBeenCalledWith('/api/v1/documents')
})

test('switches views without discarding loaded update state', async () => {
  vi.spyOn(globalThis, 'fetch').mockResolvedValue({
    ok: true,
    json: async () => [{
      id: 'saved-1', title: 'Persistent circular', date: null,
      doc_type: null, topic: null, tags: [], applies_to: [],
      source_url: 'https://mas.gov.sg/saved', pdf_url: null,
      llm_summary: null, llm_categories: [], llm_impact_check: null,
    }],
  })
  render(<App />)
  await screen.findAllByText('Persistent circular')

  fireEvent.click(screen.getByRole('button', { name: 'Resilience Analysis' }))
  expect(screen.getByRole('heading', { name: 'Resilience Analysis' })).toBeInTheDocument()

  fireEvent.click(screen.getByRole('button', { name: 'Regulatory Updates' }))
  await waitFor(() => expect(screen.getAllByText('Persistent circular').length).toBeGreaterThan(0))
  expect(globalThis.fetch).toHaveBeenCalledTimes(1)
})

test('shows saved-document states separately and retains documents when scraping fails', async () => {
  let resolveDocuments
  vi.spyOn(globalThis, 'fetch')
    .mockImplementationOnce(() => new Promise(resolve => { resolveDocuments = resolve }))
    .mockRejectedValueOnce(new Error('MAS unavailable'))

  render(<App />)
  expect(screen.getByText('Loading saved documents…')).toBeInTheDocument()

  resolveDocuments({
    ok: true,
    json: async () => [{
      id: 'saved-1', title: 'Still visible', date: null, doc_type: null,
      topic: null, tags: [], applies_to: [], source_url: 'https://mas.gov.sg/saved',
      pdf_url: null, llm_summary: null, llm_categories: [], llm_impact_check: null,
    }],
  })
  await screen.findAllByText('Still visible')

  fireEvent.click(screen.getByRole('button', { name: 'Fetch Latest Updates' }))

  expect(await screen.findByRole('alert')).toHaveTextContent('MAS unavailable')
  expect(screen.getAllByText('Still visible').length).toBeGreaterThan(0)
})

test('shows a saved-database empty state after initial loading', async () => {
  vi.spyOn(globalThis, 'fetch').mockResolvedValue({ ok: true, json: async () => [] })

  render(<App />)

  expect(await screen.findByText('No saved regulatory documents yet.')).toBeInTheDocument()
})

test('disables fresh scraping until saved documents finish loading', () => {
  vi.spyOn(globalThis, 'fetch').mockImplementation(() => new Promise(() => {}))

  render(<App />)

  expect(screen.getByRole('button', { name: 'Fetch Latest Updates' })).toBeDisabled()
  expect(globalThis.fetch).toHaveBeenCalledTimes(1)
})

test('shows a lookback-specific empty state after a successful scrape', async () => {
  vi.spyOn(globalThis, 'fetch')
    .mockResolvedValueOnce({ ok: true, json: async () => [] })
    .mockResolvedValueOnce({ ok: true, json: async () => [] })
  render(<App />)
  await screen.findByText('No saved regulatory documents yet.')

  fireEvent.click(screen.getByRole('button', { name: 'Fetch Latest Updates' }))

  expect(await screen.findByText('No MAS documents found in the last 7 days.')).toBeInTheDocument()
})
