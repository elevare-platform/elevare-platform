// Run in Node, not jsdom: jsdom's Blob does not survive IndexedDB's structured clone, while the
// browsers this runs in (Chrome and Edge) store a Blob fine, and Node's own Blob behaves like theirs.
// @vitest-environment node
import 'fake-indexeddb/auto'
import { IDBFactory } from 'fake-indexeddb'
import { describe, it, expect, beforeEach } from 'vitest'
import { openRecordingStore } from './recordingStore'

const chunk = (text) => new Blob([text], { type: 'video/webm' })
const text = (blob) => blob.text()

describe('the recording store', () => {
  let store
  beforeEach(() => {
    store = openRecordingStore(new IDBFactory())
  })

  it('hands back the chunks of a recording in the order they were recorded', async () => {
    await store.addChunk('iv-1', 'seg-a', 2, chunk('C'))
    await store.addChunk('iv-1', 'seg-a', 0, chunk('A'))
    await store.addChunk('iv-1', 'seg-a', 1, chunk('B'))

    const chunks = await store.readSegment('iv-1', 'seg-a')

    expect(await Promise.all(chunks.map(text))).toEqual(['A', 'B', 'C'])
  })

  it('orders chunks as numbers, so the tenth chunk comes after the ninth', async () => {
    for (const index of [10, 9, 2, 1]) await store.addChunk('iv-1', 'seg-a', index, chunk(`c${index}`))

    const chunks = await store.readSegment('iv-1', 'seg-a')

    expect(await Promise.all(chunks.map(text))).toEqual(['c1', 'c2', 'c9', 'c10'])
  })

  it('says it kept a chunk', async () => {
    expect(await store.addChunk('iv-1', 'seg-a', 0, chunk('A'))).toBe(true)
  })

  it('lists the recordings kept for an interview, each with its size', async () => {
    await store.addChunk('iv-1', 'seg-a', 0, chunk('AAAA'))
    await store.addChunk('iv-1', 'seg-a', 1, chunk('BB'))
    await store.addChunk('iv-1', 'seg-b', 0, chunk('C'))

    const segments = await store.segments('iv-1')

    expect(segments).toEqual(
      expect.arrayContaining([
        { segment: 'seg-a', chunks: 2, bytes: 6 },
        { segment: 'seg-b', chunks: 1, bytes: 1 },
      ])
    )
    expect(segments).toHaveLength(2)
  })

  it('keeps one interview apart from another', async () => {
    await store.addChunk('iv-1', 'seg-a', 0, chunk('mine'))
    await store.addChunk('iv-2', 'seg-a', 0, chunk('theirs'))

    expect(await store.segments('iv-1')).toHaveLength(1)
    expect(await Promise.all((await store.readSegment('iv-2', 'seg-a')).map(text))).toEqual(['theirs'])
  })

  it('keeps two recordings of one interview apart, so a reload never mixes them', async () => {
    await store.addChunk('iv-1', 'before', 0, chunk('old'))
    await store.addChunk('iv-1', 'after', 0, chunk('new'))

    expect(await Promise.all((await store.readSegment('iv-1', 'before')).map(text))).toEqual(['old'])
    expect(await Promise.all((await store.readSegment('iv-1', 'after')).map(text))).toEqual(['new'])
  })

  it('forgets one recording and leaves the others', async () => {
    await store.addChunk('iv-1', 'before', 0, chunk('old'))
    await store.addChunk('iv-1', 'after', 0, chunk('new'))

    expect(await store.deleteSegment('iv-1', 'before')).toBe(true)

    expect((await store.segments('iv-1')).map((entry) => entry.segment)).toEqual(['after'])
  })

  it('forgets everything for an interview that is over, and nothing for another', async () => {
    await store.addChunk('iv-1', 'a', 0, chunk('1'))
    await store.addChunk('iv-1', 'b', 0, chunk('2'))
    await store.addChunk('iv-2', 'a', 0, chunk('3'))

    await store.deleteInterview('iv-1')

    expect(await store.segments('iv-1')).toEqual([])
    expect(await store.segments('iv-2')).toHaveLength(1)
  })

  it('keeps what it was given across a close and reopen, which is what survives a reload', async () => {
    const factory = new IDBFactory()
    await openRecordingStore(factory).addChunk('iv-1', 'seg-a', 0, chunk('kept'))

    const reopened = openRecordingStore(factory)

    expect(await Promise.all((await reopened.readSegment('iv-1', 'seg-a')).map(text))).toEqual(['kept'])
  })

  it('has nothing for an interview it has never seen', async () => {
    expect(await store.segments('nobody')).toEqual([])
    expect(await store.readSegment('nobody', 'x')).toEqual([])
  })
})

describe('when the browser cannot keep a recording', () => {
  it('is simply not there, so the interview records in memory as before', () => {
    expect(openRecordingStore(null)).toBeNull()
  })

  it('never throws when storage fails, and says nothing was kept', async () => {
    const broken = { open: () => { throw new Error('storage is not allowed') } }
    const store = openRecordingStore(broken)

    expect(await store.addChunk('iv-1', 'a', 0, chunk('x'))).toBe(false)
    expect(await store.segments('iv-1')).toEqual([])
    expect(await store.readSegment('iv-1', 'a')).toEqual([])
    expect(await store.deleteSegment('iv-1', 'a')).toBe(false)
    expect(await store.deleteInterview('iv-1')).toBe(false)
  })

  it('never throws when opening fails asynchronously either', async () => {
    const failing = {
      open: () => {
        const request = {}
        queueMicrotask(() => request.onerror?.())
        return request
      },
    }
    const store = openRecordingStore(failing)

    expect(await store.addChunk('iv-1', 'a', 0, chunk('x'))).toBe(false)
  })
})
