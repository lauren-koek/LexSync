import { fireEvent, render, screen } from '@testing-library/react'
import { expect, test } from 'vitest'
import RegulatoryChangesView from './RegulatoryChangesView.jsx'

const docs = [
  {
    id: '1', title: 'AML Circular', date: '2026-09-01', doc_type: 'Circular',
    topic: 'AML', tags: [], applies_to: [], source_url: 'https://mas/1',
    llm_categories: ['Reporting'], llm_impact_check: 'high material impact',
  },
  {
    id: '2', title: 'Capital Guideline', date: '2026-08-01', doc_type: 'Guideline',
    topic: 'Capital', tags: [], applies_to: [], source_url: 'https://mas/2',
    llm_categories: ['Prudential'], llm_impact_check: null,
  },
]

function view(overrides = {}) {
  return {
    docs,
    initialLoading: false,
    initialError: null,
    ...overrides,
  }
}

test('renders all documents as timeline rows', () => {
  render(<RegulatoryChangesView documents={view()} />)
  expect(screen.getByText(/2 changes shown/i)).toBeInTheDocument()
  expect(screen.getByText('AML Circular')).toBeInTheDocument()
  expect(screen.getByText('Capital Guideline')).toBeInTheDocument()
})

test('filters rows by document type', () => {
  render(<RegulatoryChangesView documents={view()} />)

  const [typeSelect] = screen.getAllByRole('combobox')
  fireEvent.change(typeSelect, { target: { value: 'Guideline' } })

  expect(screen.queryByText('AML Circular')).not.toBeInTheDocument()
  expect(screen.getByText('Capital Guideline')).toBeInTheDocument()
})

test('opens the affected-documents page from an explicit impact action', () => {
  render(<RegulatoryChangesView documents={view()} />)
  fireEvent.click(screen.getAllByRole('button', { name: /View impact for AML Circular/i })[0])
  expect(
    screen.getByRole('button', { name: /Back to regulatory changes/i }),
  ).toBeInTheDocument()
  expect(screen.getByText('Regulatory change')).toBeInTheDocument()
})
