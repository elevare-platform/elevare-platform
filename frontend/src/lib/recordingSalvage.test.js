// Run in Node, not jsdom: see recordingStore.test.js.
// @vitest-environment node
import 'fake-indexeddb/auto'
import { IDBFactory } from 'fake-indexeddb'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { openRecordingStore } from './recordingStore'
import { MIN_USEFUL_BYTES, salvagePreviousRecordings } from './recordingSalvage'

const readText = (blob) => blob.text()

const big = (label) => new Blob([label.repeat(MIN_USEFUL_BYTES)], { type: 'video/webm' })

// withRetry that does not wait, and gives up after three tries like the real one.
const quickRetry = async (fn) => {
  let last
  for (let attempt = 0; attempt < 3; attempt += 1) {
    try {
      return await fn(attempt)
    } catch (err) {
      last = err
    }
  }
  throw last
}

describe('salvagePreviousRecordings', () => {
  let store
  let requestPartUploadUrl
  let putBlob

  beforeEach(() => {
    store = openRecordingStore(new IDBFactory())
    let part = 0
    requestPartUploadUrl = vi.fn(async () => ({ upload_url: `https://r2.test/part-${++part}`, part }))
    putBlob = vi.fn(async () => {})
  })

  const run = (extra = {}) =>
    salvagePreviousRecordings({
      store,
      interviewId: 'iv-1',
      currentSegment: 'now',
      requestPartUploadUrl,
      putBlob,
      withRetry: quickRetry,
      ...extra,
    })

  it('uploads an earlier recording as a part, in its original order, then forgets it', async () => {
    await store.addChunk('iv-1', 'before', 1, new Blob(['B'.repeat(MIN_USEFUL_BYTES)]))
    await store.addChunk('iv-1', 'before', 0, new Blob(['A'.repeat(MIN_USEFUL_BYTES)]))

    const result = await run()

    expect(result).toEqual({ uploaded: 1, failed: 0 })
    expect(putBlob).toHaveBeenCalledTimes(1)
    const sent = putBlob.mock.calls[0][0]
    expect(sent.url).toBe('https://r2.test/part-1')
    expect(sent.contentType).toBe('video/webm')
    const body = await readText(sent.blob)
    expect(body.startsWith('A')).toBe(true)
    expect(body.endsWith('B')).toBe(true)
    expect(await store.segments('iv-1')).toEqual([])
  })

  it('never touches the recording being made now', async () => {
    await store.addChunk('iv-1', 'now', 0, big('N'))

    const result = await run()

    expect(result).toEqual({ uploaded: 0, failed: 0 })
    expect(requestPartUploadUrl).not.toHaveBeenCalled()
    expect(await store.segments('iv-1')).toHaveLength(1)
  })

  it('sends each earlier recording as its own part, after two reloads', async () => {
    await store.addChunk('iv-1', 'first', 0, big('1'))
    await store.addChunk('iv-1', 'second', 0, big('2'))

    const result = await run()

    expect(result.uploaded).toBe(2)
    expect(putBlob.mock.calls.map((call) => call[0].url).sort()).toEqual([
      'https://r2.test/part-1',
      'https://r2.test/part-2',
    ])
  })

  it('does not send other interviews recordings', async () => {
    await store.addChunk('iv-2', 'before', 0, big('X'))

    await run()

    expect(putBlob).not.toHaveBeenCalled()
    expect(await store.segments('iv-2')).toHaveLength(1)
  })

  it('throws away a recording too small to be a video, without using up a part', async () => {
    await store.addChunk('iv-1', 'before', 0, new Blob(['tiny']))

    const result = await run()

    expect(result).toEqual({ uploaded: 0, failed: 0 })
    expect(requestPartUploadUrl).not.toHaveBeenCalled()
    expect(await store.segments('iv-1')).toEqual([])
  })

  it('keeps a recording that could not be sent, to try again next time, and still sends the others', async () => {
    await store.addChunk('iv-1', 'a-bad', 0, big('1'))
    await store.addChunk('iv-1', 'b-good', 0, big('2'))
    putBlob.mockImplementation(async ({ blob }) => {
      if ((await readText(blob)).startsWith('1')) throw new Error('the connection dropped')
    })

    const result = await run()

    expect(result).toEqual({ uploaded: 1, failed: 1 })
    expect((await store.segments('iv-1')).map((entry) => entry.segment)).toEqual(['a-bad'])
  })

  it('reserves the part once and retries the same address, so a poor connection cannot use up the parts', async () => {
    await store.addChunk('iv-1', 'before', 0, big('1'))
    putBlob.mockRejectedValueOnce(new Error('dropped')).mockRejectedValueOnce(new Error('dropped'))

    const result = await run()

    expect(result.uploaded).toBe(1)
    expect(requestPartUploadUrl).toHaveBeenCalledTimes(1)
    expect(putBlob).toHaveBeenCalledTimes(3)
    expect(new Set(putBlob.mock.calls.map((call) => call[0].url)).size).toBe(1)
  })

  it('keeps the recording when the server will not give an upload address', async () => {
    await store.addChunk('iv-1', 'before', 0, big('1'))
    requestPartUploadUrl.mockRejectedValue({ response: { status: 422, data: { code: 'INTERVIEW_TOO_MANY_PARTS' } } })

    const result = await run()

    expect(result).toEqual({ uploaded: 0, failed: 1 })
    expect(putBlob).not.toHaveBeenCalled()
    expect(await store.segments('iv-1')).toHaveLength(1)
  })

  it('does nothing, and does not fail, when the browser kept nothing', async () => {
    expect(await run({ store: null })).toEqual({ uploaded: 0, failed: 0 })
    expect(await run({ interviewId: null })).toEqual({ uploaded: 0, failed: 0 })
  })
})
