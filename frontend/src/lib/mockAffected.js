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
    reasoning:
      'MAS Notice 643 requires material related party transactions and write-offs to be approved by a special majority of three-fourths of the board, not a simple majority. The threshold in this clause must be raised to remain compliant.',
  },
  {
    docName: 'Related Party Transaction (RPT) Approval Policy',
    section: 'Section 3 — Materiality Thresholds',
    original:
      'Materiality thresholds for each related party group are reviewed by Risk & Compliance and endorsed by the Chief Risk Officer as needed.',
    redline:
      'Materiality thresholds are [-for each related party group reviewed by Risk & Compliance and endorsed by the Chief Risk Officer as needed-] {+set separately for exposures to each related party group and for each type of non-exposure transaction, taking into account the nature, scope, frequency, value of and risks associated with those transactions, and are endorsed by the Board+}.',
    reasoning:
      'The Notice requires separate materiality thresholds per related party group and per transaction type, weighing the nature, scope, frequency, value and risk of the transactions, with Board endorsement — a stricter standard than CRO sign-off "as needed".',
  },
  {
    docName: 'Related Party Transaction (RPT) Approval Policy',
    section: 'Section 4 — Identification of Related Parties',
    original:
      'Directors, executive officers and key credit approvers are required to disclose potential conflicts of interest to the Board upon appointment and whenever a material change occurs.',
    redline:
      '[-Directors, executive officers and key credit approvers-] {+Persons in the Bank’s director group, key credit approver group, senior management group, substantial shareholder group, major stake entity group and related corporation group+} are required to disclose potential conflicts of interest to the Board upon appointment and whenever a material change occurs.',
    reasoning:
      'MAS Notice 643 defines related parties across six groups (director, key credit approver, senior management, substantial shareholder, major stake entity and related corporation groups). This clause captures only three categories and must be broadened.',
  },
  {
    docName: 'Related Party Transaction (RPT) Approval Policy',
    section: 'Section 5 — Scope of Approval',
    original:
      'Where a related party transaction is approved, the approval covers the principal terms of the transaction.',
    redline:
      'Where a related party transaction is approved, the approval covers [-the principal terms-] {+all the terms and conditions+} of the transaction.',
    reasoning:
      'The Notice requires that approval be given in relation to all the terms and conditions of the related party transaction, not merely its principal terms.',
  },
  {
    docName: 'Credit Risk Management Framework',
    section: 'Section 7 — Related party exposure monitoring',
    original:
      'Exposures to related parties are monitored by the credit team and reviewed periodically.',
    redline:
      'Exposures to related parties are [-monitored by the credit team and reviewed periodically-] {+aggregated by related party group and monitored against the materiality thresholds set by the Board, with any transaction exceeding a threshold escalated for three-fourths special-majority Board approval before it is entered into+}.',
    reasoning:
      'To operationalise the Notice, exposures must be aggregated per related party group and tested against Board-set materiality thresholds, triggering the special-majority approval process — periodic credit-team review is insufficient.',
  },
  {
    docName: 'Board Governance & Conflicts of Interest Charter',
    section: 'Clause 6 — Abstention from voting',
    original:
      'A director with an interest in a related party transaction shall not vote on that transaction.',
    redline:
      'A director with an interest in a related party transaction shall [-not vote on that transaction-] {+abstain from voting on that transaction and be excluded from the total number of directors used to determine the three-fourths special majority required for approval+}.',
    reasoning:
      'Under the Notice an interested director must abstain, and the three-fourths majority is counted on the total board excluding abstaining directors — the charter must state both the abstention and the counting basis.',
  },
  {
    docName: 'Regulatory Reporting Procedures Manual',
    section: 'Item 9 — Related party transaction register',
    original:
      'A summary of related party transactions is filed annually for internal record-keeping.',
    redline:
      'A [-summary of related party transactions is filed annually for internal record-keeping-] {+register of related party transactions is maintained, recording the approval obtained and the identity of any director who abstained from voting, and is reported to the Board each quarter+}.',
    reasoning:
      'Adequate oversight under the Notice requires a maintained register capturing each approval and any abstaining directors, reported to the Board — an annual internal summary does not provide sufficient governance evidence.',
  },
]

function hash(str) {
  let h = 0
  for (let i = 0; i < str.length; i += 1) {
    h = (h * 31 + str.charCodeAt(i)) & 0xffffffff
  }
  return Math.abs(h)
}

// Returns a stable list of mock affected-document suggestions for a regulation,
// shaped to match the backend suggestion payload consumed by <SuggestionCard>.
// Used as a fallback when the API returns no real suggestions so the UI always
// has something to demo. Deterministic per regulation, always at least one item.
export function mockSuggestionsFor(doc) {
  const key = doc?.id || doc?.source_url || doc?.title || 'mock'
  const h = hash(String(key))
  const count = 1 + (h % 3) // 1–3 affected documents
  const results = []
  for (let i = 0; i < count; i += 1) {
    const base = INTERNAL_DOCS[(h + i * 7) % INTERNAL_DOCS.length]
    // Similarity between 0.71 and 0.95, stable per (regulation, index).
    const similarity = 0.71 + (((h >> (i + 1)) % 25) / 100)
    results.push({
      id: `mock-${key}-${i}`,
      regulation_clause_reference: `${base.docName} — ${base.section}`,
      similarity_score: similarity,
      impact_score: similarity >= 0.85 ? 8 : 5,
      legal_reasoning: base.reasoning,
      redline_diff: base.redline,
      statutory_citations: ['MAS Notice 643'],
      status: 'pending',
    })
  }
  return results
}
