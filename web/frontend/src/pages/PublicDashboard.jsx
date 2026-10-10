import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  ArrowClockwise,
  ChartLine,
  LockSimple,
  MapPin,
  ShieldCheck,
} from '@phosphor-icons/react'
import { api } from '../lib/api'
import { activityLevelClass, fmtInt } from '../lib/format'
import { KpiCard, KpiHero } from '../components/KpiCard'
import { CameraMap } from '../components/MapView'
import { CameraChart, DailyChart, HourlyChart } from '../components/charts'

function DashboardSkeleton() {
  return (
    <div className="grid">
      <div className="col-5">
        <div className="panel skeleton skeleton--block" style={{ height: 196 }} />
      </div>
      <div className="col-7">
        <div className="grid">
          {[0, 1, 2, 3].map((key) => (
            <div className="col-6" key={key}>
              <div className="panel skeleton" style={{ height: 92 }} />
            </div>
          ))}
        </div>
      </div>
      <div className="col-7">
        <div className="panel skeleton" style={{ height: 480 }} />
      </div>
      <div className="col-5">
        <div className="panel skeleton" style={{ height: 480 }} />
      </div>
    </div>
  )
}

export function PublicDashboard() {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  const load = useCallback(() => {
    setLoading(true)
    setError(null)

    Promise.all([
      api('/analytics/summary'),
      api('/cameras'),
      api('/analytics/cameras'),
      api('/analytics/trends'),
      api('/analytics/insights'),
    ])
      .then(([summary, cameras, cameraStats, trends, insights]) => {
        setData({
          summary,
          cameras: cameras.cameras,
          cameraStats: cameraStats.cameras,
          trends,
          insights: insights.insights,
        })
      })
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false))
  }, [])

  useEffect(() => {
    load()
  }, [load])

  const summary = data?.summary

  return (
    <>
      <div className="page-head">
        <div>
          <span className="eyebrow reveal">Public access · aggregated data</span>
          <h1 className="page-title reveal">Traffic Overview</h1>
          <p className="page-sub reveal">
            City-wide ANPR analytics from the simulated Hyderabad camera
            network. Public pages show aggregates only — vehicle-level data
            requires operator login.
          </p>
        </div>
        <button
          type="button"
          className="btn btn--ghost btn--sm reveal"
          onClick={load}
          disabled={loading}
        >
          <ArrowClockwise size={14} />
          Refresh
        </button>
      </div>

      {error && (
        <div className="alert alert--error reveal">
          <span>Could not load analytics: {error}</span>
          <button type="button" className="btn btn--ghost btn--sm" onClick={load}>
            Retry
          </button>
        </div>
      )}

      {loading && !data && <DashboardSkeleton />}

      {data && (
        <div className="grid">
          <div className="col-5">
            <KpiHero
              label="Total recorded observations"
              value={summary.total_observations}
              foot={
                <>
                  <span>
                    Window{' '}
                    {summary.first_seen && summary.last_seen
                      ? `${summary.first_seen} → ${summary.last_seen}`
                      : 'awaiting data'}
                  </span>
                  <span className={activityLevelClass(summary.traffic_activity)}>
                    <span className="level__dot" />
                    {summary.traffic_activity}
                  </span>
                </>
              }
            />
          </div>

          <div className="col-7">
            <div className="grid">
              <div className="col-6">
                <KpiCard
                  label="Unique vehicles"
                  value={summary.unique_vehicles}
                  hint="Distinct plate identities recorded"
                />
              </div>
              <div className="col-6">
                <KpiCard
                  label="Active cameras"
                  value={summary.active_cameras}
                  hint={`of ${summary.total_cameras} network locations`}
                />
              </div>
              <div className="col-6">
                <KpiCard
                  label="Multi-camera vehicles"
                  value={summary.multi_camera_vehicles}
                  hint="Observed at more than one junction"
                />
              </div>
              <div className="col-6">
                <div className="panel panel--interactive reveal kpi-card">
                  <span className="kpi-card__label">Traffic activity</span>
                  <span
                    className={activityLevelClass(summary.traffic_activity)}
                    style={{ fontSize: 22 }}
                  >
                    <span className="level__dot" />
                    {summary.traffic_activity}
                  </span>
                  <span className="kpi-card__hint">
                    Observation-count indicator, not congestion
                  </span>
                </div>
              </div>
            </div>
          </div>

          <div className="col-7">
            <div className="panel reveal">
              <div className="panel__head">
                <h2 className="panel__title">Camera network — Hyderabad</h2>
                <span className="panel__meta">
                  {data.cameras.length} locations · recorded points
                </span>
              </div>
              <CameraMap
                cameras={data.cameras}
                stats={data.cameraStats}
              />
              <div className="panel__foot">
                Markers show junction-level coordinates of the simulated
                network. Vehicle trajectories are operator-only.
              </div>
            </div>
          </div>

          <div className="col-5">
            <div className="panel reveal">
              <div className="panel__head">
                <h2 className="panel__title">Camera-wise observations</h2>
                <span className="panel__meta">by camera id</span>
              </div>
              {data.cameraStats.length ? (
                <CameraChart data={data.cameraStats} />
              ) : (
                <div className="empty-state">
                  <MapPin size={22} />
                  <span className="empty-state__title">No observations yet</span>
                  <span className="empty-state__hint">
                    Run ANPR detection from the operator console to populate
                    camera analytics.
                  </span>
                </div>
              )}
            </div>
          </div>

          <div className="col-7">
            <div className="panel reveal">
              <div className="panel__head">
                <h2 className="panel__title">Activity by hour</h2>
                <span className="panel__meta">
                  {data.trends.peak_hour !== null
                    ? `peak ${String(data.trends.peak_hour).padStart(2, '0')}:00 · ${data.trends.peak_hour_observations} obs`
                    : 'no data'}
                </span>
              </div>
              <HourlyChart data={data.trends.hourly} />
            </div>
          </div>

          <div className="col-5">
            <div className="panel reveal">
              <div className="panel__head">
                <h2 className="panel__title">System insights</h2>
                <span className="panel__meta">derived automatically</span>
              </div>
              <ol className="insight-list">
                {data.insights.map((insight, index) => (
                  <li className="insight-list__item" key={insight}>
                    <span className="insight-list__index">
                      {String(index + 1).padStart(2, '0')}
                    </span>
                    <span>{insight}</span>
                  </li>
                ))}
              </ol>
              <div className="panel__foot">
                Insights are computed from recorded ANPR observations in the
                current dataset.
              </div>
            </div>
          </div>

          <div className="col-8">
            <div className="panel reveal">
              <div className="panel__head">
                <h2 className="panel__title">Observations by day</h2>
                <span className="panel__meta">recorded history</span>
              </div>
              {data.trends.daily.length ? (
                <DailyChart data={data.trends.daily} />
              ) : (
                <div className="empty-state">
                  <ChartLine size={22} />
                  <span className="empty-state__title">No daily data</span>
                </div>
              )}
            </div>
          </div>

          <div className="col-4">
            <div className="panel reveal">
              <div className="panel__head">
                <h2 className="panel__title">Access levels</h2>
                <span className="panel__meta">privacy by design</span>
              </div>
              <ul className="access-list">
                <li className="access-list__item">
                  <ShieldCheck size={17} />
                  Public: statistics, camera analysis, charts, insights
                </li>
                <li className="access-list__item access-list__item--locked">
                  <LockSimple size={17} />
                  ANPR detection uploads
                </li>
                <li className="access-list__item access-list__item--locked">
                  <LockSimple size={17} />
                  Number plate details & evidence
                </li>
                <li className="access-list__item access-list__item--locked">
                  <LockSimple size={17} />
                  Multi-camera tracking & vehicle search
                </li>
                <li className="access-list__item access-list__item--locked">
                  <LockSimple size={17} />
                  Map trajectories
                </li>
              </ul>
              <div className="panel__foot">
                Operator accounts are restricted to <span className="mono">.cop@</span>{' '}
                emails.{' '}
                <Link to="/login" style={{ color: 'var(--accent)' }}>
                  Sign in
                </Link>
              </div>
            </div>
          </div>
        </div>
      )}
    </>
  )
}
