import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import RecordingClips from './RecordingClips'
import { clipTitle, showsClips } from '@/lib/recordingClips'

const CLIPS = [
  { attempt: 1, video_url: 'https://r2/one.webm' },
  { attempt: 2, video_url: 'https://r2/two.webm' },
]

describe('showsClips', () => {
  it('is for a reinstated interview with more than one recording', () => {
    expect(showsClips(CLIPS, 'https://r2/two.webm')).toBe(true)
  })

  it('is for an earlier attempt that is the only recording (the latest recorded nothing)', () => {
    expect(showsClips([CLIPS[0]], null)).toBe(true)
  })

  it('is not for an interview with one recording, or none, or an older server that sends no list', () => {
    expect(showsClips([CLIPS[0]], 'https://r2/one.webm')).toBe(false)
    expect(showsClips([], null)).toBe(false)
    expect(showsClips(undefined, 'https://r2/one.webm')).toBe(false)
  })
})

describe('RecordingClips', () => {
  it('shows one titled player per attempt, oldest first, and says why there are several', () => {
    const { container } = render(<RecordingClips recordings={CLIPS} />)

    const section = screen.getByRole('region', { name: 'Recordings' })
    expect(section).toHaveTextContent('each attempt has its own recording')
    const titles = screen.getAllByText(/^Attempt/).map((node) => node.textContent)
    expect(titles).toEqual(['Attempt 1', 'Attempt 2, after the interview was reinstated'])
    const players = container.querySelectorAll('video')
    expect([...players].map((video) => video.getAttribute('src'))).toEqual([
      'https://r2/one.webm',
      'https://r2/two.webm',
    ])
  })

  it('titles the first attempt plainly and later ones as after the reinstating', () => {
    expect(clipTitle(1)).toBe('Attempt 1')
    expect(clipTitle(3)).toBe('Attempt 3, after the interview was reinstated')
  })
})
