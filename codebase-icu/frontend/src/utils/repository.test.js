import { describe, expect, it, vi } from 'vitest'
import { EMPTY_PATH_ERROR, isSameRepository, selectRepository } from './repository.js'
import { ApiError } from '../services/api.js'

const selection = {
  path: 'D:\\CodebaseICU-Validation\\repo-1',
  repo_root: 'D:\\CodebaseICU-Validation\\repo-1',
  branch: 'main',
  is_default: false,
}

describe('selectRepository', () => {
  it('configures the trimmed path and returns the backend selection', async () => {
    const apiClient = { configureRepository: vi.fn().mockResolvedValue(selection) }
    const outcome = await selectRepository(apiClient, '  D:\\CodebaseICU-Validation\\repo-1  ')
    expect(apiClient.configureRepository).toHaveBeenCalledWith('D:\\CodebaseICU-Validation\\repo-1')
    expect(outcome).toEqual({ ok: true, selection })
  })

  it('rejects an empty path without calling the backend', async () => {
    const apiClient = { configureRepository: vi.fn() }
    for (const value of ['', '   ', undefined, null]) {
      expect(await selectRepository(apiClient, value)).toEqual({ ok: false, error: EMPTY_PATH_ERROR })
    }
    expect(apiClient.configureRepository).not.toHaveBeenCalled()
  })

  it('surfaces the backend validation message instead of throwing', async () => {
    const apiClient = {
      configureRepository: vi
        .fn()
        .mockRejectedValue(new ApiError("'D:\\nope' does not exist", 400)),
    }
    expect(await selectRepository(apiClient, 'D:\\nope')).toEqual({
      ok: false,
      error: "'D:\\nope' does not exist",
    })
  })

  it('falls back to a generic message for errors without one', async () => {
    const apiClient = { configureRepository: vi.fn().mockRejectedValue(undefined) }
    const outcome = await selectRepository(apiClient, 'D:\\repo')
    expect(outcome.ok).toBe(false)
    expect(outcome.error).toMatch(/configuration failed/i)
  })
})

describe('isSameRepository', () => {
  it('compares selections by path', () => {
    expect(isSameRepository(selection, { ...selection, branch: 'dev' })).toBe(true)
    expect(isSameRepository(selection, { ...selection, path: 'D:\\other' })).toBe(false)
    expect(isSameRepository(null, selection)).toBe(false)
  })
})
