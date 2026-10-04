import { useEffect, useRef, useState } from 'react'

// Tracks an element's rendered width so SVG charts can lay out at real pixel size.
export default function useElementWidth(fallback = 600) {
  const ref = useRef(null)
  const [width, setWidth] = useState(fallback)

  useEffect(() => {
    const element = ref.current
    if (!element) return undefined
    setWidth(element.clientWidth || fallback)
    if (typeof ResizeObserver === 'undefined') return undefined
    const observer = new ResizeObserver((entries) => {
      const next = Math.round(entries[0].contentRect.width)
      if (next > 0) setWidth(next)
    })
    observer.observe(element)
    return () => observer.disconnect()
  }, [fallback])

  return [ref, width]
}
