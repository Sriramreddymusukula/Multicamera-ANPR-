import { useEffect, useRef, useState } from 'react'
import { Link, NavLink, Outlet, useLocation } from 'react-router-dom'
import {
  List,
  LockSimple,
  SignIn,
  SignOut,
} from '@phosphor-icons/react'
import { api } from '../lib/api'
import { useAuth } from '../lib/auth'
import { activityLevelClass, fmtInt } from '../lib/format'
import { useReveal } from '../lib/motion'
import { enableReviewSound } from '../lib/reviewSound'
import { Ticker } from './Ticker'
import { MeridianShell } from './MeridianShell'
import '../styles/workspace.css'

const NAV = [
  { to: '/', label: 'Meridian', end: true },
  { to: '/overview', label: 'Overview' },
  { to: '/console', label: 'Console', locked: true },
  { to: '/reviews', label: 'Review', locked: true },
  { to: '/search', label: 'Vehicle Search', locked: true },
  { to: '/tracking', label: 'Tracking', locked: true },
]

const TITLES = {
  '/': 'Overview',
  '/overview': 'Network Overview',
  '/login': 'Operator Login',
  '/register': 'Operator Registration',
  '/console': 'ANPR Console',
  '/reviews': 'Observation Review',
  '/search': 'Vehicle Search',
  '/tracking': 'Multi-Camera Tracking',
}

function BrandMark() {
  return (
    <svg className="brand__mark" viewBox="0 0 32 32" aria-hidden="true">
      <path d="M3 25V7l7 12 6-12v18" fill="none" stroke="var(--accent)" strokeWidth="2" strokeLinejoin="round" />
      <path d="M19 25V7l5 9 5-9v18" fill="none" stroke="var(--accent)" strokeWidth="2" strokeLinejoin="round" />
    </svg>
  )
}

export function Layout() {
  const { isAuthed, email, logout } = useAuth()
  const location = useLocation()
  const isMeridian = location.pathname === '/'
  const mainRef = useRef(null)
  const [summary, setSummary] = useState(null)
  const [menuOpen, setMenuOpen] = useState(false)

  useReveal(mainRef, [location.pathname])

  useEffect(() => {
    const unlock = () => { void enableReviewSound() }
    window.addEventListener('pointerdown', unlock)
    window.addEventListener('keydown', unlock)
    return () => {
      window.removeEventListener('pointerdown', unlock)
      window.removeEventListener('keydown', unlock)
    }
  }, [])

  useEffect(() => {
    let active = true

    api('/analytics/summary')
      .then((data) => {
        if (active) setSummary(data)
      })
      .catch(() => {})

    return () => {
      active = false
    }
  }, [location.pathname])

  useEffect(() => {
    setMenuOpen(false)
    document.title = isMeridian ? 'Meridian — City Intelligence' : `${TITLES[location.pathname] || 'Command Centre'} · Meridian`
  }, [location.pathname, isMeridian])

  if (isMeridian) {
    return <MeridianShell><Outlet /></MeridianShell>
  }

  const tickerItems = summary
    ? [
        { label: 'Total observations', value: fmtInt(summary.total_observations) },
        { label: 'Unique vehicles', value: fmtInt(summary.unique_vehicles) },
        {
          label: 'Active cameras',
          value: `${summary.active_cameras}/${summary.total_cameras}`,
        },
        {
          label: 'Multi-camera vehicles',
          value: fmtInt(summary.multi_camera_vehicles),
        },
        { label: 'Activity', value: summary.traffic_activity },
        {
          label: 'Window',
          value:
            summary.first_seen && summary.last_seen
              ? `${summary.first_seen} → ${summary.last_seen}`
              : 'Awaiting data',
        },
      ]
    : [{ label: 'Telemetry', value: 'Syncing…' }]

  return (
    <div className="workspace-shell">
      <header className="topbar">
        <Link to="/" className="brand" aria-label="Meridian home">
          <BrandMark />
          <span className="brand__text">
            <span className="brand__name">MERIDIAN</span>
            <span className="brand__sub">City Intelligence · Hyderabad</span>
          </span>
        </Link>

        <nav className="nav" aria-label="Primary">
          {NAV.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              className={({ isActive }) =>
                `nav__link${isActive ? ' is-active' : ''}`
              }
            >
              {item.label}
              {item.locked && !isAuthed && (
                <LockSimple size={12} className="nav__lock" />
              )}
            </NavLink>
          ))}
        </nav>

        <div className="topbar__actions">
          {isAuthed ? (
            <>
              <span className="operator-chip" title={email || ''}>
                <span className="operator-chip__dot" />
                <span className="operator-chip__email">{email}</span>
              </span>
              <button
                type="button"
                className="btn btn--ghost btn--sm"
                onClick={logout}
              >
                <SignOut size={14} />
                Sign out
              </button>
            </>
          ) : (
            <Link to="/login" className="btn btn--primary btn--sm">
              <SignIn size={14} />
              Operator login
            </Link>
          )}

          <button
            type="button"
            className="menu-toggle"
            aria-label="Toggle navigation"
            aria-expanded={menuOpen}
            onClick={() => setMenuOpen((open) => !open)}
          >
            <List size={18} />
          </button>
        </div>
      </header>

      {menuOpen && (
        <nav className="mobile-menu" aria-label="Mobile">
          {NAV.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              className={({ isActive }) =>
                `nav__link${isActive ? ' is-active' : ''}`
              }
            >
              {item.label}
              {item.locked && !isAuthed && (
                <LockSimple size={12} className="nav__lock" />
              )}
            </NavLink>
          ))}
        </nav>
      )}

      <div className="statusbar">
        <span className="statusbar__state">
          <span className="pulse-dot" />
          Simulated camera network · recorded observations only
        </span>
        <span className="statusbar__right">
          <span className="statusbar__item">
            Records <strong>{fmtInt(summary?.total_observations)}</strong>
          </span>
          <span className="statusbar__item">
            Cameras{' '}
            <strong>
              {summary ? `${summary.active_cameras}/${summary.total_cameras}` : '—'}
            </strong>
          </span>
          <span className="statusbar__item">
            Updated <strong>{summary?.last_seen || '—'}</strong>
          </span>
          <span className={activityLevelClass(summary?.traffic_activity)}>
            <span className="level__dot" />
            {summary?.traffic_activity || 'NO DATA'}
          </span>
        </span>
      </div>

      <Ticker items={tickerItems} />

      <main className="page" ref={mainRef}>
        <Outlet />
      </main>

      <footer className="footer">
        <p className="footer__note">
          Prototype analytics for a simulated four-camera ANPR network in
          Hyderabad. Vehicle routes are reconstructed from recorded detection
          observations — this is not live CCTV tracking, and no plate data is
          exposed on public pages.
        </p>
        <p className="footer__mono">
          CAM-01…CAM-04 · Map © OpenStreetMap contributors
        </p>
      </footer>
    </div>
  )
}
