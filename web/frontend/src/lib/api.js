const TOKEN_KEY = 'anpr_token'
const EMAIL_KEY = 'anpr_email'

export function getToken() {
  return localStorage.getItem(TOKEN_KEY)
}

export function getEmail() {
  return localStorage.getItem(EMAIL_KEY)
}

export function setSession(token, email) {
  localStorage.setItem(TOKEN_KEY, token)
  localStorage.setItem(EMAIL_KEY, email)
  window.dispatchEvent(new Event('anpr:session'))
}

export function clearSession() {
  localStorage.removeItem(TOKEN_KEY)
  localStorage.removeItem(EMAIL_KEY)
  window.dispatchEvent(new Event('anpr:session'))
}

export class ApiError extends Error {
  constructor(message, status) {
    super(message)
    this.status = status
  }
}

async function errorMessage(response) {
  try {
    const data = await response.json()
    if (typeof data.detail === 'string') return data.detail
    if (Array.isArray(data.detail) && data.detail.length) {
      return data.detail[0]?.msg || 'Request failed.'
    }
    return `Request failed (${response.status}).`
  } catch {
    return `Request failed (${response.status}).`
  }
}

export async function api(path, options = {}) {
  const { method = 'GET', body, form, auth = false } = options
  const headers = {}

  if (auth) {
    const token = getToken()
    if (token) headers.Authorization = `Bearer ${token}`
  }

  let payload
  if (form) {
    payload = form
  } else if (body !== undefined) {
    headers['Content-Type'] = 'application/json'
    payload = JSON.stringify(body)
  }

  const response = await fetch(`/api${path}`, { method, headers, body: payload })

  if (response.status === 401 && auth) {
    clearSession()
  }

  if (!response.ok) {
    throw new ApiError(await errorMessage(response), response.status)
  }

  return response.json()
}

export async function apiBlob(path) {
  const token = getToken()
  const headers = token ? { Authorization: `Bearer ${token}` } : {}
  const response = await fetch(`/api${path}`, { headers })

  if (!response.ok) {
    throw new ApiError(await errorMessage(response), response.status)
  }

  return response.blob()
}
