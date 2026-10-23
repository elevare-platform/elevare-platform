import { clipTitle } from '@/lib/recordingClips'

/**
 * RecordingClips - one player per attempt of a reinstated strict interview, each titled, with a
 * line saying why there are several. The server sends the clips oldest first.
 */
export default function RecordingClips({ recordings, videoClassName = 'w-full rounded-xl overflow-hidden bg-black aspect-video' }) {
  return (
    <section aria-label="Recordings" className="space-y-3">
      <p className="text-xs text-text-muted">
        This interview was reinstated, so each attempt has its own recording. The second one carries
        on where the first stopped.
      </p>
      {recordings.map((clip) => (
        <div key={clip.attempt}>
          <p className="mb-1 text-xs font-semibold text-text">{clipTitle(clip.attempt)}</p>
          <video src={clip.video_url} controls preload="metadata" className={videoClassName}>
            Your browser does not support inline video playback.
          </video>
        </div>
      ))}
    </section>
  )
}
