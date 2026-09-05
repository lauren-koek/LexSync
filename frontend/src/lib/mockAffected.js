// MOCK DATA — placeholder for the future vector-search + redline pipeline.
//
// Later, when a regulatory change is ingested, we'll embed it and run a vector
// search over internal documents to find likely-affected clauses, then ask the
// LLM to propose a redline fix for each. Until that exists, this module fabricates
// a stable, plausible set of "affected documents" for a given regulation so the
// UI can be built and demoed. Results are deterministic per regulation id.

const INTERNAL_DOCS = [
  {
    docName: 'Client Onboarding & KYC Policy',
    section: 'Clause 4.2 — Counterparty exposure limits',
    original:
      'Aggregate exposure to a single counterparty group shall not exceed 30% of eligible capital.',
    redline:
      'Aggregate exposure to a single counterparty group shall not exceed [-30%-] {+25%+} of eligible capital{+, measured on a look-through basis to connected parties+}.',
  },
  {
    docName: 'Credit Risk Management Framework',
    section: 'Section 7 — Large exposure reporting',
    original:
      'Large exposures are reported to the risk committee on a quarterly basis.',
    redline:
      'Large exposures are reported to the risk committee on a [-quarterly-] {+monthly+} basis{+, with breaches escalated within 2 business days+}.',
  },
  {
    docName: 'AML/CFT Procedures Manual',
    section: 'Clause 12 — Suspicious transaction reporting',
    original:
      'Suspicious transactions must be reported to the MLRO within five business days.',
    redline:
      'Suspicious transactions must be reported to the MLRO within [-five-] {+two+} business days.',
  },
  {
    docName: 'Vendor Data Processing Agreement',
    section: 'Clause 8 — Data retention & breach notification',
    original:
      'The Vendor shall retain processing logs for thirty-six (36) months and notify the Company of any material breach within seventy-two (72) hours.',
    redline:
      'The Vendor shall retain processing logs for [-thirty-six (36)-] {+eighty-four (84)+} months and notify the Company of any material breach within [-seventy-two (72)-] {+twenty-four (24)+} hours.',
  },
  {
    docName: 'Capital Adequacy Internal Guideline',
    section: 'Section 3 — Group capital framework',
    original:
      'Designated financial holding companies maintain a minimum total capital ratio of 10%.',
    redline:
      'Designated financial holding companies maintain a minimum total capital ratio of [-10%-] {+12%+}{+, inclusive of a capital conservation buffer+}.',
  },
  {
    docName: 'Misconduct Reporting SOP',
    section: 'Clause 5 — Reporting channels',
    original:
      'Misconduct is reported through the legacy incident portal.',
    redline:
      'Misconduct is reported through the [-legacy incident portal-] {+centralised MAS-aligned reporting system+}{+, effective 1 January 2027+}.',
  },
  {
    docName: 'Payment Services Compliance Checklist',
    section: 'Item 9 — Stablecoin issuance controls',
    original:
      'Stablecoin reserves are reviewed annually by an external auditor.',
    redline:
      'Stablecoin reserves are reviewed [-annually-] {+monthly+} by an external auditor{+ and attested to MAS+}.',
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
