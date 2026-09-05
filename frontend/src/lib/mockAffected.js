// MOCK DATA — placeholder for the future vector-search + redline pipeline.
//
// Later, when a regulatory change is ingested, we'll embed it and run a vector
// search over internal documents to find likely-affected clauses, then ask the
// LLM to propose a redline fix for each. Until that exists, this module fabricates
// a stable, plausible set of "affected documents" for a given regulation so the
// UI can be built and demoed. Results are deterministic per regulation id.

const INTERNAL_DOCS = [
  {
    docName: 'Related Party Transaction (RPT) Approval Policy',
    section: 'Section 2 — Board Approval Threshold',
    original:
      'A related party transaction exceeding the materiality threshold set under this policy, or any write-off of exposure to a related party, requires the approval of a simple majority of the Board (i.e. more than half of directors present and voting).',
    redline:
      'A related party transaction exceeding the materiality threshold set under this policy, or any write-off of exposure to a related party, requires the approval of [-a simple majority of the Board (i.e. more than half of directors present and voting)-] {+not less than two-thirds of the Board of directors, with any director having an interest in the transaction abstaining from the deliberation and vote+}.',
  },
  {
    docName: 'Related Party Transaction (RPT) Approval Policy',
    section: 'Section 3 — Materiality Thresholds',
    original:
      'Materiality thresholds for each related party group are reviewed by Risk & Compliance and endorsed by the Chief Risk Officer as needed.',
    redline:
      'Materiality thresholds for each related party group are reviewed by Risk & Compliance and endorsed by the [-Chief Risk Officer as needed-] {+Board at least annually. A transaction is material where its value exceeds the lower of S$5 million or 5% of the Bank’s latest audited capital funds+}.',
  },
  {
    docName: 'Related Party Transaction (RPT) Approval Policy',
    section: 'Section 4 — Identification of Related Parties',
    original:
      'Directors, executive officers and key credit approvers are required to disclose potential conflicts of interest to the Board upon appointment and whenever a material change occurs.',
    redline:
      'Directors, executive officers and key credit approvers are required to disclose potential conflicts of interest to the Board upon appointment[-and whenever a material change occurs-] {+, whenever a material change occurs, and in any event no less than annually. Disclosures shall extend to entities in which the individual, or a connected party, holds a controlling interest of 20% or more+}.',
  },
  {
    docName: 'Related Party Transaction (RPT) Approval Policy',
    section: 'Section 5 — Reporting to MAS',
    original:
      'A summary of related party transactions is submitted to the Board on a quarterly basis.',
    redline:
      'A summary of related party transactions is submitted to the Board [-on a quarterly basis-] {+on a quarterly basis and lodged with the Monetary Authority of Singapore within 14 days of Board approval, in the form prescribed under MAS Notice 643+}.',
  },
  {
    docName: 'Credit Risk Management Framework',
    section: 'Section 7 — Related party exposure limits',
    original:
      'Aggregate credit exposure to all related parties shall not exceed 25% of capital funds.',
    redline:
      'Aggregate credit exposure to all related parties shall not exceed [-25%-] {+50% of capital funds, with exposure to any single related party group not exceeding 25%+} of capital funds{+, measured on a look-through basis to connected counterparties+}.',
  },
  {
    docName: 'Board Governance & Conflicts of Interest Charter',
    section: 'Clause 6 — Abstention from voting',
    original:
      'An interested director may remain present during discussion of a related party transaction but shall not vote on it.',
    redline:
      'An interested director [-may remain present during discussion of a related party transaction but shall not vote on it-] {+shall recuse themselves from both the deliberation and the vote on the related party transaction, and shall not be counted towards the quorum for that item+}.',
  },
  {
    docName: 'Regulatory Reporting Procedures Manual',
    section: 'Item 9 — MAS Notice 643 returns',
    original:
      'Related party transaction returns are prepared annually for management review.',
    redline:
      'Related party transaction returns are prepared [-annually for management review-] {+quarterly and submitted to MAS in accordance with MAS Notice 643, with material transactions reported within 14 days of approval+}.',
  },
]

function hash(str) {
  let h = 0
  for (let i = 0; i < str.length; i += 1) {
    h = (h * 31 + str.charCodeAt(i)) & 0xffffffff
  }
  return Math.abs(h)
}

// Returns a stable array of affected internal documents for a regulation.
export function affectedDocumentsFor(doc) {
  const key = doc?.id || doc?.source_url || doc?.title || ''
  const h = hash(String(key))
  const count = h % 4 // 0–3 affected documents
  const results = []
  for (let i = 0; i < count; i += 1) {
    const base = INTERNAL_DOCS[(h + i * 7) % INTERNAL_DOCS.length]
    // Confidence between 0.71 and 0.95, stable per (regulation, index).
    const confidence = 0.71 + (((h >> (i + 1)) % 25) / 100)
    results.push({ id: `${key}-${i}`, confidence, ...base })
  }
  return results
}

export function affectedCountFor(doc) {
  return affectedDocumentsFor(doc).length
}
