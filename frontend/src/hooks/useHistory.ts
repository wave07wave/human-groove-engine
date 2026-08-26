import { useCallback, useState } from 'react'

export function useHistory<T>(initial: T | null, limit = 20) {
  const [past, setPast] = useState<T[]>([])
  const [present, setPresent] = useState<T | null>(initial)
  const [future, setFuture] = useState<T[]>([])
  const commit = useCallback((value: T) => {
    setPresent(current => { if (current) setPast(items => [...items.slice(-(limit - 1)), current]); return value })
    setFuture([])
  }, [limit])
  // Server-derived analysis belongs to the current edit and must not create
  // another Undo step.
  const replace = useCallback((value: T) => setPresent(value), [])
  const undo = useCallback(() => setPast(items => {
    const value = items.at(-1); if (!value) return items
    setPresent(current => { if (current) setFuture(next => [current, ...next]); return value }); return items.slice(0, -1)
  }), [])
  const redo = useCallback(() => setFuture(items => {
    const [value, ...rest] = items; if (!value) return items
    setPresent(current => { if (current) setPast(prev => [...prev, current]); return value }); return rest
  }), [])
  return { present, commit, replace, undo, redo, canUndo: !!past.length, canRedo: !!future.length }
}
