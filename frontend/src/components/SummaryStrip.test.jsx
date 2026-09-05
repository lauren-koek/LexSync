import { render, screen } from '@testing-library/react'
import { expect, test } from 'vitest'
import SummaryStrip from './SummaryStrip.jsx'

const today = new Date().toISOString().slice(0, 10)

const docs = [
  { id: '1', date: today, llm_impact_check: 'This has a high, material impact.' },
  { id: '2', date: '2000-01-01', llm_impact_check: 'may require review' },
  { id: '3', date: today, llm_impact_check: null },
]

test('summarises totals, recency, and high-impact counts', () => {
  render(<SummaryStrip docs={docs} days={7} />)

  expect(screen.getByText('Documents tracked').nextSibling).toHaveTextContent('3')
  expect(screen.getByText('New in 7 days').nextSibling).toHaveTextContent('2')
  expect(screen.getByText('High impact').nextSibling).toHaveTextContent('1')
})
