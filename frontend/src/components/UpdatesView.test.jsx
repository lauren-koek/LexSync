import { render, screen } from '@testing-library/react'
import { expect, test, vi } from 'vitest'
import UpdatesView from './UpdatesView.jsx'

test('leads with attention and keeps evidence in the workspace', () => {
  const documents = {
    days: 7, setDays: vi.fn(), initialLoading: false, initialError: null,
    scrapeLoading: false, scrapeError: null, resultSource: 'saved', runFetch: vi.fn(),
    docs: [{ id: '1', title: 'Material AML update', date: '2026-09-05', doc_type: 'Circular', topic: 'AML', source_url: 'https://mas/1', tags: [], applies_to: [], llm_categories: [], llm_impact_check: 'high material impact', llm_summary: 'Review controls now.' }],
  }
  render(<UpdatesView documents={documents} />)
  expect(screen.getByRole('heading', { name: 'Regulatory change, made legible.' })).toBeInTheDocument()
  expect(screen.getByText(/1 high-impact update needs attention/i)).toBeInTheDocument()
  expect(screen.getByRole('link', { name: /Source/i })).toHaveAttribute('href', 'https://mas/1')
})
