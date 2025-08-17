import { useState, useEffect, useRef, Suspense } from 'react'
import { Canvas } from '@react-three/fiber'
import { OrbitControls, Sky } from '@react-three/drei'
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
      <Canvas camera={{ position: [0, 10, 10], fov: 75 }}>
        <Suspense fallback={null}>
          <Sky sunPosition={[100, 20, 100]} />
          <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, 0, 0]}>
            <planeGeometry args={[1000, 1000]} />
            <meshStandardMaterial color="#006994" transparent opacity={0.8} />
          </mesh>
          
          {gameState.players.map((player) => (
            <group key={player.id} position={player.position} rotation={player.rotation}>
              <mesh>
                <boxGeometry args={[2, 0.2, 0.5]} />
                <meshStandardMaterial color={player.id === playerId ? "#ff6b6b" : "#4ecdc4"} />
              </mesh>
              <mesh position={[0, 1, 0]}>
                <planeGeometry args={[1, 2]} />
                <meshStandardMaterial color="#ffffff" transparent opacity={0.8} />
              </mesh>
            </group>
          ))}
          
          <ambientLight intensity={0.5} />
          <directionalLight position={[10, 10, 5]} intensity={1} />
          <OrbitControls enablePan={true} enableZoom={true} enableRotate={true} />
        </Suspense>
      </Canvas>

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
        <div className="game-info">3D graphics enabled with Three.js integration</div>
      </div>
    </div>
  )
}

export default App
