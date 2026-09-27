import { afterEach, describe, expect, it, vi } from 'vitest'
import { api, ApiError, BASE_URL } from './api.js'

function mockFetch(status, body) {
  const fetchMock = vi.fn().mockResolvedValue({
    ok: status >= 200 && status < 300,
    status,
    statusText: 'status text',
    text: () => Promise.resolve(JSON.stringify(body)),
  })
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('repository API client', () => {
  it('posts only the path to /repository/configure', async () => {
    const selection = { path: 'D:\\repo', repo_root: 'D:\\repo', branch: 'main', is_default: false }
    const fetchMock = mockFetch(200, selection)

    await expect(api.configureRepository('D:\\repo')).resolves.toEqual(selection)

    const [url, options] = fetchMock.mock.calls[0]
    expect(url).toBe(`${BASE_URL}/repository/configure`)
    expect(options.method).toBe('POST')
    expect(JSON.parse(options.body)).toEqual({ path: 'D:\\repo' })
  })

  it('raises an ApiError carrying the backend detail when configuration fails', async () => {
    mockFetch(400, { detail: "'D:\\missing' does not exist" })

    const error = await api.configureRepository('D:\\missing').catch((err) => err)
    expect(error).toBeInstanceOf(ApiError)
    expect(error.status).toBe(400)
    expect(error.message).toBe("'D:\\missing' does not exist")
  })

  it('reads the current selection from /repository', async () => {
    const fetchMock = mockFetch(200, { path: 'D:\\demo', is_default: true })
    await api.currentRepository()
    expect(fetchMock.mock.calls[0][0]).toBe(`${BASE_URL}/repository`)
  })
})
