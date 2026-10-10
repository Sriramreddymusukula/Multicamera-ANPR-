const MUTE_KEY = 'meridian-review-sound-muted'
let audioContext
let pendingBell = false

export function isReviewSoundEnabled() {
  try {
    return window.localStorage.getItem(MUTE_KEY) !== 'true'
  } catch {
    return true
  }
}

export function setReviewSoundEnabled(enabled) {
  try {
    window.localStorage.setItem(MUTE_KEY, String(!enabled))
  } catch {
    // Alerts still work for this session when storage is unavailable.
  }
  if (!enabled) pendingBell = false
}

function ringBell() {
  if (!audioContext || audioContext.state !== 'running') return
  const start = audioContext.currentTime
  for (const strike of [0, 0.23]) {
    for (const [frequency, volume] of [[880, 0.085], [1760, 0.027], [2640, 0.011]]) {
      const tone = audioContext.createOscillator()
      const gain = audioContext.createGain()
      const at = start + strike
      tone.type = 'sine'
      tone.frequency.value = frequency
      gain.gain.setValueAtTime(0.0001, at)
      gain.gain.exponentialRampToValueAtTime(volume, at + 0.012)
      gain.gain.exponentialRampToValueAtTime(0.0001, at + 0.72)
      tone.connect(gain).connect(audioContext.destination)
      tone.start(at)
      tone.stop(at + 0.73)
    }
  }
}

export async function enableReviewSound() {
  if (!isReviewSoundEnabled()) return false
  const AudioContextClass = window.AudioContext || window.webkitAudioContext
  if (!AudioContextClass) return false
  audioContext ||= new AudioContextClass()
  if (audioContext.state === 'running') {
    if (pendingBell) {
      pendingBell = false
      ringBell()
    }
    return true
  }
  try {
    await audioContext.resume()
  } catch {
    return false
  }
  if (audioContext.state === 'running' && pendingBell) {
    pendingBell = false
    ringBell()
  }
  return audioContext.state === 'running'
}

export function playReviewSound() {
  if (!isReviewSoundEnabled()) return
  if (audioContext?.state === 'running') ringBell()
  else pendingBell = true
}
