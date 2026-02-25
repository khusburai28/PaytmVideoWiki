import { useRef, useEffect } from 'react'
import ReactPlayer from 'react-player'
import './VideoPlayer.css'

function VideoPlayer({ videoId, seekTime }) {
  const playerRef = useRef(null)

  useEffect(() => {
    if (playerRef.current && seekTime !== undefined && seekTime !== null) {
      playerRef.current.seekTo(seekTime, 'seconds')
    }
  }, [seekTime])

  return (
    <div className="video-player-container">
      <ReactPlayer
        ref={playerRef}
        url={`/api/video/${videoId}`}
        controls
        width="100%"
        height="100%"
        playing={seekTime !== undefined && seekTime !== null}
        config={{
          file: {
            attributes: {
              controlsList: 'nodownload'
            }
          }
        }}
      />
    </div>
  )
}

export default VideoPlayer
