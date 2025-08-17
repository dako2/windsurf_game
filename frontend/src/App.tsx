import { useState, useEffect, useRef } from 'react'
import './App.css'

interface Player {
  id: string
  position: [number, number, number]
  rotation: [number, number, number]
  speed: number
  name: string
  weightShift?: number
  foiling?: boolean
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
  const [keysPressedDisplay, setKeysPressedDisplay] = useState<string[]>([])
  const [sailAdjustment, setSailAdjustment] = useState(0)
  const canvasRef = useRef<HTMLCanvasElement>(null)

  useEffect(() => {
    const connectWebSocket = () => {
      const websocket = new WebSocket(import.meta.env.VITE_WS_URL || 'ws://localhost:8000/ws')
      
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
      console.log('Key down detected:', event.key)
      event.preventDefault()
      keysPressed.current.add(event.key.toLowerCase())
      setKeysPressedDisplay(Array.from(keysPressed.current))
      
      if (event.key.toLowerCase() === 'q') {
        setSailAdjustment(prev => {
          const newValue = Math.max(prev - 0.3, -2.0)
          console.log('Q pressed - Sail adjustment:', newValue)
          return newValue
        })
      } else if (event.key.toLowerCase() === 'e') {
        setSailAdjustment(prev => {
          const newValue = Math.min(prev + 0.3, 2.0)
          console.log('E pressed - Sail adjustment:', newValue)
          return newValue
        })
      }
    }

    const handleKeyUp = (event: KeyboardEvent) => {
      console.log('Key up detected:', event.key)
      event.preventDefault()
      keysPressed.current.delete(event.key.toLowerCase())
      setKeysPressedDisplay(Array.from(keysPressed.current))
    }

    console.log('Adding keyboard event listeners to document')
    document.addEventListener('keydown', handleKeyDown, true)
    document.addEventListener('keyup', handleKeyUp, true)

    return () => {
      console.log('Removing keyboard event listeners from document')
      document.removeEventListener('keydown', handleKeyDown, true)
      document.removeEventListener('keyup', handleKeyUp, true)
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

  // const playerData = gameState.players.find(p => p.id === playerId) // Unused in AI simulator mode
  const windArrow = `→`.repeat(Math.floor(gameState.windStrength / 5))
  
  const calculateSailAngle = (windDirection: number, playerRotation: number = 0, isCurrentPlayer: boolean = false) => {
    const windRad = (windDirection * Math.PI) / 180
    const playerRad = (playerRotation * Math.PI) / 180
    const relativeWind = windRad - playerRad
    const baseAngle = Math.sin(relativeWind) * 2.0
    
    const adjustment = isCurrentPlayer ? sailAdjustment * 2.0 : 0
    const finalAngle = baseAngle + adjustment
    
    return finalAngle
  }

  const drawWindsurfer = (ctx: CanvasRenderingContext2D, x: number, y: number, rotation: number, isCurrentPlayer: boolean, foiling: boolean) => {
    ctx.save()
    ctx.translate(x, y)
    ctx.rotate(rotation)
    
    ctx.fillStyle = isCurrentPlayer ? "#ff6b6b" : "#4ecdc4"
    if (foiling) {
      ctx.shadowColor = "rgba(0,0,0,0.3)"
      ctx.shadowBlur = 8
      ctx.shadowOffsetY = 4
    }
    ctx.fillRect(-15, -3, 30, 6)
    
    const sailAngle = calculateSailAngle(gameState.windDirection, rotation * 180 / Math.PI, isCurrentPlayer)
    ctx.save()
    ctx.rotate(sailAngle)
    ctx.fillStyle = "#ffffff"
    ctx.strokeStyle = "#cccccc"
    ctx.lineWidth = 1
    ctx.beginPath()
    ctx.moveTo(0, -20)
    ctx.lineTo(-12, 15)
    ctx.lineTo(12, 15)
    ctx.closePath()
    ctx.fill()
    ctx.stroke()
    ctx.restore()
    
    ctx.strokeStyle = "#8B4513"
    ctx.lineWidth = 2
    ctx.beginPath()
    ctx.moveTo(0, -20)
    ctx.lineTo(0, 15)
    ctx.stroke()
    
    ctx.fillStyle = "#ffeb3b"
    ctx.beginPath()
    ctx.arc(0, -8, 4, 0, 2 * Math.PI)
    ctx.fill()
    
    if (foiling) {
      ctx.fillStyle = "rgba(135, 206, 235, 0.6)"
      ctx.beginPath()
      ctx.arc(0, 0, 25, 0, 2 * Math.PI)
      ctx.fill()
    }
    
    ctx.restore()
  }

  const drawWaves = (ctx: CanvasRenderingContext2D, time: number) => {
    const canvas = ctx.canvas
    ctx.strokeStyle = "rgba(255, 255, 255, 0.3)"
    ctx.lineWidth = 1
    
    for (let i = 0; i < 5; i++) {
      ctx.beginPath()
      for (let x = 0; x < canvas.width; x += 10) {
        const waveHeight = Math.sin((x + time * 100 + i * 100) * 0.01) * 8
        const y = canvas.height / 2 + waveHeight + i * 20
        if (x === 0) ctx.moveTo(x, y)
        else ctx.lineTo(x, y)
      }
      ctx.stroke()
    }
  }

  const drawBuoys = (ctx: CanvasRenderingContext2D, centerX: number, centerY: number) => {
    const buoys = [
      { x: centerX + 100, y: centerY + 100 },
      { x: centerX - 150, y: centerY + 80 },
      { x: centerX + 50, y: centerY - 120 }
    ]
    
    ctx.fillStyle = "#ff9800"
    buoys.forEach(buoy => {
      ctx.beginPath()
      ctx.arc(buoy.x, buoy.y, 8, 0, 2 * Math.PI)
      ctx.fill()
    })
  }

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return

    const ctx = canvas.getContext('2d')
    if (!ctx) return

    const animate = () => {
      ctx.fillStyle = "#006994"
      ctx.fillRect(0, 0, canvas.width, canvas.height)
      
      drawWaves(ctx, Date.now())
      
      const centerX = canvas.width / 2
      const centerY = canvas.height / 2
      
      drawBuoys(ctx, centerX, centerY)
      
      gameState.players.forEach(player => {
        const screenX = centerX + player.position[0] * 10
        const screenY = centerY + player.position[2] * 10
        const rotation = player.rotation[1]
        const isCurrentPlayer = player.id === playerId
        const foiling = player.foiling || false
        
        drawWindsurfer(ctx, screenX, screenY, rotation, isCurrentPlayer, foiling)
      })
      
      if (gameState.players.length === 0) {
        drawWindsurfer(ctx, centerX, centerY, 0, true, false)
      }
      
      requestAnimationFrame(animate)
    }
    
    animate()
  }, [gameState, playerId, sailAdjustment])

  return (
    <div className="game-container">
      <canvas 
        ref={canvasRef}
        width={800}
        height={600}
        style={{ 
          border: '2px solid #333',
          borderRadius: '8px',
          background: 'linear-gradient(180deg, #87CEEB 0%, #006994 100%)'
        }}
      />

      <div className="game-ui">
        <h2>🤖 Automated Windsurf Simulator</h2>
        <div>AI Players: {gameState.players.filter(p => p.name.includes('AI')).length}</div>
        <div>Human Players: {gameState.players.filter(p => !p.name.includes('AI')).length}</div>
        <div>Total Players: {gameState.players.length}</div>
      </div>

      <div className="real-time-matrix">
        <div><strong>🤖 AI SIMULATOR DATA</strong></div>
        {gameState.players.map(player => (
          <div key={player.id} style={{ marginBottom: '10px', padding: '5px', border: player.name.includes('AI') ? '2px solid #00ff00' : '1px solid #ccc' }}>
            <div><strong>{player.name}</strong></div>
            <div>Position: ({Math.round(player.position[0])}, {Math.round(player.position[2])})</div>
            <div>Speed: {Math.round(player.speed * 10) / 10} knots</div>
            <div>Rotation: {Math.round(player.rotation[1] * 180 / Math.PI)}°</div>
            <div>Weight Shift: {player.weightShift ? Math.round(player.weightShift * 100) / 100 : 0}</div>
            <div>Foiling: {player.foiling ? '🦅 YES' : '🌊 NO'}</div>
          </div>
        ))}
        <div style={{ marginTop: '10px', borderTop: '1px solid #ccc', paddingTop: '5px' }}>
          <div>Wind Direction: {Math.round(gameState.windDirection)}°</div>
          <div>Wind Strength: {Math.round(gameState.windStrength * 10) / 10} knots</div>
          <div>Manual Keys: {keysPressedDisplay.join(', ') || 'None'}</div>
        </div>
      </div>

      <div className="wind-indicator">
        <div>Wind</div>
        <div style={{ transform: `rotate(${gameState.windDirection}deg)` }}>
          {windArrow}
        </div>
        <div>{gameState.windStrength} knots</div>
      </div>

      <div className="controls">
        <div><strong>🤖 Automated Simulator:</strong></div>
        <div>✅ AI demonstrates weight shift physics</div>
        <div>✅ AI shows foiling activation at speed</div>
        <div>✅ AI exhibits crash recovery</div>
        <div>✅ Dynamic wind conditions</div>
        <div style={{ marginTop: '10px', fontSize: '12px', color: '#888' }}>
          Manual controls still available: W/S/A/D/Q/E/R/F
        </div>
      </div>

      <div className="multiplayer-info">
        <div>Status: {connected ? '🟢 Connected' : '🔴 Connecting...'}</div>
        <div>Simulation: {connected ? '🤖 AI Running' : '⏸️ Paused'}</div>
        <div>Player ID: {playerId.slice(0, 8)}</div>
        <div className="game-info">Automated physics demonstration active</div>
      </div>
    </div>
  )
}

export default App
