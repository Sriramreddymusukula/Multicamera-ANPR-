import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { ArrowsClockwise, Path, WarningCircle } from '@phosphor-icons/react'
import { api } from '../lib/api'

export function Tracking() {
  const navigate = useNavigate()
  const [vehicles, setVehicles] = useState(null)
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(true)

  const load = () => {
    setLoading(true)
    setError(null)

    api('/vehicles/multi-camera', { auth: true })
      .then((data) => setVehicles(data.vehicles))
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    load()
  }, [])

  return (
    <>
      <div className="page-head">
        <div>
          <span className="eyebrow reveal">Operator access · cross-camera</span>
          <h1 className="page-title reveal">Multi-Camera Tracking</h1>
          <p className="page-sub reveal">
            Vehicles observed at more than one camera, ranked by observation
            count. Select a vehicle to draw its recorded route on the map.
          </p>
        </div>
        <button
          type="button"
          className="btn btn--ghost btn--sm reveal"
          onClick={load}
          disabled={loading}
        >
          <ArrowsClockwise size={14} />
          Refresh
        </button>
      </div>

      {error && (
        <div className="alert alert--error reveal">
          <WarningCircle size={17} style={{ flex: 'none', marginTop: 1 }} />
          <span>{error}</span>
        </div>
      )}

      {loading && !vehicles && (
        <div className="panel">
          <div className="skeleton skeleton--line" />
          <div className="skeleton skeleton--line" style={{ width: '80%' }} />
          <div className="skeleton skeleton--line" style={{ width: '60%' }} />
        </div>
      )}

      {vehicles && vehicles.length === 0 && (
        <div className="panel reveal">
          <div className="empty-state">
            <Path size={22} />
            <span className="empty-state__title">
              No multi-camera vehicles recorded
            </span>
            <span className="empty-state__hint">
              Process the same vehicle at two different cameras from the ANPR
              Console — matching plate observations are associated
              automatically.
            </span>
          </div>
        </div>
      )}

      {vehicles && vehicles.length > 0 && (
        <div className="panel reveal" style={{ padding: 0 }}>
          <div style={{ overflowX: 'auto' }}>
            <table className="table">
              <thead>
                <tr>
                  <th>Plate</th>
                  <th>Observed route</th>
                  <th>Cameras</th>
                  <th>Observations</th>
                  <th>Last seen</th>
                </tr>
              </thead>
              <tbody>
                {vehicles.map((vehicle) => (
                  <tr
                    key={vehicle.plate}
                    className="is-clickable"
                    onClick={() =>
                      navigate(`/search?plate=${encodeURIComponent(vehicle.plate)}`)
                    }
                  >
                    <td>
                      <span className="chip chip--plate">{vehicle.plate}</span>
                    </td>
                    <td>
                      <span className="route-chips">
                        {vehicle.cameras.map((cameraId, index) => (
                          <span
                            key={`${cameraId}-${index}`}
                            style={{ display: 'contents' }}
                          >
                            <span className="chip chip--cyan">{cameraId}</span>
                            {index < vehicle.cameras.length - 1 && (
                              <span className="route-chips__arrow">→</span>
                            )}
                          </span>
                        ))}
                      </span>
                    </td>
                    <td className="num">{vehicle.camera_count}</td>
                    <td className="num">{vehicle.observations}</td>
                    <td className="num" style={{ color: 'var(--text-2)' }}>
                      {vehicle.last_seen || '—'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </>
  )
}
