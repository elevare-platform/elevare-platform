// Sends the recording a strict interview kept across a reload to the server, as separate parts.
// The server joins the parts with the final recording into one video before scoring.

import { putBlob as realPutBlob, withRetry as realWithRetry } from '@/lib/interviewUpload'

// A recording smaller than this holds no usable video (a recorder started and stopped at once).
export const MIN_USEFUL_BYTES = 2000

/**
 * Uploads every earlier recording kept for this interview (every one but `currentSegment`, the
 * one being made now) and forgets each once the server has it. A recording that cannot be sent is
 * left where it is, to be tried again the next time, and the others are still sent. Resolves with
 * how many were sent and how many were not; never throws.
 *
 * The part number is reserved once per recording and the same address is retried, so a poor
 * connection cannot use up the parts a candidate is allowed.
 */
export async function salvagePreviousRecordings({
  store,
  interviewId,
  currentSegment,
  requestPartUploadUrl,
  putBlob = realPutBlob,
  withRetry = realWithRetry,
}) {
  const result = { uploaded: 0, failed: 0 }
  if (!store || !interviewId) return result

  const kept = await store.segments(interviewId)
  for (const { segment } of kept) {
    if (segment === currentSegment) continue
    const chunks = await store.readSegment(interviewId, segment)
    const blob = new Blob(chunks, { type: 'video/webm' })
    if (blob.size < MIN_USEFUL_BYTES) {
      await store.deleteSegment(interviewId, segment)
      continue
    }
    try {
      const { upload_url: url } = await withRetry(() => requestPartUploadUrl())
      await withRetry(() => putBlob({ url, blob, contentType: 'video/webm' }))
      await store.deleteSegment(interviewId, segment)
      result.uploaded += 1
    } catch {
      result.failed += 1
    }
  }
  return result
}
