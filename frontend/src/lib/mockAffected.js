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
      'A related party transaction exceeding the materiality threshold set under this policy, or any write-off of exposure to a related party, requires the approval of a [-simple majority of the Board (i.e. more than half of directors present and voting)-] {+special majority of three-fourths of the Board of directors, determined by reference to the total number of directors on the Board and excluding any director required to abstain from voting+}.',
  },
  {
    docName: 'Related Party Transaction (RPT) Approval Policy',
    section: 'Section 3 — Materiality Thresholds',
    original:
      'Materiality thresholds for each related party group are reviewed by Risk & Compliance and endorsed by the Chief Risk Officer as needed.',
    redline:
      'Materiality thresholds are [-for each related party group reviewed by Risk & Compliance and endorsed by the Chief Risk Officer as needed-] {+set separately for exposures to each related party group and for each type of non-exposure transaction, taking into account the nature, scope, frequency, value of and risks associated with those transactions, and are endorsed by the Board+}.',
  },
  {
    docName: 'Related Party Transaction (RPT) Approval Policy',
    section: 'Section 4 — Identification of Related Parties',
    original:
      'Directors, executive officers and key credit approvers are required to disclose potential conflicts of interest to the Board upon appointment and whenever a material change occurs.',
    redline:
      '[-Directors, executive officers and key credit approvers-] {+Persons in the Bank’s director group, key credit approver group, senior management group, substantial shareholder group, major stake entity group and related corporation group+} are required to disclose potential conflicts of interest to the Board upon appointment and whenever a material change occurs.',
  },
  {
    docName: 'Related Party Transaction (RPT) Approval Policy',
    section: 'Section 5 — Scope of Approval',
    original:
      'Where a related party transaction is approved, the approval covers the principal terms of the transaction.',
    redline:
      'Where a related party transaction is approved, the approval covers [-the principal terms-] {+all the terms and conditions+} of the transaction.',
  },
  {
    docName: 'Credit Risk Management Framework',
    section: 'Section 7 — Related party exposure monitoring',
    original:
      'Exposures to related parties are monitored by the credit team and reviewed periodically.',
    redline:
      'Exposures to related parties are [-monitored by the credit team and reviewed periodically-] {+aggregated by related party group and monitored against the materiality thresholds set by the Board, with any transaction exceeding a threshold escalated for three-fourths special-majority Board approval before it is entered into+}.',
  },
  {
    docName: 'Board Governance & Conflicts of Interest Charter',
    section: 'Clause 6 — Abstention from voting',
    original:
      'A director with an interest in a related party transaction shall not vote on that transaction.',
    redline:
      'A director with an interest in a related party transaction shall [-not vote on that transaction-] {+abstain from voting on that transaction and be excluded from the total number of directors used to determine the three-fourths special majority required for approval+}.',
  },
  {
    docName: 'Regulatory Reporting Procedures Manual',
    section: 'Item 9 — Related party transaction register',
    original:
      'A summary of related party transactions is filed annually for internal record-keeping.',
    redline:
      'A [-summary of related party transactions is filed annually for internal record-keeping-] {+register of related party transactions is maintained, recording the approval obtained and the identity of any director who abstained from voting, and is reported to the Board each quarter+}.',
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
