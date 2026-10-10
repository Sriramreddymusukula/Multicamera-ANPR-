import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { ArrowUpRight, List, X } from '@phosphor-icons/react'

const links = [
  ['Home', '#home'],
  ['Platform', '#platform'],
  ['Technology', '#technology'],
  ['Use Cases', '#use-cases'],
  ['About', '#about'],
]

export function MeridianShell({ children }) {
  const [scrolled, setScrolled] = useState(false)
  const [open, setOpen] = useState(false)
  const [active, setActive] = useState('#home')

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 32)
    onScroll()
    window.addEventListener('scroll', onScroll, { passive: true })
    const observer = new IntersectionObserver((entries) => {
      const visible = entries.filter((entry) => entry.isIntersecting)
      if (visible.length) setActive('#' + visible[0].target.id)
    }, { rootMargin: '-30% 0px -60% 0px' })
    const observed = new Set()
    const observeSections = () => {
      links.forEach(([, href]) => {
        const section = document.querySelector(href)
        if (section && !observed.has(section)) {
          observer.observe(section)
          observed.add(section)
        }
      })
      if (observed.size === links.length) mutationObserver.disconnect()
    }
    const mutationObserver = new MutationObserver(observeSections)
    mutationObserver.observe(document.getElementById('main-content'), { childList: true, subtree: true })
    observeSections()
    return () => {
      window.removeEventListener('scroll', onScroll)
      observer.disconnect()
      mutationObserver.disconnect()
    }
  }, [])

  return (
    <div className="meridian">
      <a className="meridian-skip" href="#main-content">Skip to content</a>
      <header className={'meridian-nav' + (scrolled || open ? ' is-scrolled' : '')}>
        <a className="meridian-brand" href="#home" onClick={() => setOpen(false)} aria-label="Meridian home">
          <span className="meridian-brand__symbol" aria-hidden="true"><i /><i /><i /></span>
          <span><strong>MERIDIAN</strong><small>CITY INTELLIGENCE</small></span>
        </a>
        <nav className={'meridian-nav__links' + (open ? ' is-open' : '')} aria-label="Main navigation">
          {links.map(([label, href]) => <a key={href} href={href} aria-current={active === href ? 'page' : undefined} onClick={() => setOpen(false)}>{label}</a>)}
          <Link className="meridian-nav__mobile-cta" to="/console" onClick={() => setOpen(false)}>Launch Console <ArrowUpRight /></Link>
        </nav>
        <Link className="meridian-nav__cta" to="/console">Launch Console <ArrowUpRight size={17} /></Link>
        <button className="meridian-nav__toggle" type="button" aria-label={open ? 'Close menu' : 'Open menu'} aria-expanded={open} onClick={() => setOpen((value) => !value)}>{open ? <X size={22} /> : <List size={22} />}</button>
      </header>
      <main id="main-content">{children}</main>
    </div>
  )
}
