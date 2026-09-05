import { render, screen } from '@testing-library/react'
import { expect, test } from 'vitest'
import ImpactMapView from './ImpactMapView.jsx'

test('explains the future relationship map without fake controls', () => {
  render(<ImpactMapView />)
  expect(screen.getByText('Regulation')).toBeInTheDocument()
  expect(screen.getByText('Internal policy')).toBeInTheDocument()
  expect(screen.getByText('Required action')).toBeInTheDocument()
  expect(screen.getByText(/once internal documents are ingested/i)).toBeInTheDocument()
  expect(screen.queryByRole('button', { name: /filter/i })).not.toBeInTheDocument()
})
