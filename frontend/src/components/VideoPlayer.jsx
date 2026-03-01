import { useRef, useEffect } from 'react'
import videojs from 'video.js'
import 'video.js/dist/video-js.css'
import './VideoPlayer.css'

function VideoPlayer({ videoId, seekTime }) {
  const videoRef = useRef(null)
  const playerRef = useRef(null)

  useEffect(() => {
    // Make sure Video.js player is only initialized once
    if (!playerRef.current) {
      const videoElement = document.createElement('video')
      videoElement.classList.add('video-js', 'vjs-big-play-centered')
      videoElement.setAttribute('controls', '')
      videoElement.setAttribute('preload', 'auto')

      videoRef.current.appendChild(videoElement)

      const player = videojs(videoElement, {
        controls: true,
        responsive: true,
        fluid: true,
        preload: 'auto',
        html5: {
          vhs: {
            enableLowInitialPlaylist: true,
          },
        },
        controlBar: {
          pictureInPictureToggle: false,
        },
      })

      playerRef.current = player
    }
  }, [])

  // Update video source when videoId changes
  useEffect(() => {
    const player = playerRef.current

    if (player && !player.isDisposed() && videoId) {
      player.src({
        src: `/api/video/${videoId}`,
        type: 'video/mp4',
      })

      player.load()
    }
  }, [videoId])

  // Handle seeking when timestamp is clicked
  useEffect(() => {
    const player = playerRef.current

    if (player && !player.isDisposed() && seekTime !== undefined && seekTime !== null) {
      // Set current time directly without ready() since player is already initialized
      player.currentTime(seekTime)
      player.play().catch(err => {
        console.log('Play prevented:', err)
      })
    }
  }, [seekTime])

  // Dispose the player on unmount
  useEffect(() => {
    const player = playerRef.current

    return () => {
      if (player && !player.isDisposed()) {
        player.dispose()
        playerRef.current = null
      }
    }
  }, [])

  return (
    <div className="video-player-container">
      <div ref={videoRef} data-vjs-player />
    </div>
  )
}

export default VideoPlayer
