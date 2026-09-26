import { describe, expect, it } from 'vitest'
import { parseStatusMismatch } from './testResult.js'

describe('parseStatusMismatch', () => {
  it('extracts actual and expected status codes from a pytest assertion message', () => {
    expect(parseStatusMismatch('assert 500 == 401')).toEqual({ actual: 500, expected: 401 })
  })

  it('returns null for messages without a status-code assertion', () => {
    expect(
      parseStatusMismatch('An expired token must be rejected with 401 Unauthorized'),
    ).toBeNull()
  })

  it('returns null for empty input', () => {
    expect(parseStatusMismatch(undefined)).toBeNull()
    expect(parseStatusMismatch('')).toBeNull()
  })
})
