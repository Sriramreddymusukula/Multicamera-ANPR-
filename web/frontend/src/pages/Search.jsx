import { useCallback, useEffect, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import {
  ArrowsClockwise,
  MagnifyingGlass,
  MapPin,
  WarningCircle,
} from '@phosphor-icons/react'
import { api } from '../lib/api'
import { fmtPercent } from '../lib/format'
import { EvidenceThumb } from '../components/EvidenceThumb'
import { CameraMap, RouteOverlay } from '../components/MapView'

function RouteChips({ path }) {
  return (
    <span className="route-chips">
      {path.map((cameraId, index) => (
        <span key={`${cameraId}-${index}`} style={{ display: 'contents' }}>
          <span className="chip chip--cyan">{cameraId}</span>
          {index < path.length - 1 && (
            <span className="route-chips__arrow">→</span>
          )}
        </span>
      ))}
    </span>
  )
}

export function Search() {
  const [params, setParams] = useSearchParams()
  const [query, setQuery] = useState(params.get('plate') || '')
  const [result, setResult] = useState(null)
  const [trajectory, setTrajectory] = useState(null)
  const [cameras, setCameras] = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [replayKey, setReplayKey] = useState(0)

  useEffect(() => {
    api('/cameras')
      .then((data) => setCameras(data.cameras))
      .catch(() => {})
  }, [])

  const run = useCallback(async (plate) => {
    const cleaned = String(plate || '').trim()
    if (!cleaned) return

    setLoading(true)
    setError(null)
    setResult(null)
    setTrajectory(null)

    try {
      const search = await api(
        `/vehicles/search?plate=${encodeURIComponent(cleaned)}`,
        { auth: true },
      )
      setResult(search)

      if (search.found) {
        const route = await api(
          `/vehicles/${encodeURIComponent(search.plate)}/trajectory`,
          { auth: true },
        )
        setTrajectory(route)
        setReplayKey((key) => key + 1)
      }
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    const initial = params.get('plate')
    if (initial) run(initial)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const submit = (event) => {
    event.preventDefault()
    setParams(query.trim() ? { plate: query.trim() } : {})
    run(query)
  }

  return (
    <>
      <div className="page-head">
        <div>
          <span className="eyebrow reveal">Operator access · vehicle lookup</span>
          <h1 className="page-title reveal">Vehicle Search</h1>
          <p className="page-sub reveal">
            Search a plate number to inspect its recorded camera observations
            and reconstruct its trajectory across the network.
          </p>
        </div>
      </div>

      <div className="panel reveal" style={{ marginBottom: 16 }}>
        <form className="toolbar" onSubmit={submit}>
          <div className="field">
            <label className="field__label" htmlFor="search-plate">
              Plate number
            </label>
            <input
              id="search-plate"
              className="input input--mono"
              placeholder="TG257602"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              maxLength={20}
            />
          </div>
          <button
            type="submit"
            className="btn btn--primary"
            disabled={loading || !query.trim()}
          >
            <MagnifyingGlass size={15} />
            {loading ? 'Searching…' : 'Search'}
          </button>
        </form>
      </div>

      {error && (
        <div className="alert alert--error reveal">
          <WarningCircle size={17} style={{ flex: 'none', marginTop: 1 }} />
          <span>{error}</span>
        </div>
      )}

      {result && !result.found && (
        <div className="panel reveal">
          <div className="alert alert--info" style={{ marginBottom: 14 }}>
            <span>
              No observations recorded for <strong className="mono">{result.plate}</strong>.
            </span>
          </div>
          {result.similar.length > 0 && (
            <>
              <div className="panel__head">
                <h2 className="panel__title">Similar plates in database</h2>
              </div>
              <div className="similar-list">
                {result.similar.map((row) => (
                  <button
                    key={row.plate}
                    type="button"
                    className="similar-list__btn"
                    onClick={() => {
                      setQuery(row.plate)
                      setParams({ plate: row.plate })
                      run(row.plate)
                    }}
                  >
                    <span className="chip chip--plate">{row.plate}</span>
                    <span className="mono" style={{ color: 'var(--text-3)', fontSize: 12 }}>
                      {row.observations} observation(s)
                    </span>
                  </button>
                ))}
              </div>
            </>
          )}
        </div>
      )}

      {result?.found && trajectory && (
        <>
          <div className="panel reveal" style={{ marginBottom: 16 }}>
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 12,
                flexWrap: 'wrap',
              }}
            >
              <span className="chip chip--plate">{trajectory.plate}</span>
              <span className="chip">
                {trajectory.summary.observations} observation(s)
              </span>
              <span className="chip">
                {trajectory.summary.cameras} camera(s)
              </span>
              {trajectory.multi_camera ? (
                <span className="chip chip--accent">Multi-camera vehicle</span>
              ) : (
                <span className="chip">Single-camera observation</span>
              )}
              <span className="mono" style={{ color: 'var(--text-3)', fontSize: 12 }}>
                {trajectory.summary.first_seen} → {trajectory.summary.last_seen}
              </span>
              {trajectory.multi_camera && (
                <RouteChips path={trajectory.camera_path} />
              )}
            </div>
          </div>

          <div className="grid">
            <div className="col-7">
              <div className="panel reveal">
                <div className="panel__head">
                  <h2 className="panel__title">Observed trajectory</h2>
                  <button
                    type="button"
                    className="btn btn--ghost btn--sm"
                    onClick={() => setReplayKey((key) => key + 1)}
                    disabled={!trajectory.multi_camera}
                  >
                    <ArrowsClockwise size={13} />
                    Replay route
                  </button>
                </div>
                <CameraMap cameras={cameras} tall>
                  <RouteOverlay
                    points={trajectory.polyline}
                    replayKey={replayKey}
                  />
                </CameraMap>
                <div className="panel__foot">
                  Route reconstructed from recorded ANPR observations at
                  junction-level coordinates — not live tracking.
                </div>
              </div>
            </div>

            <div className="col-5">
              <div className="panel reveal">
                <div className="panel__head">
                  <h2 className="panel__title">Observation timeline</h2>
                  <span className="panel__meta">
                    {trajectory.observations.length} events
                  </span>
                </div>
                <ol className="timeline">
                  {trajectory.observations.map((event, index) => (
                    <li
                      className="timeline__item"
                      key={`${event.timestamp}-${index}`}
                    >
                      <span
                        className={`timeline__dot${index === 0 ? ' timeline__dot--first' : ''}`}
                      />
                      <div className="timeline__head">
                        <span className="chip chip--cyan">{event.camera_id}</span>
                        <span style={{ color: 'var(--text-2)', fontSize: 13 }}>
                          {event.location}
                        </span>
                        <span className="timeline__time">{event.timestamp}</span>
                      </div>
                      <div className="timeline__meta">
                        <span className="confidence">
                          <span className="confidence__bar">
                            <span
                              className="confidence__fill"
                              style={{
                                width: `${Math.round(event.confidence * 100)}%`,
                              }}
                            />
                          </span>
                          {fmtPercent(event.confidence)}
                        </span>
                        <EvidenceThumb
                          name={event.evidence}
                          alt={`Evidence at ${event.camera_id}`}
                        />
                      </div>
                    </li>
                  ))}
                </ol>
              </div>
            </div>
          </div>
        </>
      )}

      {!result && !loading && !error && (
        <div className="panel reveal">
          <div className="empty-state">
            <MapPin size={22} />
            <span className="empty-state__title">
              Search a plate to view its route
            </span>
            <span className="empty-state__hint">
              Vehicles observed at more than one camera get a trajectory drawn
              between junction markers in chronological order. You can also
              browse{' '}
              <Link to="/tracking" style={{ color: 'var(--accent)' }}>
                multi-camera vehicles
              </Link>
              .
            </span>
          </div>
        </div>
      )}
    </>
  )
}
