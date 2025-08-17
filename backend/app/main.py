from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
import json
import asyncio
import math
import time
from typing import Dict, List, Tuple
from dataclasses import dataclass, asdict

app = FastAPI()

# Disable CORS. Do not remove this for full-stack development.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)

@dataclass
class Player:
    id: str
    name: str
    position: Tuple[float, float, float]
    rotation: Tuple[float, float, float]
    speed: float
    sail_angle: float
    last_update: float

@dataclass
class GameState:
    players: Dict[str, Player]
    wind_direction: float
    wind_strength: float
    waves: float
    timestamp: float

class GameManager:
    def __init__(self):
        self.connections: Dict[str, WebSocket] = {}
        self.game_state = GameState(
            players={},
            wind_direction=45.0,
            wind_strength=15.0,
            waves=2.0,
            timestamp=time.time()
        )
        self.running = True
        
    async def connect(self, websocket: WebSocket, player_id: str):
        await websocket.accept()
        self.connections[player_id] = websocket
        
    def disconnect(self, player_id: str):
        if player_id in self.connections:
            del self.connections[player_id]
        if player_id in self.game_state.players:
            del self.game_state.players[player_id]
            
    async def add_player(self, player_id: str, name: str):
        player = Player(
            id=player_id,
            name=name,
            position=(0.0, 0.0, 0.0),
            rotation=(0.0, 0.0, 0.0),
            speed=0.0,
            sail_angle=0.0,
            last_update=time.time()
        )
        self.game_state.players[player_id] = player
        await self.broadcast_game_state()
        
    def update_player_input(self, player_id: str, keys: List[str]):
        if player_id not in self.game_state.players:
            return
            
        player = self.game_state.players[player_id]
        current_time = time.time()
        dt = current_time - player.last_update
        
        max_speed = 25.0
        acceleration = 5.0
        turn_speed = 2.0
        
        x, y, z = player.position
        rx, ry, rz = player.rotation
        
        if 'w' in keys:  # Forward
            wind_factor = self.calculate_wind_effect(player.sail_angle, self.game_state.wind_direction, ry)
            player.speed = min(max_speed, player.speed + acceleration * dt * wind_factor)
        elif 's' in keys:  # Backward
            player.speed = max(0, player.speed - acceleration * dt * 2)
        else:
            player.speed = max(0, player.speed - acceleration * dt * 0.5)  # Natural deceleration
            
        if 'a' in keys:  # Turn left
            ry -= turn_speed * dt
        if 'd' in keys:  # Turn right
            ry += turn_speed * dt
            
        if 'q' in keys:  # Adjust sail left
            player.sail_angle = max(-45, player.sail_angle - 30 * dt)
        if 'e' in keys:  # Adjust sail right
            player.sail_angle = min(45, player.sail_angle + 30 * dt)
            
        if player.speed > 0:
            x += math.sin(ry) * player.speed * dt
            z += math.cos(ry) * player.speed * dt
            
        wave_height = math.sin(current_time * 0.5 + x * 0.1) * 0.2
        y = wave_height
        
        player.position = (x, y, z)
        player.rotation = (rx, ry, rz)
        player.last_update = current_time
        
    def calculate_wind_effect(self, sail_angle: float, wind_direction: float, boat_heading: float) -> float:
        relative_wind = wind_direction - boat_heading
        optimal_sail_angle = relative_wind * 0.5
        
        angle_diff = abs(sail_angle - optimal_sail_angle)
        efficiency = max(0.1, 1.0 - (angle_diff / 45.0))
        
        wind_factor = self.game_state.wind_strength / 20.0
        
        return efficiency * wind_factor
        
    async def update_wind(self):
        current_time = time.time()
        self.game_state.wind_direction += math.sin(current_time * 0.1) * 0.5
        self.game_state.wind_strength = 15 + math.sin(current_time * 0.05) * 5
        self.game_state.waves = 2 + math.sin(current_time * 0.03) * 1
        self.game_state.timestamp = current_time
        
    async def broadcast_game_state(self):
        if not self.connections:
            return
            
        players_data = []
        for player in self.game_state.players.values():
            players_data.append({
                "id": player.id,
                "name": player.name,
                "position": list(player.position),
                "rotation": list(player.rotation),
                "speed": player.speed
            })
            
        message = {
            "type": "gameState",
            "gameState": {
                "players": players_data,
                "windDirection": self.game_state.wind_direction,
                "windStrength": self.game_state.wind_strength,
                "waves": self.game_state.waves
            }
        }
        
        disconnected = []
        for player_id, websocket in self.connections.items():
            try:
                await websocket.send_text(json.dumps(message))
            except:
                disconnected.append(player_id)
                
        for player_id in disconnected:
            self.disconnect(player_id)
            
    async def game_loop(self):
        while self.running:
            await self.update_wind()
            await self.broadcast_game_state()
            await asyncio.sleep(1/30)  # 30 FPS

game_manager = GameManager()

@app.on_event("startup")
async def startup_event():
    asyncio.create_task(game_manager.game_loop())

@app.get("/healthz")
async def healthz():
    return {"status": "ok"}

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    player_id = None
    try:
        await websocket.accept()
        
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)
            
            if message["type"] == "join":
                player_id = message["playerId"]
                player_name = message["name"]
                await game_manager.connect(websocket, player_id)
                await game_manager.add_player(player_id, player_name)
                
            elif message["type"] == "input" and player_id:
                keys = message["keys"]
                game_manager.update_player_input(player_id, keys)
                
    except WebSocketDisconnect:
        if player_id:
            game_manager.disconnect(player_id)
    except Exception as e:
        print(f"WebSocket error: {e}")
        if player_id:
            game_manager.disconnect(player_id)
