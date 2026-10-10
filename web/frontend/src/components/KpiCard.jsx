import { useEffect, useRef } from 'react'
import { fmtInt } from '../lib/format'
import { gsap, prefersReducedMotion } from '../lib/motion'

function useCountUp(ref, value) {
  useEffect(() => {
    const element = ref.current
    if (!element) return

    if (!Number.isFinite(value) || prefersReducedMotion()) {
      element.textContent = fmtInt(value)
      return undefined
    }

    const state = { value: 0 }

    const tween = gsap.to(state, {
      value,
      duration: 1.15,
      ease: 'power2.out',
      onUpdate: () => {
        element.textContent = fmtInt(Math.round(state.value))
      },
    })

    return () => tween.kill()
  }, [ref, value])
}

export function KpiHero({ label, value, foot }) {
  const valueRef = useRef(null)
  useCountUp(valueRef, value)

  return (
    <div className="panel panel--interactive reveal kpi-hero">
      <span className="kpi-hero__label">{label}</span>
      <span className="kpi-hero__value" ref={valueRef}>
        {fmtInt(value)}
      </span>
      {foot && <span className="kpi-hero__foot">{foot}</span>}
    </div>
  )
}

export function KpiCard({ label, value, hint }) {
  const valueRef = useRef(null)
  useCountUp(valueRef, value)

  return (
    <div className="panel panel--interactive reveal kpi-card">
      <span className="kpi-card__label">{label}</span>
      <span className="kpi-card__value" ref={valueRef}>
        {fmtInt(value)}
      </span>
      {hint && <span className="kpi-card__hint">{hint}</span>}
    </div>
  )
}
