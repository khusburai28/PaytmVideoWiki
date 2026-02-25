import { useRef, useEffect } from 'react'
import './VideoPlayer.css'

function VideoPlayer({ videoId, seekTime }) {
  const videoRef = useRef(null)

  useEffect(() => {
    if (videoRef.current && seekTime !== undefined) {
      videoRef.current.currentTime = seekTime
      videoRef.current.play()
    }
  }, [seekTime])

  return (
    <div className="video-player-container">
      <video
        ref={videoRef}
        className="video-player"
        controls
        controlsList="nodownload"
      >
        <source src={`/api/video/${videoId}`} type="video/mp4" />
        Your browser does not support the video tag.
      </video>
    </div>
  )
}

export default VideoPlayer
