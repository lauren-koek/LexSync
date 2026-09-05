import { render, screen } from '@testing-library/react'
import { expect, test } from 'vitest'
import PageIntro from './PageIntro.jsx'
import MetricStrip from './MetricStrip.jsx'

test('renders an orienting page hierarchy and status', () => {
  render(<PageIntro eyebrow="Workspace" title="Make change legible" description="Review what matters." status="2 need attention" />)
  expect(screen.getByRole('heading', { name: 'Make change legible' })).toBeInTheDocument()
  expect(screen.getByText('Review what matters.')).toBeInTheDocument()
  expect(screen.getByText('2 need attention')).toBeInTheDocument()
})

test('renders decision metrics as a labelled group', () => {
  render(<MetricStrip items={[{ label: 'High impact', value: 3, tone: 'red' }]} />)
  expect(screen.getByRole('group', { name: 'Summary metrics' })).toHaveTextContent('High impact3')
})
