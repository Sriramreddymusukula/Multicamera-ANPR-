const OPERATOR_EMAIL = /^[A-Za-z0-9_%+-]+(?:\.[A-Za-z0-9_%+-]+)*\.cop@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}$/

export function normalizeOperatorEmail(value) {
  return value.trim().toLowerCase()
}

export function isOperatorEmail(value) {
  const email = normalizeOperatorEmail(value)
  if (!OPERATOR_EMAIL.test(email)) return false
  return email.split('@')[1].split('.').every((part) => !part.startsWith('-') && !part.endsWith('-'))
}
