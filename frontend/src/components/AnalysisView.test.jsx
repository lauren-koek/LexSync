import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, expect, test, vi } from 'vitest'

import { runAnalysis } from '../api.js'
import AnalysisView from './AnalysisView.jsx'
import Redline from './Redline.jsx'

vi.mock('../api.js', () => ({ runAnalysis: vi.fn() }))

const response = {
  regulation_id: 'Uploaded_Regulation',
  asset_id: 'Uploaded_Internal_Asset',
  clause_count: 3,
  match_count: 1,
  report: [{
    regulation: { title: 'Regulation', clause_reference: 'Section 12A', content: 'retain seven years' },
    asset: { title: 'Playbook', clause_reference: 'Clause 8', content: 'retain three years' },
    similarity_score: 0.8123,
    analysis: {
      is_affected: true,
      impact_score: 7,
      legal_reasoning: 'The retention period changed.',
      proposed_amended_clause: 'retain seven years',
      statutory_citations: ['Section 12A'],
    },
    redline_diff: 'retain [-three-] {+seven+} years',
    analysis_source: 'offline_heuristic',
  }],
  propagation: { dispatched: 1, dry_run: true, timestamp: '2026-09-05T00:00:00Z' },
}

beforeEach(() => runAnalysis.mockReset())

test('renders safe additions and deletions in a redline', () => {
  render(<Redline value="retain [-three-] {+seven+} years" />)

  expect(screen.getByText('three', { selector: 'del' })).toBeInTheDocument()
  expect(screen.getByText('seven', { selector: 'ins' })).toBeInTheDocument()
})

test('submits historical inputs and renders the impact report', async () => {
  runAnalysis.mockResolvedValue(response)
  render(<AnalysisView />)

  expect(screen.getByRole('heading', { name: 'Resilience Analysis' })).toBeInTheDocument()
  const progress = screen.getByLabelText('Analysis progress')
  for (const step of ['Inputs', 'Analyse', 'Findings', 'Decision']) expect(progress).toHaveTextContent(step)

  expect(screen.getByLabelText('Regulatory update text').value).toContain('Section 12A')
  expect(screen.getByLabelText('Internal legal asset text').value).toContain('Clause 8')

  const file = new File(['uploaded regulation'], 'regulation.txt', { type: 'text/plain' })
  fireEvent.change(screen.getByLabelText('Regulation file'), { target: { files: [file] } })
  expect(screen.getByText(/replaces the pasted regulation text/i)).toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: 'Run Resilience Analysis' }))

  await waitFor(() => expect(runAnalysis).toHaveBeenCalled())
  expect(runAnalysis.mock.calls[0][0].regulationFile).toBe(file)
  expect(await screen.findByText('The retention period changed.')).toBeInTheDocument()
  expect(screen.getByRole('heading', { name: /1 clause requires action/i })).toBeInTheDocument()
  expect(screen.getByRole('table', { name: 'Impact summary' })).toBeInTheDocument()
  expect(screen.getByText(/Citations:.*Section 12A/)).toBeInTheDocument()
  expect(screen.getByText('3', { selector: '.metric-value' })).toBeInTheDocument()
  expect(screen.getByText('three', { selector: 'del' })).toBeInTheDocument()
})

test('shows the historical no-match state', async () => {
  runAnalysis.mockResolvedValue({ ...response, match_count: 0, report: [], propagation: { ...response.propagation, dispatched: 0 } })
  render(<AnalysisView />)

  fireEvent.click(screen.getByRole('button', { name: 'Run Resilience Analysis' }))

  expect(await screen.findByText(/No semantically related internal assets/)).toBeInTheDocument()
  expect(screen.getByText(/check the source text or try another internal asset/i)).toBeInTheDocument()
})

test('keeps the previous report visible when a later analysis fails', async () => {
  runAnalysis.mockResolvedValueOnce(response).mockRejectedValueOnce(new Error('analysis unavailable'))
  render(<AnalysisView />)
  const submit = screen.getByRole('button', { name: 'Run Resilience Analysis' })

  fireEvent.click(submit)
  expect(await screen.findByText('The retention period changed.')).toBeInTheDocument()
  fireEvent.click(submit)

  expect(await screen.findByRole('alert')).toHaveTextContent('analysis unavailable')
  expect(screen.getByText('The retention period changed.')).toBeInTheDocument()
})

test('renders HTML-like redline content as text rather than markup', () => {
  render(<Redline value={'[-<script>alert(1)</script>-] {+safe\ntext+}'} />)

  expect(document.querySelector('script')).toBeNull()
  expect(screen.getByText('<script>alert(1)</script>', { selector: 'del' })).toBeInTheDocument()
  expect(screen.getByText(/safe\s+text/, { selector: 'ins' })).toBeInTheDocument()
})
