import { useEffect, useState } from 'react'

export async function fetchJson(path) {
  const res = await fetch(path)
  if (!res.ok) throw new Error(`${path}: ${res.status}`)
  return res.json()
}

/** Fetch once (or poll every `interval` ms when set). */
export function useApi(path, interval = 0) {
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)
  useEffect(() => {
    if (!path) return undefined
    let alive = true
    const load = () =>
      fetchJson(path)
        .then((d) => alive && setData(d))
        .catch((e) => alive && setError(e))
    load()
    if (interval > 0) {
      const id = setInterval(load, interval)
      return () => { alive = false; clearInterval(id) }
    }
    return () => { alive = false }
  }, [path, interval])
  return { data, error }
}

export const LINE_COLORS = {
  'Line 1': '#22d3ee',
  'Line 2': '#818cf8',
  'Line 3': '#f87171',
  'Line 4': '#34d399',
}
export const PALETTE = ['#22d3ee', '#818cf8', '#34d399', '#fbbf24', '#f87171', '#e879f9', '#94a3b8']
