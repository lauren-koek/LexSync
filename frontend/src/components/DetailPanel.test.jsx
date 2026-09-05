import { render, screen } from '@testing-library/react'
import { expect, test } from 'vitest'

import DetailPanel from './DetailPanel.jsx'

const document = {
  id: 'notice-656',
  title: 'Notice 656',
  date: '2026-09-04',
  effective_date: '2026-07-01',
  doc_type: 'Notices',
  topic: 'Credit Risk',
  tags: [],
  applies_to: [],
  issued_pursuant_to: [],
  source_url: 'https://www.mas.gov.sg/regulation/notices/notice-656',
  llm_categories: [],
  llm_summary: 'Summary text.',
  llm_impact_check: 'IMPACT CHECK\nArtefact types to review: policies\nEffective date: 04 September 2026',
}

test('shows scraped effective date in document metadata', () => {
  render(<DetailPanel doc={document} />)

  expect(screen.getByText('Effective 2026-07-01')).toBeInTheDocument()
})

test('does not repeat the impact heading or LLM-generated effective date in the impact body', () => {
  render(<DetailPanel doc={document} />)

  expect(screen.getAllByText(/Impact check/i)).toHaveLength(1)
  expect(screen.getByText('Artefact types to review: policies')).toBeInTheDocument()
  expect(screen.queryByText('Effective date: 04 September 2026')).not.toBeInTheDocument()
})
