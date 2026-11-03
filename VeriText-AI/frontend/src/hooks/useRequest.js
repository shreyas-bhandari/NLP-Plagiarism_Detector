import { useCallback, useEffect, useRef, useState } from 'react'

/**
 * Small data-fetching hook: loading / error / data plus a manual `reload`.
 * Requests are cancelled (ignored) when the component unmounts or the key changes.
 */
export function useRequest(request, deps = [], { skip = false } = {}) {
  const [state, setState] = useState({ data: null, loading: !skip, error: null })
  const requestRef = useRef(request)
  requestRef.current = request
  const aliveRef = useRef(true)

  useEffect(() => {
    aliveRef.current = true
    return () => {
      aliveRef.current = false
    }
  }, [])

  const run = useCallback(async () => {
    setState((prev) => ({ ...prev, loading: true, error: null }))
    try {
      const data = await requestRef.current()
      if (aliveRef.current) setState({ data, loading: false, error: null })
      return data
    } catch (error) {
      if (aliveRef.current) setState({ data: null, loading: false, error })
      return null
    }
  }, [])

  useEffect(() => {
    if (skip) {
      setState({ data: null, loading: false, error: null })
      return
    }
    run()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps)

  return { ...state, reload: run, setData: (data) => setState((prev) => ({ ...prev, data })) }
}

export default useRequest
