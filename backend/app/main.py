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
    weight_shift: float
    board_velocity: Tuple[float, float]
    foiling: bool
    last_update: float

@dataclass
class GameState:
    players: Dict[str, Player]
    wind_direction: float
    wind_strength: float
    waves: float
    timestamp: float

def compute_sail_force(wind_speed: float, wind_dir: float, sail_angle: float) -> Tuple[float, float]:
    relative_angle = wind_dir - sail_angle
    fx = wind_speed * math.cos(math.radians(relative_angle))
    fy = wind_speed * math.sin(math.radians(relative_angle))
    return (fx, fy)

def compute_water_drag(velocity: Tuple[float, float]) -> Tuple[float, float]:
    drag_coeff = 0.8
    return (-drag_coeff * velocity[0], -drag_coeff * velocity[1])

def compute_foil_lift(velocity: Tuple[float, float]) -> float:
    speed = math.sqrt(velocity[0]**2 + velocity[1]**2)
    lift_coeff = 1.2
    return lift_coeff * speed**2

def vector_magnitude(velocity: Tuple[float, float]) -> float:
    return math.sqrt(velocity[0]**2 + velocity[1]**2)

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
        self.ai_player_id = None
        self.simulation_time = 0.0
        self.simulation_phase = "accelerating"
        
    async def connect(self, websocket: WebSocket, player_id: str):
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
            weight_shift=0.0,
            board_velocity=(0.0, 0.0),
            foiling=False,
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
        turn_speed = 2.0
        weight_shift_speed = 2.0
        mass = 80.0
        
        x, y, z = player.position
        rx, ry, rz = player.rotation
        
        if 'r' in keys:
            player.weight_shift = max(-1.0, player.weight_shift - weight_shift_speed * dt)
        elif 'f' in keys:
            player.weight_shift = min(1.0, player.weight_shift + weight_shift_speed * dt)
        else:
            if player.weight_shift > 0:
                player.weight_shift = max(0, player.weight_shift - weight_shift_speed * dt * 0.5)
            elif player.weight_shift < 0:
                player.weight_shift = min(0, player.weight_shift + weight_shift_speed * dt * 0.5)
        
        if 'a' in keys:
            ry -= turn_speed * dt
        if 'd' in keys:
            ry += turn_speed * dt
            
        if 'q' in keys:
            player.sail_angle = max(-45, player.sail_angle - 30 * dt)
        if 'e' in keys:
            player.sail_angle = min(45, player.sail_angle + 30 * dt)
        
        sail_force = compute_sail_force(self.game_state.wind_strength, self.game_state.wind_direction, player.sail_angle)
        drag_force = compute_water_drag(player.board_velocity)
        
        total_force = (sail_force[0] + drag_force[0], sail_force[1] + drag_force[1])
        
        if not player.foiling:
            weight_factor = 1.0 + (player.weight_shift * -0.3)
            total_force = (total_force[0] * weight_factor, total_force[1] * weight_factor)
        
        speed = vector_magnitude(player.board_velocity)
        if speed > 5.0:
            if not player.foiling:
                player.foiling = True
            lift = compute_foil_lift(player.board_velocity)
            total_force = (total_force[0] * 1.2, total_force[1] * 1.2)
        else:
            player.foiling = False
        
        if player.foiling:
            if abs(player.weight_shift) > 0.7:
                player.foiling = False
                player.board_velocity = (player.board_velocity[0] * 0.6, player.board_velocity[1] * 0.6)
        
        if 'w' in keys:
            wind_factor = self.calculate_wind_effect(player.sail_angle, self.game_state.wind_direction, ry)
            acc = (total_force[0] / mass * wind_factor, total_force[1] / mass * wind_factor)
            if player.id == "ai_simulator":
                print(f"AI: wind_factor={wind_factor:.2f}, speed={vector_magnitude(player.board_velocity):.2f}, foiling={player.foiling}, weight_shift={player.weight_shift:.2f}")
            player.board_velocity = (
                player.board_velocity[0] + acc[0] * dt,
                player.board_velocity[1] + acc[1] * dt
            )
        elif 's' in keys:
            player.board_velocity = (
                player.board_velocity[0] * (1 - 2 * dt),
                player.board_velocity[1] * (1 - 2 * dt)
            )
        else:
            player.board_velocity = (
                player.board_velocity[0] * (1 - 0.5 * dt),
                player.board_velocity[1] * (1 - 0.5 * dt)
            )
        
        player.speed = min(max_speed, vector_magnitude(player.board_velocity))
        
        x += player.board_velocity[0] * dt
        z += player.board_velocity[1] * dt
            
        if player.foiling:
            wave_height = math.sin(current_time * 0.5 + x * 0.1) * 0.2 + 0.5
        else:
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
                "speed": player.speed,
                "weightShift": player.weight_shift,
                "foiling": player.foiling
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
            
    def create_ai_player(self):
        """Create an AI-controlled player for simulation"""
        if self.ai_player_id is None:
            self.ai_player_id = "ai_simulator"
            ai_player = Player(
                id=self.ai_player_id,
                name="🤖 AI Windsurfer",
                position=(0.0, 0.0, 0.0),
                rotation=(0.0, 0.0, 0.0),
                speed=0.0,
                sail_angle=0.0,
                weight_shift=0.0,
                board_velocity=(0.0, 0.0),
                foiling=False,
                last_update=time.time()
            )
            self.game_state.players[self.ai_player_id] = ai_player
            print(f"AI Player created: {self.ai_player_id}")

    def simulate_ai_input(self) -> List[str]:
        """Generate AI input based on simulation phase and conditions"""
        if self.ai_player_id not in self.game_state.players:
            return []
            
        player = self.game_state.players[self.ai_player_id]
        keys = []
        
        self.simulation_time += 0.033  # 30 FPS intervals
        
        if self.simulation_phase == "accelerating":
            keys.append('w')  # Always accelerating
            keys.append('r')  # Weight forward for better acceleration
            
            if self.simulation_time % 2 < 1:
                keys.append('q')  # Adjust sail left
            else:
                keys.append('e')  # Adjust sail right
                
            if player.speed > 4.0:
                self.simulation_phase = "foiling"
                print(f"AI entering foiling phase at speed {player.speed}")
                
        elif self.simulation_phase == "foiling":
            keys.append('w')  # Continue forward
            
            if abs(player.weight_shift) > 0.3:
                if player.weight_shift > 0:
                    keys.append('r')  # Weight forward to center
                else:
                    keys.append('f')  # Weight back to center
            
            turn_cycle = (self.simulation_time % 10) / 10
            if turn_cycle < 0.3:
                keys.append('a')  # Turn left
            elif turn_cycle > 0.7:
                keys.append('d')  # Turn right
                
            if self.simulation_time > 15 and self.simulation_time < 17:
                keys.append('f')  # Intentional weight back to demonstrate crash
                
        elif self.simulation_phase == "turning":
            keys.append('w')  # Maintain speed
            
            if self.simulation_time % 8 < 4:
                keys.append('d')  # Turn right
            else:
                keys.append('a')  # Turn left
                
        if self.simulation_time > 30:
            self.simulation_time = 0
            self.simulation_phase = "accelerating"
            player.position = (0.0, 0.0, 0.0)
            player.rotation = (0.0, 0.0, 0.0)
            player.speed = 0.0
            player.board_velocity = (0.0, 0.0)
            player.weight_shift = 0.0
            player.foiling = False
            print("AI simulation reset - starting new cycle")
            
        return keys

    async def game_loop(self):
        self.create_ai_player()
        
        while self.running:
            if self.ai_player_id:
                ai_keys = self.simulate_ai_input()
                if ai_keys:
                    self.update_player_input(self.ai_player_id, ai_keys)
            
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
                if player_id != "ai_simulator":  # Don't log AI input to reduce spam
                    print(f"DEBUG: Received input message - player_id={player_id}, keys={keys}")
                game_manager.update_player_input(player_id, keys)
                
    except WebSocketDisconnect:
        if player_id:
            game_manager.disconnect(player_id)
    except Exception as e:
        print(f"WebSocket error: {e}")
        if player_id:
            game_manager.disconnect(player_id)
