const sessionKey = 'hge-embodied-session-v1'
let memorySessionId: string | null = null

/** Returns a stable anonymous identifier without requiring account data. */
export function anonymousSessionId() {
  let storage: Storage | null = null
  try { storage = globalThis.localStorage ?? null } catch { storage = null }
  const existing = storage?.getItem(sessionKey)
  if (existing) return existing
  if (memorySessionId) return memorySessionId
  const value = globalThis.crypto?.randomUUID?.().replaceAll('_', '-') ?? `session-${Date.now()}-${Math.random().toString(36).slice(2)}`
  try { storage?.setItem(sessionKey, value) } catch { /* In-memory fallback for private/test contexts. */ }
  memorySessionId = value
  return value
}
