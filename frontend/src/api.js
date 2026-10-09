const TOKEN_KEY = 'leadflow_admin_token'

export const getToken = () => {
  try {
    return sessionStorage.getItem(TOKEN_KEY)
  } catch {
    return null
  }
}
const setToken = (value) => {
  try {
    value ? sessionStorage.setItem(TOKEN_KEY, value) : sessionStorage.removeItem(TOKEN_KEY)
  } catch {
    /* storage can be blocked; the session then lasts until reload */
  }
}

export class ApiError extends Error {
  constructor(message, status) {
    super(message)
    this.status = status
  }
}

let onUnauthorised = () => {}
export const setUnauthorisedHandler = (fn) => {
  onUnauthorised = fn
}

export async function api(path, { method = 'GET', body } = {}) {
  const token = getToken()
  const response = await fetch(`/api${path}`, {
    method,
    headers: { 'Content-Type': 'application/json', ...(token ? { Authorization: `Bearer ${token}` } : {}) },
    body: body === undefined ? undefined : JSON.stringify(body),
  })
  if (response.status === 204) return null
  const data = await response.json().catch(() => ({}))
  if (!response.ok) {
    if (response.status === 401 && path !== '/admin/login') onUnauthorised()
    let detail = data.detail
    if (Array.isArray(detail)) detail = detail.map((d) => d.msg).join(' ')
    throw new ApiError(typeof detail === 'string' ? detail : `Request failed (${response.status})`, response.status)
  }
  return data
}

export async function login(password) {
  const { token } = await api('/admin/login', { method: 'POST', body: { password } })
  setToken(token)
}

export const logout = () => setToken(null)
