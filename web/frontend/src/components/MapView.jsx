import { useEffect, useMemo, useRef } from 'react'
import {
  CircleMarker,
  MapContainer,
  Marker,
  Polyline,
  TileLayer,
  Tooltip,
  ZoomControl,
  useMap,
} from 'react-leaflet'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import { gsap, prefersReducedMotion } from '../lib/motion'

const TILE_URL =
  'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png'

const TILE_ATTRIBUTION =
  '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'

const HYDERABAD_CENTER = [17.4948, 78.42]

function cameraIcon(camera) {
  const html = `
    <div class="cam-marker">
      <span class="cam-marker__pulse"></span>
      <span class="cam-marker__core"></span>
      <span class="cam-marker__label">${camera.id}</span>
    </div>
  `

  return L.divIcon({
    className: 'cam-marker-wrap',
    html,
    iconSize: [14, 14],
    iconAnchor: [7, 7],
  })
}

export function CameraMap({ cameras = [], stats = [], children, tall, selectedId, onSelect, cityOverview = false }) {
  const statById = useMemo(
    () =>
      Object.fromEntries(
        stats.map((row) => [row.camera_id, row]),
      ),
    [stats],
  )

  return (
    <div className={`map-wrap${tall ? ' map-wrap--tall' : ''}`}>
      <MapContainer
        center={cityOverview ? [17.45, 78.44] : HYDERABAD_CENTER}
        zoom={cityOverview ? 11 : 12}
        zoomControl={false}
        scrollWheelZoom={!cityOverview}
        style={{ height: '100%', width: '100%' }}
      >
        <TileLayer url={TILE_URL} attribution={TILE_ATTRIBUTION} />
        <ZoomControl position="bottomright" />

        {cameras.map((camera) => {
          const stat = statById[camera.id]

          return (
            <Marker
              key={camera.id}
              position={[camera.lat, camera.lon]}
              icon={cameraIcon(camera)}
              opacity={selectedId && selectedId !== camera.id ? 0.6 : 1}
              eventHandlers={onSelect ? { click: () => onSelect(camera.id) } : undefined}
            >
              <Tooltip direction="top" offset={[0, -12]} className="cam-tooltip">
                <strong>{camera.id}</strong> · {camera.location}
                {stat && (
                  <span className="cam-tooltip__meta">
                    {stat.observations} recorded observation
                    {stat.observations === 1 ? '' : 's'}
                  </span>
                )}
              </Tooltip>
            </Marker>
          )
        })}

        {children}
      </MapContainer>
    </div>
  )
}

function interpolate(points, progress) {
  if (!points || points.length < 2) return points || []

  const segments = []
  let total = 0

  for (let i = 1; i < points.length; i += 1) {
    const distance = Math.hypot(
      points[i][0] - points[i - 1][0],
      points[i][1] - points[i - 1][1],
    )
    segments.push(distance)
    total += distance
  }

  if (total === 0) return points

  let remaining = total * progress
  const drawn = [points[0]]

  for (let i = 1; i < points.length; i += 1) {
    const distance = segments[i - 1]

    if (remaining >= distance) {
      drawn.push(points[i])
      remaining -= distance
    } else {
      const fraction = distance === 0 ? 0 : remaining / distance
      drawn.push([
        points[i - 1][0] + (points[i][0] - points[i - 1][0]) * fraction,
        points[i - 1][1] + (points[i][1] - points[i - 1][1]) * fraction,
      ])
      break
    }
  }

  return drawn
}

export function RouteOverlay({ points, replayKey = 0 }) {
  const map = useMap()
  const progressRef = useRef(null)
  const tipRef = useRef(null)

  useEffect(() => {
    if (!points || points.length < 2) return undefined

    const bounds = L.latLngBounds(points)
    map.fitBounds(bounds, { padding: [56, 56], maxZoom: 14 })

    const apply = (progress) => {
      const drawn = interpolate(points, progress)
      progressRef.current?.setLatLngs(drawn)
      const tip = drawn[drawn.length - 1]
      if (tip) tipRef.current?.setLatLng(tip)
    }

    if (prefersReducedMotion()) {
      apply(1)
      return undefined
    }

    const state = { progress: 0 }

    const tween = gsap.to(state, {
      progress: 1,
      duration: 1.4 + points.length * 0.55,
      ease: 'power2.inOut',
      onUpdate: () => apply(state.progress),
    })

    return () => tween.kill()
  }, [points, replayKey, map])

  if (!points || points.length < 2) return null

  return (
    <>
      <Polyline
        positions={points}
        pathOptions={{
          color: 'rgba(56, 189, 248, 0.28)',
          weight: 2,
          dashArray: '4 8',
        }}
      />
      <Polyline
        ref={progressRef}
        positions={[]}
        pathOptions={{
          color: '#38bdf8',
          weight: 3.5,
          lineCap: 'round',
        }}
      />
      <CircleMarker
        ref={tipRef}
        center={points[0]}
        radius={6}
        pathOptions={{
          color: '#38bdf8',
          weight: 3,
          fillColor: '#0a0e15',
          fillOpacity: 1,
        }}
      />
    </>
  )
}
