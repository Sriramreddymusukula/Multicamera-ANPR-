import { useCallback, useEffect, useRef, useState } from 'react'
import { BellRinging, CheckCircle, WarningCircle, XCircle } from '@phosphor-icons/react'
import { api } from '../lib/api'
import { fmtPercent } from '../lib/format'
import { enableReviewSound, isReviewSoundEnabled, playReviewSound, setReviewSoundEnabled } from '../lib/reviewSound'
import { EvidenceThumb } from '../components/EvidenceThumb'

const COLORS = ['Black', 'White', 'Silver', 'Grey', 'Blue', 'Red', 'Green', 'Brown', 'Yellow', 'Other']

function ReviewItem({ item, onDecide }) {
  const [plate, setPlate] = useState(item.prediction)
  const [vehicleColor, setVehicleColor] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  const decide = async (action) => {
    setBusy(true)
    setError('')
    try {
      await api(`/reviews/${item.id}/decision`, {
        method: 'POST',
        auth: true,
        body: { action, plate: plate.trim().toUpperCase(), vehicle_color: vehicleColor || null },
      })
      onDecide(item.id)
    } catch (cause) {
      setError(cause.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <article className="review-item">
      <div className="review-item__visuals">
        <EvidenceThumb name={item.frame} alt={`Vehicle frame from ${item.camera_id}`} large />
        <EvidenceThumb name={item.evidence} alt="Detected plate crop for review" large />
      </div>
      <div className="review-item__body">
        <div className="review-item__top"><span className="eyebrow">PENDING REVIEW / {item.camera_id}</span><span>{item.observed_at}</span></div>
        <h2>{item.prediction}</h2>
        <p>Local model reading · compare with the frame and plate crop</p>

        <div className="review-item__scores">
          <span>Detector <strong>{fmtPercent(item.detector_score)}</strong></span>
          <span>OCR <strong>{item.ocr_score == null ? 'Unavailable' : fmtPercent(item.ocr_score)}</strong></span>
          {item.match_score != null && <span>Frame agreement <strong>{fmtPercent(item.match_score)}</strong></span>}
        </div>

        <div className="review-item__context">
          <div><small>WHY THIS NEEDS A DECISION</small><p>{item.reasons.join(' · ')}</p></div>
          <div>
            <small>OBSERVATION CONTEXT</small>
            <dl className="review-item__facts">
              <div><dt>Assigned camera / junction</dt><dd>{item.camera_id} · {item.location}</dd></div>
              <div><dt>Processed at</dt><dd>{item.observed_at}</dd></div>
              <div><dt>Source</dt><dd>{item.source_name || (item.video_time != null ? 'Uploaded video' : 'Uploaded image')}</dd></div>
              <div><dt>Video evidence</dt><dd>{item.video_time != null ? `${item.hits || 1} sampled read(s) · ${item.video_time}s into video` : 'Still image'}</dd></div>
            </dl>
          </div>
          <div>
            <small>VEHICLE APPEARANCE · GEMINI SUGGESTION</small>
            <p>{item.suggested_color || 'Colour unavailable'} · {item.suggested_style || 'Body style unavailable'}</p>
            <p>Derived from a frame with the plate masked. Check the original frame before using these details.</p>
            {item.suggested_color && <button className="review-item__provider" type="button" onClick={() => setVehicleColor(item.suggested_color)}>Use suggested colour</button>}
          </div>
          {item.alternatives?.length > 1 && (
            <div><small>ALTERNATE VIDEO READS · SELECT TO FILL</small><div className="review-item__suggestions">{item.alternatives.map((value) => <button type="button" key={value} onClick={() => setPlate(value)}>{value}</button>)}</div></div>
          )}
          <div>
            <small>INDEPENDENT PLATE READING</small>
            <p>{item.provider ? `${item.provider_read || 'No valid reading'} · ${item.provider}` : 'Unavailable for this crop'}</p>
            {item.provider_read && <button className="review-item__provider" type="button" onClick={() => setPlate(item.provider_read)}>Use second reading</button>}
          </div>
          <div>
            <small>POSSIBLE RECORDED SIGHTINGS · NOT A VERIFIED ROUTE</small>
            {item.related_observations?.length > 0 ? (
              <div className="review-item__sightings">{item.related_observations.map((seen, index) => (
                <div key={`${seen.plate}-${index}`}>
                  <strong>{seen.plate}</strong>
                  <span>{seen.camera_id} · {seen.location}</span>
                  <span>{seen.minutes_apart} min {seen.time_relation} processing time · {seen.character_matches}/{seen.plate.length} characters match</span>
                </div>
              ))}</div>
            ) : <p>No nearby registration candidates in recorded history.</p>}
          </div>
        </div>

        <div className="review-item__action">
          <label htmlFor={`plate-${item.id}`}>Confirmed registration</label>
          <input id={`plate-${item.id}`} className="input" value={plate} maxLength={12} autoComplete="off" onChange={(event) => setPlate(event.target.value.toUpperCase())} />
          <label htmlFor={`color-${item.id}`}>Vehicle colour · optional operator observation</label>
          <select id={`color-${item.id}`} className="input" value={vehicleColor} onChange={(event) => setVehicleColor(event.target.value)}>
            <option value="">Unknown / not visible</option>
            {COLORS.map((color) => <option key={color} value={color}>{color}</option>)}
          </select>
          <p className="review-item__hint">Colour is saved with this review only. It does not establish a vehicle match. A route becomes available after confirmed registrations are observed at multiple cameras.</p>
          <button className="btn btn--primary" type="button" disabled={busy} onClick={() => decide('confirm')}><CheckCircle size={16} /> Confirm &amp; save</button>
          <button className="btn btn--ghost" type="button" disabled={busy} onClick={() => decide('reject')}><XCircle size={16} /> Reject</button>
        </div>
        {error && <p className="review-item__error" role="alert">{error}</p>}
      </div>
    </article>
  )
}

export function Reviews() {
  const [items, setItems] = useState([])
  const [error, setError] = useState('')
  const [soundEnabled, setSoundEnabledState] = useState(isReviewSoundEnabled)
  const previousCount = useRef(null)

  const refresh = useCallback(async () => {
    try {
      const data = await api('/reviews', { auth: true })
      if (data.count > (previousCount.current ?? 0)) playReviewSound()
      previousCount.current = data.count
      setItems(data.items)
      setError('')
    } catch (cause) {
      setError(cause.message)
    }
  }, [])

  useEffect(() => {
    const initial = setTimeout(refresh, 0)
    const timer = setInterval(refresh, 15000)
    return () => { clearTimeout(initial); clearInterval(timer) }
  }, [refresh])

  const toggleSound = async () => {
    const enabled = !soundEnabled
    setReviewSoundEnabled(enabled)
    setSoundEnabledState(enabled)
    if (enabled) {
      await enableReviewSound()
      playReviewSound()
    }
  }

  return (
    <div className="review-workspace">
      <div className="page-head review-workspace__head">
        <div><span className="eyebrow">MERIDIAN / OPERATOR WORKSPACE / 02</span><h1 className="page-title">Observation review</h1><p className="page-sub">Compare plate readings, frame evidence, time, junction and possible earlier sightings. Confirm the registration only after reviewing the evidence.</p></div>
        <button type="button" className="btn btn--ghost" onClick={toggleSound} aria-pressed={soundEnabled}><BellRinging size={16} /> {soundEnabled ? 'Bell alerts on' : 'Bell alerts off'}</button>
      </div>
      <div className="review-workspace__summary"><strong>{items.length}</strong><span>observations awaiting a decision</span><button type="button" onClick={refresh}>Refresh queue</button></div>
      {error && <div className="alert alert--error" role="alert"><WarningCircle size={18} /> {error}</div>}
      {items.length === 0 && !error && <div className="panel review-workspace__empty"><CheckCircle size={28} /><h2>Queue is clear</h2><p>New uncertain observations will appear here. Bell alerts are on by default while this page is open.</p></div>}
      <div className="review-workspace__list">{items.map((item) => <ReviewItem key={item.id} item={item} onDecide={(id) => { setItems((current) => current.filter((entry) => entry.id !== id)); previousCount.current = Math.max(0, (previousCount.current || 1) - 1) }} />)}</div>
    </div>
  )
}
