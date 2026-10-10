import { useCallback, useEffect, useRef, useState } from 'react'
import {
  Camera,
  CheckCircle,
  Image,
  UploadSimple,
  VideoCamera,
  WarningCircle,
} from '@phosphor-icons/react'
import { api } from '../lib/api'
import { fmtBytes, fmtPercent } from '../lib/format'
import { EvidenceThumb } from '../components/EvidenceThumb'

const MODES = [
  { id: 'image', label: 'Image', icon: Image, accept: '.jpg,.jpeg,.png,.bmp' },
  {
    id: 'video',
    label: 'Video',
    icon: VideoCamera,
    accept: '.mp4,.avi,.mkv,.mov,.webm,.ogv',
  },
]

function DetectionTable({ detections }) {
  return (
    <table className="table">
      <thead>
        <tr>
          <th>Plate</th>
          <th title="YOLO plate-region detection score; verify OCR text against evidence">Detector score</th>
          <th>Camera</th>
          <th>Recorded</th>
          <th>Evidence</th>
        </tr>
      </thead>
      <tbody>
        {detections.map((detection, index) => (
          <tr key={`${detection.plate_number}-${index}`}>
            <td>
              <span className="chip chip--plate">{detection.plate_number}</span>
            </td>
            <td>
              <span className="confidence">
                <span className="confidence__bar">
                  <span
                    className="confidence__fill"
                    style={{ width: `${Math.round(detection.confidence * 100)}%` }}
                  />
                </span>
                {fmtPercent(detection.confidence)}
              </span>
            </td>
            <td>
              <span className="chip">{detection.camera_id}</span>{' '}
              <span style={{ color: 'var(--text-3)' }}>
                {detection.location}
              </span>
            </td>
            <td className="num" style={{ color: 'var(--text-2)' }}>
              {detection.timestamp || '—'}
              {detection.video_time !== undefined && (
                <div style={{ color: 'var(--text-3)', fontSize: 11.5 }}>
                  at {detection.video_time}s · {detection.hits} hit(s)
                </div>
              )}
            </td>
            <td>
              <EvidenceThumb
                name={detection.evidence || detection.frame}
                alt={`Evidence for ${detection.plate_number}`}
              />
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}

export function Console() {
  const [cameras, setCameras] = useState([])
  const [cameraId, setCameraId] = useState('')
  const [mode, setMode] = useState('image')
  const [file, setFile] = useState(null)
  const [dragging, setDragging] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)
  const [result, setResult] = useState(null)
  const [job, setJob] = useState(null)
  const fileInput = useRef(null)

  useEffect(() => {
    api('/cameras')
      .then((data) => {
        setCameras(data.cameras)
        setCameraId((current) => current || data.cameras[0]?.id || '')
      })
      .catch((err) => setError(err.message))
  }, [])

  useEffect(() => {
    if (!job?.id || job.status === 'completed' || job.status === 'failed') {
      return undefined
    }

    let cancelled = false
    let timer = null

    const poll = async () => {
      try {
        const status = await api(`/jobs/${job.id}`, { auth: true })
        if (cancelled) return

        setJob(status)

        if (status.status === 'completed') {
          setResult(status.result)
          setBusy(false)
          return
        }

        if (status.status === 'failed') {
          setError(status.error || 'Video analysis failed.')
          setBusy(false)
          return
        }
      } catch (err) {
        if (!cancelled) {
          setError(err.message)
          setBusy(false)
        }
        return
      }

      timer = setTimeout(poll, 2000)
    }

    timer = setTimeout(poll, 700)

    return () => {
      cancelled = true
      if (timer) clearTimeout(timer)
    }
  }, [job?.id, job?.status])

  const selectMode = useCallback((nextMode) => {
    setMode(nextMode)
    setFile(null)
    setError(null)
    if (fileInput.current) fileInput.current.value = ''
  }, [])

  const onDrop = useCallback(
    (event) => {
      event.preventDefault()
      setDragging(false)
      const dropped = event.dataTransfer?.files?.[0]
      if (dropped) {
        setFile(dropped)
        setError(null)
      }
    },
    [],
  )

  const run = async () => {
    if (!file || !cameraId) {
      setError('Choose a camera and a file before running detection.')
      return
    }

    setBusy(true)
    setError(null)
    setResult(null)
    setJob(null)

    const form = new FormData()
    form.append('camera_id', cameraId)
    form.append('file', file)

    try {
      if (mode === 'image') {
        const data = await api('/detect/image', {
          method: 'POST',
          form,
          auth: true,
        })
        setResult(data)
        setBusy(false)
      } else {
        const data = await api('/detect/video', {
          method: 'POST',
          form,
          auth: true,
        })
        setJob({ id: data.job_id, status: 'queued', progress: null })
      }
    } catch (err) {
      setError(err.message)
      setBusy(false)
    }
  }

  const activeMode = MODES.find((entry) => entry.id === mode)
  const progress = job?.progress
  const progressPercent = progress?.percent ?? 0
  const indeterminate = job && !progress?.percent

  return (
    <div className="console-workspace">
      <div className="page-head console-workspace__hero">
        <div>
          <span className="eyebrow reveal">MERIDIAN / OPERATOR WORKSPACE / 01</span>
          <h1 className="page-title reveal">ANPR Console</h1>
          <p className="page-sub reveal">
            Turn image and video input into recorded observations. Select a
            camera, inspect the result, and keep the evidence connected.
          </p>
        </div>
        <div className="console-workspace__hero-art" aria-hidden="true">
          <span>DETECT <i /> READ <i /> RECORD</span>
        </div>
      </div>

      <div className="console-workspace__intro">
        <span>01 / CONFIGURE INPUT</span>
        <span>02 / REVIEW DETECTIONS</span>
        <span>SIMULATED CAMERA NETWORK · OPERATOR ACCESS</span>
      </div>

      <div className="grid console-workspace__grid">
        <div className="col-5">
          <div className="panel reveal console-workspace__input">
            <div className="panel__head">
              <h2 className="panel__title">01 / Detection input</h2>
              <span className="panel__meta">CAMERA + MEDIA</span>
            </div>

            <div className="field">
              <label className="field__label" htmlFor="console-camera">
                Camera location
              </label>
              <select
                id="console-camera"
                className="select"
                value={cameraId}
                onChange={(event) => setCameraId(event.target.value)}
              >
                {cameras.map((camera) => (
                  <option key={camera.id} value={camera.id}>
                    {camera.label}
                  </option>
                ))}
              </select>
            </div>

            <div className="field">
              <span className="field__label">Input type</span>
              <div style={{ display: 'flex', gap: 8 }}>
                {MODES.map((entry) => (
                  <button
                    key={entry.id}
                    type="button"
                    className={`btn ${mode === entry.id ? 'btn--primary' : 'btn--ghost'}`}
                    style={{ flex: 1 }}
                    onClick={() => selectMode(entry.id)}
                  >
                    <entry.icon size={14} />
                    {entry.label}
                  </button>
                ))}
              </div>
            </div>

            <label
              className={`dropzone${dragging ? ' is-drag' : ''}`}
              htmlFor="console-file"
              onDragOver={(event) => {
                event.preventDefault()
                setDragging(true)
              }}
              onDragLeave={() => setDragging(false)}
              onDrop={onDrop}
            >
              <UploadSimple size={26} className="dropzone__icon" />
              <span className="dropzone__title">
                {mode === 'image'
                  ? 'Drop a vehicle image here'
                  : 'Drop a traffic video here'}
              </span>
              <span className="dropzone__hint">
                {mode === 'image'
                  ? 'JPG · PNG · BMP — up to 25 MB'
                  : 'MP4 · AVI · MKV · MOV — up to 300 MB, sampled at 3 fps'}
              </span>
              {file && (
                <span className="dropzone__file">
                  <activeMode.icon size={13} />
                  {file.name} · {fmtBytes(file.size)}
                </span>
              )}
              <input
                id="console-file"
                ref={fileInput}
                type="file"
                accept={activeMode.accept}
                hidden
                onChange={(event) => {
                  setFile(event.target.files?.[0] || null)
                  setError(null)
                }}
              />
            </label>

            <button
              type="button"
              className="btn btn--primary"
              style={{ width: '100%', marginTop: 16 }}
              onClick={run}
              disabled={busy || !file}
            >
              <Camera size={15} />
              {busy
                ? mode === 'video'
                  ? 'Analyzing video…'
                  : 'Running detection…'
                : 'Run ANPR detection'}
            </button>

            {job && job.status !== 'completed' && job.status !== 'failed' && (
              <div className="progress">
                <div className="progress__head">
                  <span>
                    {progress
                      ? `${progress.frames} frame(s) · ~${progress.seconds}s of footage`
                      : 'Queued…'}
                  </span>
                  <span>{progress?.percent ? `${progressPercent}%` : '…'}</span>
                </div>
                <div className="progress__bar">
                  <div
                    className={`progress__fill${indeterminate ? ' progress__fill--indeterminate' : ''}`}
                    style={{ width: `${progressPercent}%` }}
                  />
                </div>
              </div>
            )}

            {error && (
              <div className="alert alert--error" style={{ marginTop: 16, marginBottom: 0 }}>
                <WarningCircle size={17} style={{ flex: 'none', marginTop: 1 }} />
                <span>{error}</span>
              </div>
            )}
          </div>
        </div>

        <div className="col-7">
          <div className="panel reveal console-workspace__results">
            <div className="panel__head">
              <h2 className="panel__title">02 / Evidence review</h2>
              {result && (
                <span className="panel__meta">
                  {result.detections.length} plate(s) · {result.saved_count}{' '}
                  record(s) saved
                </span>
              )}
            </div>

            {!result && !busy && (
              <div className="empty-state">
                <Camera size={22} />
                <span className="empty-state__title">No detection run yet</span>
                <span className="empty-state__hint">
                  Choose a camera, pick an image or video and run the ANPR
                  pipeline. Review the recognized text against the evidence
                  crop before relying on it.
                </span>
              </div>
            )}

            {busy && mode === 'image' && (
              <div>
                <div className="skeleton skeleton--line" />
                <div className="skeleton skeleton--line" style={{ width: '70%' }} />
                <div className="skeleton skeleton--block" style={{ marginTop: 14 }} />
              </div>
            )}

            {result && result.detections.length > 0 && (
              <>
                <div className="alert alert--success" style={{ marginBottom: 14 }}>
                  <CheckCircle size={17} style={{ flex: 'none', marginTop: 1 }} />
                  <span>
                    {result.source_label} processed · {result.saved_count}{' '}
                    record(s) added to the shared detection database.
                  </span>
                </div>
                <div style={{ overflowX: 'auto' }}>
                  <DetectionTable detections={result.detections} />
                </div>
              </>
            )}

            {result && result.detections.length === 0 && (
              <div className="empty-state">
                <WarningCircle size={22} />
                <span className="empty-state__title">
                  No readable plates found
                </span>
                <span className="empty-state__hint">
                  {result.source_label} processed, but the pipeline found no
                  structurally valid Indian plate. Try a clearer image or a
                  steadier, higher-resolution video.
                </span>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
