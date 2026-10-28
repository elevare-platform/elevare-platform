import { describe, it, expect, vi } from 'vitest'
import { putBlob, withRetry, isRetryable, uploadRecording, describeUploadFailure, UploadError } from './interviewUpload'

// A minimal stand-in for XMLHttpRequest that finishes the way the test says.
function fakeXhrFactory(outcomes) {
  const queue = [...outcomes]
  const instances = []
  const createXhr = () => {
    const outcome = queue.shift() ?? { status: 200 }
    const xhr = {
      upload: {},
      headers: {},
      timeout: 0,
      open: vi.fn(),
      setRequestHeader(name, value) {
        this.headers[name] = value
      },
      send() {
        queueMicrotask(() => {
          for (const percent of outcome.progress ?? []) {
            xhr.upload.onprogress?.({ lengthComputable: true, loaded: percent, total: 100 })
          }
          if (outcome.error) xhr.onerror?.()
          else if (outcome.timeout) xhr.ontimeout?.()
          else {
            xhr.status = outcome.status
            xhr.onload?.()
          }
        })
      },
    }
    instances.push(xhr)
    return xhr
  }
  return { createXhr, instances }
}

const noWait = { sleep: () => Promise.resolve() }

describe('putBlob', () => {
  it('sends the blob with the signed content type and reports progress', async () => {
    const { createXhr, instances } = fakeXhrFactory([{ status: 200, progress: [10, 60, 100] }])
    const seen = []

    await putBlob({
      url: 'https://r2.example/upload',
      blob: new Blob(['x']),
      contentType: 'video/webm',
      onProgress: (p) => seen.push(p),
      createXhr,
    })

    expect(seen).toEqual([10, 60, 100])
    expect(instances[0].open).toHaveBeenCalledWith('PUT', 'https://r2.example/upload')
    expect(instances[0].headers['Content-Type']).toBe('video/webm')
  })

  it('rejects on a non-2xx answer, a dropped connection and a timeout', async () => {
    for (const outcome of [{ status: 403 }, { error: true }, { timeout: true }]) {
      const { createXhr } = fakeXhrFactory([outcome])
      await expect(
        putBlob({ url: 'u', blob: new Blob(['x']), contentType: 'video/webm', createXhr }),
      ).rejects.toThrow()
    }
  })
})

describe('putBlob, why it failed', () => {
  const failure = async (outcome) => {
    const { createXhr } = fakeXhrFactory([outcome])
    try {
      await putBlob({ url: 'u', blob: new Blob(['x']), contentType: 'video/webm', createXhr })
    } catch (err) {
      return err
    }
    return null
  }

  it('says the storage service refused it, with its code', async () => {
    const err = await failure({ status: 403 })
    expect(err).toBeInstanceOf(UploadError)
    expect([err.reason, err.status]).toEqual(['rejected', 403])
  })

  it('says the connection failed, or that the device is offline, or that it took too long', async () => {
    expect((await failure({ error: true })).reason).toBe('blocked_or_dropped')
    expect((await failure({ timeout: true })).reason).toBe('timeout')
    const online = vi.spyOn(navigator, 'onLine', 'get').mockReturnValue(false)
    expect((await failure({ error: true })).reason).toBe('offline')
    online.mockRestore()
  })
})

describe('describeUploadFailure', () => {
  const rejected = new UploadError('x', 403, 'rejected')

  it('tells where it failed: asking for the address, sending the file, or confirming it', () => {
    expect(describeUploadFailure(new Error('Network Error')).stage).toBe('url')
    expect(describeUploadFailure(rejected).stage).toBe('file')
    expect(describeUploadFailure(new Error('Network Error'), { fileUploaded: true }).stage).toBe('confirm')
  })

  it('explains each cause in plain words with what to try', () => {
    const message = (err) => describeUploadFailure(err).message
    expect(message(rejected)).toMatch(/did not accept the recording \(code 403\).*Retry upload.*tell your recruiter this code/)
    expect(message(new UploadError('x', undefined, 'blocked_or_dropped'))).toMatch(/firewall.*VPN.*hotspot.*Retry upload/)
    expect(message(new UploadError('x', undefined, 'offline'))).toMatch(/not connected to the internet/)
    expect(message(new UploadError('x', undefined, 'timeout'))).toMatch(/too long.*slow connection/)
    expect(message(new UploadError('x', undefined, 'interrupted'))).toMatch(/interrupted/)
    expect(message({ response: { status: 503, data: {} } })).toMatch(/Our server had a problem \(code 503\)/)
  })

  it('uses the server’s own words when it sent any', () => {
    const err = { response: { status: 422, data: { message: 'We did not receive your recording.' } } }
    expect(describeUploadFailure(err)).toMatchObject({ message: 'We did not receive your recording.', reason: 'other', status: 422 })
  })

  it('has nothing to say when it cannot tell, so the screen uses its own line', () => {
    expect(describeUploadFailure({ response: { status: 404, data: {} } }).message).toBeNull()
  })

  it('treats a request with no answer as a failed connection, or a timeout', () => {
    expect(describeUploadFailure(new Error('Network Error')).reason).toBe('blocked_or_dropped')
    expect(describeUploadFailure({ code: 'ECONNABORTED' }).reason).toBe('timeout')
  })
})

describe('isRetryable', () => {
  it('retries network, timeout and server errors but not client errors', () => {
    expect(isRetryable(new Error('network'))).toBe(true)
    expect(isRetryable({ response: { status: 503 } })).toBe(true)
    expect(isRetryable({ response: { status: 429 } })).toBe(true)
    expect(isRetryable({ response: { status: 422 } })).toBe(false)
    expect(isRetryable({ response: { status: 403 } })).toBe(false)
  })
})

describe('withRetry', () => {
  it('succeeds after transient failures and tells the caller about each retry', async () => {
    const fn = vi
      .fn()
      .mockRejectedValueOnce(new Error('drop'))
      .mockRejectedValueOnce(new Error('drop'))
      .mockResolvedValue('ok')
    const onRetry = vi.fn()

    await expect(withRetry(fn, { ...noWait, onRetry })).resolves.toBe('ok')
    expect(fn).toHaveBeenCalledTimes(3)
    expect(onRetry).toHaveBeenCalledTimes(2)
  })

  it('gives up after the last attempt and throws the final error', async () => {
    const fn = vi.fn().mockRejectedValue(new Error('still down'))

    await expect(withRetry(fn, { attempts: 3, ...noWait })).rejects.toThrow('still down')
    expect(fn).toHaveBeenCalledTimes(3)
  })

  it('does not retry an error a retry cannot fix', async () => {
    const fn = vi.fn().mockRejectedValue({ response: { status: 422 } })

    await expect(withRetry(fn, noWait)).rejects.toEqual({ response: { status: 422 } })
    expect(fn).toHaveBeenCalledTimes(1)
  })

  it('waits between attempts using the configured delays', async () => {
    const sleep = vi.fn().mockResolvedValue()
    const fn = vi.fn().mockRejectedValue(new Error('drop'))

    await expect(withRetry(fn, { attempts: 3, delaysMs: [10, 20], sleep })).rejects.toThrow()
    expect(sleep.mock.calls.map(([ms]) => ms)).toEqual([10, 20])
  })
})

describe('uploadRecording', () => {
  it('asks for a fresh upload URL on every attempt', async () => {
    const requestUploadUrl = vi
      .fn()
      .mockResolvedValueOnce({ upload_url: 'https://r2.example/first' })
      .mockResolvedValueOnce({ upload_url: 'https://r2.example/second' })
    const { createXhr, instances } = fakeXhrFactory([{ status: 403 }, { status: 200 }])

    await uploadRecording({
      requestUploadUrl,
      blob: new Blob(['x']),
      contentType: 'video/webm',
      createXhr,
      ...noWait,
    })

    expect(requestUploadUrl).toHaveBeenCalledTimes(2)
    expect(instances[0].open).toHaveBeenCalledWith('PUT', 'https://r2.example/first')
    expect(instances[1].open).toHaveBeenCalledWith('PUT', 'https://r2.example/second')
  })

  it('stops at once when the API refuses to issue an upload URL', async () => {
    const requestUploadUrl = vi.fn().mockRejectedValue({ response: { status: 422 } })

    await expect(
      uploadRecording({
        requestUploadUrl,
        blob: new Blob(['x']),
        contentType: 'video/webm',
        ...noWait,
      }),
    ).rejects.toBeTruthy()
    expect(requestUploadUrl).toHaveBeenCalledTimes(1)
  })
})
