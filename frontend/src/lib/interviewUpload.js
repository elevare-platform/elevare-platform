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
  // `reason` is what the browser could tell: 'rejected' (the storage service answered with an
  // error), 'offline', 'blocked_or_dropped' (a failed connection; the browser cannot say whether
  // the network dropped it or a firewall, VPN or ad blocker stopped it), 'timeout' or
  // 'interrupted'.
  constructor(message, status, reason = 'other') {
    super(message)
    this.name = 'UploadError'
    this.status = status
    this.reason = reason
  }
}

const connectionFailure = () => (navigator.onLine === false ? 'offline' : 'blocked_or_dropped')

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
        reject(new UploadError(`The upload was rejected (${xhr.status}).`, xhr.status, 'rejected'))
      }
    }
    xhr.onerror = () =>
      reject(new UploadError('The connection dropped during the upload.', undefined, connectionFailure()))
    xhr.ontimeout = () => reject(new UploadError('The upload took too long.', undefined, 'timeout'))
    xhr.onabort = () => reject(new UploadError('The upload was interrupted.', undefined, 'interrupted'))

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

const RETRY = 'press "Retry upload"'
const RETRY_SENTENCE = 'Press "Retry upload".'

/**
 * What went wrong when sending the recording, for the candidate and for the log. `stage` is where:
 * 'url' (asking our server for the upload address), 'file' (sending the file to storage) or
 * 'confirm' (telling our server it arrived). `message` is the server's own words when it sent any,
 * else a plain explanation with what to try, or null when nothing more can be said (the caller
 * shows its own line). `reason` and `status` are what the log gets.
 */
export function describeUploadFailure(err, { fileUploaded = false } = {}) {
  const stage = err instanceof UploadError ? 'file' : fileUploaded ? 'confirm' : 'url'
  const serverMessage = err?.response?.data?.message
  let reason
  let status
  if (err instanceof UploadError) {
    reason = err.reason
    status = err.status
  } else if (err?.response) {
    status = err.response.status
    reason = status >= 500 ? 'server_error' : 'other'
  } else {
    reason = err?.code === 'ECONNABORTED' ? 'timeout' : connectionFailure()
  }

  const text = {
    offline: `Your device is not connected to the internet. Reconnect, then ${RETRY}.`,
    blocked_or_dropped:
      'The connection dropped, or something on this network (a firewall, a VPN or an ad blocker) ' +
      `stopped the upload. Switch off any VPN, or move to another network such as your phone's hotspot, then ${RETRY}.`,
    timeout: `The upload took too long, which is usually a slow connection. Try a faster network, then ${RETRY}.`,
    interrupted: `The upload was interrupted. ${RETRY_SENTENCE}`,
    rejected:
      `The storage service did not accept the recording (code ${status}). ${RETRY_SENTENCE} ` +
      'If it keeps happening, tell your recruiter this code.',
    server_error: `Our server had a problem (code ${status}). Please wait a minute, then ${RETRY}.`,
  }[reason]

  return {
    stage,
    reason,
    status: status ?? null,
    message: typeof serverMessage === 'string' && serverMessage ? serverMessage : (text ?? null),
  }
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
