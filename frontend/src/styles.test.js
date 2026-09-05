import { readFileSync } from 'node:fs'
import { expect, test } from 'vitest'

test('active stylesheet owns the resilience result presentation', () => {
  const css = readFileSync('src/index.css', 'utf8')
  for (const selector of ['.impact-summary', '.impact-card', '.impact-heading', '.impact-badge', '.result-block', '.result-meta', '.redline', '.propagation-note', '.analysis-notice']) {
    expect(css, `${selector} must be styled by imported index.css`).toContain(selector)
  }
})
