import axios from 'axios'

/**
 * Single Axios instance for the Flask API.
 *
 * Requests are relative (/api/...) so the same build works behind the Vite dev
 * proxy and behind Flask in production. Every failure is normalised into an
 * ApiError with a human-readable message, so components never show raw stack
 * traces or server internals.
 */
const client = axios.create({
  baseURL: '/api',
  timeout: 120000,
  headers: { Accept: 'application/json' },
})

export class ApiError extends Error {
  constructor(message, { code = 'error', status = 0, hint = '', details = {} } = {}) {
    super(message)
    this.name = 'ApiError'
    this.code = code
    this.status = status
    this.hint = hint
    this.details = details
  }
}

client.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.code === 'ECONNABORTED') {
      throw new ApiError('The request timed out. Large documents can take a while — try again.', {
        code: 'timeout',
      })
    }
    if (!error.response) {
      throw new ApiError(
        'Cannot reach the VeriText AI server. Check that the backend is running.',
        { code: 'network_error' },
      )
    }
    const payload = error.response.data || {}
    const detail = payload.error || {}
    throw new ApiError(detail.message || `Request failed (${error.response.status}).`, {
      code: detail.code || 'http_error',
      status: error.response.status,
      hint: detail.hint || '',
      details: detail.details || {},
    })
  },
)

const unwrap = (response) => response.data?.data ?? response.data

/* ------------------------------------------------------------------ health */
export const getHealth = () => client.get('/health').then(unwrap)

/* --------------------------------------------------------------- documents */
export const uploadDocument = (file, label, onProgress) => {
  const form = new FormData()
  form.append('file', file)
  form.append('label', label)
  return client
    .post('/documents/upload', form, {
      headers: { 'Content-Type': 'multipart/form-data' },
      onUploadProgress: (event) => {
        if (onProgress && event.total) {
          onProgress(Math.round((event.loaded / event.total) * 100))
        }
      },
    })
    .then(unwrap)
}

export const deleteDocument = (documentId) =>
  client.delete(`/documents/${documentId}`).then(unwrap)

/* ---------------------------------------------------------------- analysis */
export const compareDocuments = ({ docAId, docBId, options }) =>
  client
    .post('/analysis/compare', { doc_a_id: docAId, doc_b_id: docBId, options })
    .then(unwrap)

export const getAnalysis = (analysisId) => client.get(`/analysis/${analysisId}`).then(unwrap)

export const getAnalysisDocuments = (analysisId) =>
  client.get(`/analysis/${analysisId}/documents`).then(unwrap)

export const getHistory = ({ limit = 20, offset = 0, search = '' } = {}) =>
  client
    .get('/analysis/history', { params: { limit, offset, ...(search ? { search } : {}) } })
    .then(unwrap)

export const deleteAnalysis = (analysisId) =>
  client.delete(`/analysis/${analysisId}`).then(unwrap)

export const getDashboardStats = () => client.get('/stats/dashboard').then(unwrap)

/* Absolute URLs are needed for browser downloads (report / export). */
export const reportUrl = (analysisId) => `/api/analysis/${analysisId}/report`
export const exportUrl = (analysisId) => `/api/analysis/${analysisId}/export`

export default client
