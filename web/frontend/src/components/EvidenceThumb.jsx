import { useEffect, useState } from 'react'
import { ImageBroken } from '@phosphor-icons/react'
import { apiBlob } from '../lib/api'

export function EvidenceThumb({ name, alt, large }) {
  const [url, setUrl] = useState(null)
  const [failed, setFailed] = useState(false)

  useEffect(() => {
    if (!name) return undefined

    let objectUrl = null
    let active = true

    apiBlob(`/evidence/${encodeURIComponent(name)}`)
      .then((blob) => {
        if (!active) return
        objectUrl = URL.createObjectURL(blob)
        setUrl(objectUrl)
      })
      .catch(() => {
        if (active) setFailed(true)
      })

    return () => {
      active = false
      if (objectUrl) URL.revokeObjectURL(objectUrl)
    }
  }, [name])

  if (!name || failed) {
    return (
      <div className={`thumb thumb--empty${large ? ' thumb--lg' : ''}`}>
        <ImageBroken size={18} />
      </div>
    )
  }

  if (!url) {
    return <div className={`thumb skeleton${large ? ' thumb--lg' : ''}`} />
  }

  return (
    <img
      className={`thumb${large ? ' thumb--lg' : ''}`}
      src={url}
      alt={alt || 'Plate evidence'}
      loading="lazy"
    />
  )
}
