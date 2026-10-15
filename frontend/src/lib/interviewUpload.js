// Upload helpers for the AI interview recording, built for weak connections.
//
// A 20-minute recording is tens of megabytes and the candidate may be on
// mobile data. A single failed request must not cost them the interview, so
// uploads report progress, retry with a fresh upload URL, and the caller keeps
// the recording in memory until it has really arrived.

export const MAX_ATTEMPTS = 3
export const RETRY_DELAYS_MS = [2000, 6000]
// Generous on purpose: 20 minutes of video over a slow uplink takes a while.
export const PUT_TIMEOUT_MS = 20 * 60 * 1000

export class UploadError extends Error {
  constructor(message, status) {
    super(message)
    this.name = 'UploadError'
    this.status = status
  }
}

const defaultSleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms))

/**
 * PUT a blob to a presigned URL, reporting progress as a 0-100 integer.
 * XMLHttpRequest (not fetch) because only XHR reports upload progress.
 */
export function putBlob({
  url,
  blob,
  contentType,
  onProgress,
  timeoutMs = PUT_TIMEOUT_MS,
  createXhr = () => new XMLHttpRequest(),
}) {
  return new Promise((resolve, reject) => {
    const xhr = createXhr()
    xhr.open('PUT', url)
    xhr.setRequestHeader('Content-Type', contentType)
    xhr.timeout = timeoutMs

    xhr.upload.onprogress = (event) => {
      if (onProgress && event.lengthComputable && event.total > 0) {
        onProgress(Math.round((event.loaded / event.total) * 100))
      }
    }
    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        resolve()
      } else {
        reject(new UploadError(`The upload was rejected (${xhr.status}).`, xhr.status))
      }
    }
    xhr.onerror = () => reject(new UploadError('The connection dropped during the upload.'))
    xhr.ontimeout = () => reject(new UploadError('The upload took too long.'))
    xhr.onabort = () => reject(new UploadError('The upload was interrupted.'))

    xhr.send(blob)
  })
}

/**
 * Whether trying again could help. Network failures, timeouts and server
 * errors can pass; a 4xx answer from our own API (such as "already uploaded")
 * will not change on a retry. A failed PUT is always retried, because the
 * likeliest cause is an expired URL and every attempt asks for a fresh one.
 */
export function isRetryable(err) {
  const status = err?.response?.status
  if (status) return status === 408 || status === 429 || status >= 500
  return true
}

/**
 * Run `fn` up to `attempts` times with a pause between tries. `fn` receives the
 * zero-based attempt number. Non-retryable errors are thrown immediately.
 */
export async function withRetry(
  fn,
  { attempts = MAX_ATTEMPTS, delaysMs = RETRY_DELAYS_MS, sleep = defaultSleep, onRetry } = {},
) {
  let lastError
  for (let attempt = 0; attempt < attempts; attempt += 1) {
    try {
      return await fn(attempt)
    } catch (err) {
      lastError = err
      if (attempt === attempts - 1 || !isRetryable(err)) throw err
      onRetry?.(attempt + 1, err)
      await sleep(delaysMs[Math.min(attempt, delaysMs.length - 1)])
    }
  }
  throw lastError
}

/**
 * Upload the recording, retrying automatically. Every attempt asks the API
 * for a new upload URL, so an expired URL never keeps failing.
 */
export function uploadRecording({
  requestUploadUrl,
  blob,
  contentType,
  onProgress,
  createXhr,
  ...retryOptions
}) {
  return withRetry(async () => {
    onProgress?.(0)
    const { upload_url: uploadUrl } = await requestUploadUrl()
    await putBlob({ url: uploadUrl, blob, contentType, onProgress, createXhr })
  }, retryOptions)
}
