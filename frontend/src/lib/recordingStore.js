// Keeps a strict interview's recording in the browser's own storage (IndexedDB) while it is being
// made, so a reload, a crash or a closed tab does not lose what was recorded so far
// (docs/08_DECISIONS.md, "The new strict, text-only AI interview", item 24). When the candidate
// comes back, the earlier recording is found here and uploaded as a separate part.
//
// A recording is a list of chunks, one a second, kept under the interview and a "segment" (one
// per time the recorder is started, so a reload never mixes two recordings). Nothing here ever
// throws: storage can be missing (private windows), full or blocked, and the interview must carry
// on without it, recording in memory only, exactly as before. Every method says whether it worked.

const DB_NAME = 'elevare-interview-recording'
const STORE = 'chunks'

function asPromise(request) {
  return new Promise((resolve, reject) => {
    request.onsuccess = () => resolve(request.result)
    request.onerror = () => reject(request.error)
  })
}

function finished(transaction) {
  return new Promise((resolve, reject) => {
    transaction.oncomplete = () => resolve()
    transaction.onerror = () => reject(transaction.error)
    transaction.onabort = () => reject(transaction.error)
  })
}

/**
 * Opens the store, or returns null when the browser has no IndexedDB. `factory` is only for tests.
 * Chunks are keyed by [interviewId, segment, index], so they come back in recording order.
 */
export function openRecordingStore(factory = globalThis.indexedDB) {
  if (!factory) return null
  let opening = null

  const database = () => {
    opening ??= new Promise((resolve, reject) => {
      const request = factory.open(DB_NAME, 1)
      request.onupgradeneeded = () => {
        request.result.createObjectStore(STORE, { keyPath: ['interviewId', 'segment', 'index'] })
      }
      request.onsuccess = () => resolve(request.result)
      request.onerror = () => reject(request.error)
      request.onblocked = () => reject(new Error('The recording store is blocked.'))
    })
    return opening
  }

  const segmentRange = (interviewId, segment) =>
    IDBKeyRange.bound([interviewId, segment, -Infinity], [interviewId, segment, Infinity])
  const interviewRange = (interviewId) =>
    IDBKeyRange.bound([interviewId, '', -Infinity], [interviewId, '￿', Infinity])

  const attempt = async (fallback, work) => {
    try {
      return await work(await database())
    } catch {
      return fallback
    }
  }

  return {
    /** Keeps one chunk of the recording. Resolves true when it was kept. */
    addChunk: (interviewId, segment, index, blob) =>
      attempt(false, async (db) => {
        const transaction = db.transaction(STORE, 'readwrite')
        transaction.objectStore(STORE).put({ interviewId, segment, index, blob })
        await finished(transaction)
        return true
      }),

    /** The recordings kept for an interview: [{ segment, chunks, bytes }]. */
    segments: (interviewId) =>
      attempt([], async (db) => {
        const rows = await asPromise(
          db.transaction(STORE).objectStore(STORE).getAll(interviewRange(interviewId))
        )
        const found = new Map()
        for (const row of rows) {
          const entry = found.get(row.segment) ?? { segment: row.segment, chunks: 0, bytes: 0 }
          entry.chunks += 1
          entry.bytes += row.blob?.size ?? 0
          found.set(row.segment, entry)
        }
        return [...found.values()]
      }),

    /** The chunks of one recording, in the order they were recorded. */
    readSegment: (interviewId, segment) =>
      attempt([], async (db) => {
        const rows = await asPromise(
          db.transaction(STORE).objectStore(STORE).getAll(segmentRange(interviewId, segment))
        )
        return rows.map((row) => row.blob)
      }),

    /** Forgets one recording. */
    deleteSegment: (interviewId, segment) =>
      attempt(false, async (db) => {
        const transaction = db.transaction(STORE, 'readwrite')
        transaction.objectStore(STORE).delete(segmentRange(interviewId, segment))
        await finished(transaction)
        return true
      }),

    /** Forgets everything kept for an interview (it is over). */
    deleteInterview: (interviewId) =>
      attempt(false, async (db) => {
        const transaction = db.transaction(STORE, 'readwrite')
        transaction.objectStore(STORE).delete(interviewRange(interviewId))
        await finished(transaction)
        return true
      }),
  }
}
