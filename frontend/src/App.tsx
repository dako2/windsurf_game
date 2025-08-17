import { useState, useEffect, useRef } from 'react'
import './App.css'

interface Player {
  id: string
  position: [number, number, number]
  rotation: [number, number, number]
  speed: number
  name: string
}

interface GameState {
  players: Player[]
  windDirection: number
  windStrength: number
  waves: number
}

function App() {
  const [gameState, setGameState] = useState<GameState>({
    players: [],
    windDirection: 45,
    windStrength: 15,
    waves: 2
  })
  const [playerId] = useState(() => Math.random().toString(36).substr(2, 9))
  const [connected, setConnected] = useState(false)
  const [ws, setWs] = useState<WebSocket | null>(null)
  const keysPressed = useRef<Set<string>>(new Set())

  useEffect(() => {
    const connectWebSocket = () => {
      const websocket = new WebSocket('wss://app-faernnul.fly.dev/ws')
      
      websocket.onopen = () => {
        console.log('Connected to game server')
        setConnected(true)
        websocket.send(JSON.stringify({
          type: 'join',
          playerId,
          name: `Player ${playerId.slice(0, 4)}`
        }))
      }
      
      websocket.onmessage = (event) => {
        const data = JSON.parse(event.data)
        if (data.type === 'gameState') {
          setGameState(data.gameState)
        }
      }
      
      websocket.onclose = () => {
        console.log('Disconnected from game server')
        setConnected(false)
        setTimeout(connectWebSocket, 3000)
      }
      
      websocket.onerror = (error) => {
        console.error('WebSocket error:', error)
      }
      
      setWs(websocket)
    }

    connectWebSocket()

    return () => {
      if (ws) {
        ws.close()
      }
    }
  }, [playerId])

  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      keysPressed.current.add(event.key.toLowerCase())
    }

    const handleKeyUp = (event: KeyboardEvent) => {
      keysPressed.current.delete(event.key.toLowerCase())
    }

    window.addEventListener('keydown', handleKeyDown)
    window.addEventListener('keyup', handleKeyUp)

    return () => {
      window.removeEventListener('keydown', handleKeyDown)
      window.removeEventListener('keyup', handleKeyUp)
    }
  }, [])

  useEffect(() => {
    const gameLoop = setInterval(() => {
      if (ws && connected) {
        const keys = Array.from(keysPressed.current)
        if (keys.length > 0) {
          ws.send(JSON.stringify({
            type: 'input',
            playerId,
            keys
          }))
        }
      }
    }, 50)

    return () => clearInterval(gameLoop)
  }, [ws, connected, playerId])

  const playerData = gameState.players.find(p => p.id === playerId)
  const windArrow = `→`.repeat(Math.floor(gameState.windStrength / 5))

  return (
    <div className="game-container">
      <div className="game-ui">
        <h2>3D Windsurfing Game</h2>
        <div>Speed: {playerData ? Math.round(playerData.speed) : 0} knots</div>
        <div>Players Online: {gameState.players.length}</div>
      </div>

      <div className="wind-indicator">
        <div>Wind</div>
        <div style={{ transform: `rotate(${gameState.windDirection}deg)` }}>
          {windArrow}
        </div>
        <div>{gameState.windStrength} knots</div>
      </div>

      <div className="controls">
        <div><strong>Controls:</strong></div>
        <div>W/S - Forward/Backward</div>
        <div>A/D - Turn Left/Right</div>
        <div>Q/E - Adjust Sail</div>
      </div>

      <div className="multiplayer-info">
        <div>Status: {connected ? '🟢 Connected' : '🔴 Connecting...'}</div>
        <div>Player ID: {playerId.slice(0, 8)}</div>
      </div>

      <div className="main-content">
        <div className="game-title">🏄‍♂️ Windsurfing Game</div>
        <div className="game-status">
          Real-time multiplayer backend is running!
        </div>
        <div className="game-info">
          3D graphics temporarily disabled due to Three.js compatibility issues
        </div>
        <div className="game-instructions">
          Use WASD keys to control your windsurfer
        </div>
        
        {gameState.players.length > 0 && (
          <div className="active-players">
            <h3>Active Players:</h3>
            {gameState.players.map((player) => (
              <div key={player.id} className={`player-card ${player.id === playerId ? 'current-player' : 'other-player'}`}>
                <div>{player.name} {player.id === playerId ? '(You)' : ''}</div>
                <div>Position: ({Math.round(player.position[0])}, {Math.round(player.position[2])})</div>
                <div>Speed: {Math.round(player.speed)} knots</div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

export default App
