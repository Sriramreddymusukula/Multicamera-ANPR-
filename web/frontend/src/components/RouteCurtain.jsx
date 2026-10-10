import { useRef } from 'react'
import { useLocation } from 'react-router-dom'
import { useGSAP } from '@gsap/react'
import { gsap } from '../lib/motion'
import '../styles/route-curtain.css'

const operationalRoutes = new Set(['/overview', '/console', '/reviews'])

export function RouteCurtain() {
  const { pathname } = useLocation()
  const curtain = useRef(null)
  const enabled = operationalRoutes.has(pathname)
  const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches

  useGSAP(() => {
    if (!enabled || reducedMotion || !curtain.current) return
    const label = curtain.current.querySelector('.route-curtain__label')
    gsap.timeline({ defaults: { ease: 'power3.inOut' } })
      .fromTo(label, { autoAlpha: 0, y: 16 }, { autoAlpha: 1, y: 0, duration: 0.32 })
      .to(curtain.current, { xPercent: -102, duration: 0.9 }, 0.18)
  }, { scope: curtain, dependencies: [pathname, reducedMotion], revertOnUpdate: true })

  if (!enabled || reducedMotion) return null

  return (
    <div className="route-curtain" ref={curtain} aria-hidden="true">
      <div className="route-curtain__label">
        <span>MERIDIAN</span>
        <small>CITY INTELLIGENCE / OPERATIONAL VIEW</small>
      </div>
    </div>
  )
}
