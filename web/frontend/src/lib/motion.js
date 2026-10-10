import { useGSAP } from '@gsap/react'
import gsap from 'gsap'

gsap.registerPlugin(useGSAP)

export function prefersReducedMotion() {
  return (
    typeof window !== 'undefined' &&
    window.matchMedia('(prefers-reduced-motion: reduce)').matches
  )
}

/**
 * Choreographed entrance for a page: staggers every ".reveal"
 * descendant of the scope. Skipped entirely for reduced motion
 * (elements are visible by default, GSAP only animates them in).
 */
export function useReveal(scopeRef, dependencies = []) {
  useGSAP(
    () => {
      if (!scopeRef.current || prefersReducedMotion()) return

      const targets = gsap.utils.toArray('.reveal', scopeRef.current)
      if (!targets.length) return

      gsap.fromTo(
        targets,
        { autoAlpha: 0, y: 16 },
        {
          autoAlpha: 1,
          y: 0,
          duration: 0.55,
          ease: 'power3.out',
          stagger: 0.055,
          overwrite: 'auto',
          clearProps: 'transform',
        },
      )
    },
    { scope: scopeRef, dependencies },
  )
}

export { gsap }
