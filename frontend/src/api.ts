export type Role = 'admin' | 'member'

export type Account = {
  id: string
  username: string
  role: Role
  status: 'active' | 'pending' | 'disabled'
}

export class ApiError extends Error {
  status: number

  constructor(message: string, status: number) {
    super(message)
    this.status = status
  }
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch('/api/' + path, options)
  const data = await response.json().catch(() => null)
  if (!response.ok) {
    if (response.status === 401 && !path.startsWith('auth/')) {
      window.dispatchEvent(new Event('autumnleaf:session-expired'))
    }
    throw new ApiError(data?.error ?? 'AutumnLeaf could not complete the request.', response.status)
  }
  if (data === null) throw new Error('AutumnLeaf did not receive a response from the server.')
  return data as T
}

export function read<T>(path: string, signal?: AbortSignal) {
  return request<T>(path, { signal })
}

export async function write<T>(path: string, method: 'POST' | 'PATCH', data: object = {}) {
  const { csrfToken } = await read<{ csrfToken: string }>('auth/csrf/')
  return request<T>(path, {
    method,
    headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrfToken },
    body: JSON.stringify(data),
  })
}

export function message(error: unknown) {
  return error instanceof ApiError ? error.message : 'Could not reach AutumnLeaf. Try again.'
}
