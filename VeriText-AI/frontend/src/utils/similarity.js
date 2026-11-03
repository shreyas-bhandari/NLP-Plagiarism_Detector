/**
 * Presentation rules for similarity results.
 *
 * Deliberately centralised: the same band colours and wording appear in the
 * results table, the comparison viewer, the charts and the PDF-related links.
 * Colours follow the product palette — red means "look here", not "guilty".
 */

export const BAND_META = {
  very_high: {
    label: 'Very high',
    range: '90–100%',
    text: 'text-red-700',
    bg: 'bg-red-50',
    border: 'border-red-200',
    dot: 'bg-red-600',
    bar: 'bg-red-600',
    highlight: 'bg-red-100 text-red-900',
  },
  high: {
    label: 'High',
    range: '80–89%',
    text: 'text-red-600',
    bg: 'bg-red-50/70',
    border: 'border-red-200',
    dot: 'bg-red-500',
    bar: 'bg-red-500',
    highlight: 'bg-red-50 text-red-900',
  },
  moderate: {
    label: 'Moderate',
    range: '65–79%',
    text: 'text-amber-700',
    bg: 'bg-amber-50',
    border: 'border-amber-200',
    dot: 'bg-amber-500',
    bar: 'bg-amber-500',
    highlight: 'bg-amber-50 text-amber-900',
  },
  low: {
    label: 'Low',
    range: 'below 65%',
    text: 'text-emerald-700',
    bg: 'bg-emerald-50',
    border: 'border-emerald-200',
    dot: 'bg-emerald-600',
    bar: 'bg-emerald-600',
    highlight: 'bg-emerald-50 text-emerald-900',
  },
}

export const bandMeta = (band) => BAND_META[band] || BAND_META.low

export const CLASSIFICATION_META = {
  exact: {
    label: 'Exact match',
    short: 'Exact',
    description: 'Identical wording after normalising case and punctuation.',
    text: 'text-red-700',
    bg: 'bg-red-50',
    border: 'border-red-200',
    accent: 'bg-red-600',
  },
  near_exact: {
    label: 'Near-exact match',
    short: 'Near-exact',
    description: 'Almost the same word sequence, with a few words added, removed or replaced.',
    text: 'text-amber-700',
    bg: 'bg-amber-50',
    border: 'border-amber-200',
    accent: 'bg-amber-500',
  },
  semantic: {
    label: 'Semantic match',
    short: 'Semantic',
    description: 'Different wording, closely related meaning — the case exact matching cannot see.',
    text: 'text-accent-700',
    bg: 'bg-accent-50',
    border: 'border-accent-200',
    accent: 'bg-accent-500',
  },
  below_threshold: {
    label: 'Below threshold',
    short: 'Below threshold',
    description: 'Similarity below the configured flag threshold.',
    text: 'text-navy-500',
    bg: 'bg-navy-50',
    border: 'border-navy-200',
    accent: 'bg-navy-300',
  },
}

export const classificationMeta = (value) =>
  CLASSIFICATION_META[value] || CLASSIFICATION_META.below_threshold

export const STRENGTH_META = {
  strong: {
    label: 'Strong evidence',
    hint: 'Verbatim overlap, high similarity, or part of a multi-sentence passage.',
    className: 'border-red-200 bg-red-50 text-red-700',
  },
  moderate: {
    label: 'Moderate evidence',
    hint: 'Clear semantic overlap, but not verbatim and not part of a passage.',
    className: 'border-amber-200 bg-amber-50 text-amber-700',
  },
  weak: {
    label: 'Weak evidence',
    hint: 'Generic phrasing or an isolated semantic hit — usually benign.',
    className: 'border-navy-200 bg-navy-50 text-navy-600',
  },
}

export const strengthMeta = (value) => STRENGTH_META[value] || STRENGTH_META.moderate

export const SUPPRESS_REASON_LABELS = {
  generic_academic_phrasing: 'Generic academic phrasing',
  no_shared_content_terms: 'No shared content words',
  citation_context_only: 'Citation context only',
}

/**
 * Document-level bands, mirrors DOCUMENT_BANDS in the backend engine.
 * These apply to the coverage-weighted similarity index (a document-level value),
 * NOT to individual sentences — a 0.745 index is "elevated overlap", while a 0.745
 * sentence cosine is only "moderate".
 */
export const DOCUMENT_BANDS = [
  { level: 'low', label: 'Low overlap', max: 0.1, meta: 'low' },
  { level: 'moderate', label: 'Moderate overlap', max: 0.25, meta: 'low' },
  { level: 'elevated', label: 'Elevated overlap', max: 0.45, meta: 'moderate' },
  { level: 'high', label: 'High overlap', max: Infinity, meta: 'very_high' },
]

export const documentBandFromIndex = (index) => {
  const value = Number(index) || 0
  return DOCUMENT_BANDS.find((band) => value < band.max) || DOCUMENT_BANDS[DOCUMENT_BANDS.length - 1]
}

/** Overall document band (from the API) mapped to palette colours. */
export const documentBandMeta = (level) => {
  switch (level) {
    case 'high':
      return { ...BAND_META.very_high, label: 'High overlap' }
    case 'elevated':
      return { ...BAND_META.moderate, label: 'Elevated overlap' }
    case 'moderate':
      return { ...BAND_META.moderate, label: 'Moderate overlap' }
    default:
      return { ...BAND_META.low, label: 'Low overlap' }
  }
}

/** A stable colour per match index, used to link a pair in the viewer. */
export const MATCH_PALETTE = [
  { bg: 'bg-red-100', ring: 'ring-red-400', text: 'text-red-800', solid: 'bg-red-600' },
  { bg: 'bg-amber-100', ring: 'ring-amber-400', text: 'text-amber-800', solid: 'bg-amber-500' },
  { bg: 'bg-accent-100', ring: 'ring-accent-400', text: 'text-accent-800', solid: 'bg-accent-500' },
  { bg: 'bg-emerald-100', ring: 'ring-emerald-400', text: 'text-emerald-800', solid: 'bg-emerald-600' },
  { bg: 'bg-violet-100', ring: 'ring-violet-400', text: 'text-violet-800', solid: 'bg-violet-500' },
  { bg: 'bg-cyan-100', ring: 'ring-cyan-400', text: 'text-cyan-800', solid: 'bg-cyan-600' },
]

export const matchPalette = (index) => MATCH_PALETTE[Math.abs(index) % MATCH_PALETTE.length]
