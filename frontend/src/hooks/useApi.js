import { useCallback, useEffect, useRef, useState } from 'react'

/** Loads data from an API call with loading/error state and manual reload. */
export function useApi(fn, deps = [], { enabled = true } = {}) {
  const [state, set] = useState({ data: null, error: null, loading: enabled })
  const alive = useRef(true)
  const load = useCallback(() => {
    set((s) => ({ ...s, loading: true, error: null }))
    return fn().then((data) => alive.current && set({ data, error: null, loading: false }))
      .catch((error) => alive.current && set({ data: null, error, loading: false }))
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps)
  useEffect(() => { alive.current = true; if (enabled) load(); return () => { alive.current = false } }, [load, enabled])
  return { ...state, reload: load }
}
