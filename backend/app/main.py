from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
import json
import asyncio
import math
import time
from typing import Dict, List, Tuple
from dataclasses import dataclass, asdict

def wrap_deg(a: float) -> float:
    return (a + 360.0) % 360.0

def heading_to_unit(heading_deg: float) -> Tuple[float, float]:
    r = math.radians(heading_deg)
    return (math.cos(r), math.sin(r))

def unit(vx, vy):
    s = math.hypot(vx, vy)
    return (0.0, 0.0) if s == 0 else (vx/s, vy/s)

def signed_angle_deg(ax, ay, bx, by):
    ang = math.degrees(math.atan2(ax*by - ay*bx, ax*bx + ay*by))
    return ang

def apparent_wind(world_wind_vec, boat_vel):
    return (world_wind_vec[0] - boat_vel[0],
            world_wind_vec[1] - boat_vel[1])

def polar_max_ratio(rel_deg):
    """
    Max boat speed / true wind as a smooth 'polar'.
    Peak ~2.5x on a beam reach (~90°), weaker upwind/downwind.
    """
    d = abs(((rel_deg + 180.0) % 360.0) - 180.0)  # 0..180
    r = 0.8 + 1.9 * (math.sin(math.radians(d)) ** 1.4)  # ~0.8..2.7
    return min(2.5, max(0.7, r))  # clamp ~[0.7, 2.5]

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

def compute_sail_force_with_heading(wind_speed: float, wind_dir_deg: float, boat_heading_deg: float, sail_angle_deg: float) -> Tuple[float, float]:
    rel_wind_deg = wrap_deg(wind_dir_deg - boat_heading_deg)
    alpha = wrap_deg(rel_wind_deg - sail_angle_deg)  # angle of attack proxy

    c = 0.015  # tuned constant
    drive = c * (wind_speed ** 2) * max(0.0, math.sin(math.radians(2 * min(alpha, 180 - alpha))))

    side = 0.6 * c * (wind_speed ** 2) * math.sin(math.radians(alpha))

    fx_b, fy_b = drive, side
    hx, hy = heading_to_unit(boat_heading_deg)
    fx = fx_b * hx - fy_b * hy
    fy = fx_b * hy + fy_b * hx
    return (fx, fy)

def compute_water_drag(velocity: Tuple[float, float]) -> Tuple[float, float]:
    vx, vy = velocity
    speed = math.hypot(vx, vy)
    if speed == 0:
        return (0.0, 0.0)
    CdA = 0.2  # tuned
    mag = CdA * (speed ** 2)
    return (-mag * vx / speed, -mag * vy / speed)

def compute_foil_lift(velocity: Tuple[float, float]) -> float:
    speed = math.sqrt(velocity[0]**2 + velocity[1]**2)
    lift_coeff = 1.2
    return lift_coeff * speed**2

def vector_magnitude(velocity: Tuple[float, float]) -> float:
    return math.sqrt(velocity[0]**2 + velocity[1]**2)

def damp(v: Tuple[float, float], rate: float, dt: float) -> Tuple[float, float]:
    k = max(0.0, min(1.0, 1.0 - rate * dt))
    return (v[0] * k, v[1] * k)

def clamp_speed(v: Tuple[float, float], vmax: float) -> Tuple[float, float]:
    vx, vy = v
    s = math.hypot(vx, vy)
    if s <= vmax or s == 0:
        return v
    f = vmax / s
    return (vx * f, vy * f)

def compute_wave_current(position: Tuple[float, float, float], time: float, wave_strength: float) -> Tuple[float, float]:
    """Compute water current effects from wave motion"""
    x, y, z = position
    
    wave1_x = math.sin(time * 0.3 + x * 0.05) * wave_strength * 0.4
    wave1_z = math.cos(time * 0.3 + z * 0.05) * wave_strength * 0.3
    
    wave2_x = math.sin(time * 0.2 + x * 0.08 + z * 0.03) * wave_strength * 0.3
    wave2_z = math.cos(time * 0.2 + z * 0.08 + x * 0.03) * wave_strength * 0.2
    
    current_x = wave1_x + wave2_x
    current_z = wave1_z + wave2_z
    
    return (current_x, current_z)

def compute_enhanced_wave_height(position: Tuple[float, float, float], time: float, wave_strength: float, foiling: bool) -> float:
    """Compute realistic wave height with multiple wave systems"""
    x, y, z = position
    
    primary_wave = math.sin(time * 0.5 + x * 0.1) * wave_strength * 0.3
    
    cross_wave = math.sin(time * 0.3 + z * 0.08 + x * 0.02) * wave_strength * 0.2
    
    chop = math.sin(time * 1.2 + x * 0.15 + z * 0.12) * wave_strength * 0.1
    
    base_height = primary_wave + cross_wave + chop
    
    if foiling:
        foil_height = 0.8 + base_height * 0.3  # Foils follow wave contours but elevated
    else:
        foil_height = base_height
        
    return foil_height

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
        
    def update_player_input(self, player_id: str, keys: List[str], mouse_data: dict = None):
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
        ry = wrap_deg(ry)
            
        if mouse_data:
            player.sail_angle = mouse_data.get('sailAngle', 0) * 45
            sail_power_multiplier = mouse_data.get('sailPower', 1.0)
            mouse_pressed = mouse_data.get('pressed', False)
        else:
            sail_power_multiplier = 1.0
            mouse_pressed = False
            if 'q' in keys:
                player.sail_angle = max(-45, player.sail_angle - 30 * dt)
            if 'e' in keys:
                player.sail_angle = min(45, player.sail_angle + 30 * dt)
        
        sail_force = compute_sail_force_with_heading(
            self.game_state.wind_strength,
            self.game_state.wind_direction,
            ry,  # boat heading in degrees
            player.sail_angle
        )
        drag_force = compute_water_drag(player.board_velocity)
        
        wave_current = compute_wave_current(player.position, current_time, self.game_state.waves)
        current_force = (wave_current[0] * 0.5, wave_current[1] * 0.5)  # Scale current influence
        
        wx, wz = heading_to_unit(self.game_state.wind_direction)
        true_wind_vec = (wx * self.game_state.wind_strength, wz * self.game_state.wind_strength)
        
        hx, hz = heading_to_unit(ry)
        
        awx, awz = apparent_wind(true_wind_vec, player.board_velocity)
        
        rel_aw_deg = abs(signed_angle_deg(hx, hz, awx, awz))
        
        total_force = (sail_force[0] + drag_force[0] + current_force[0], 
                      sail_force[1] + drag_force[1] + current_force[1])
        
        total_force = (total_force[0] * sail_power_multiplier, total_force[1] * sail_power_multiplier)
        if mouse_pressed:
            total_force = (total_force[0] * 1.2, total_force[1] * 1.2)
        
        if not player.foiling:
            weight_factor = 1.0 + (player.weight_shift * -0.3)
            total_force = (total_force[0] * weight_factor, total_force[1] * weight_factor)
        
        speed = vector_magnitude(player.board_velocity)
        if speed > 5.0:
            if not player.foiling:
                player.foiling = True
                print(f"Player {player.id} entering foiling mode at {speed:.1f} knots")
            
            lift = compute_foil_lift(player.board_velocity)
            
            foil_efficiency = 1.4
            wave_sensitivity = 1.2
            
            total_force = (total_force[0] * foil_efficiency, total_force[1] * foil_efficiency)
            
            enhanced_current = (wave_current[0] * wave_sensitivity, wave_current[1] * wave_sensitivity)
            total_force = (total_force[0] + enhanced_current[0], total_force[1] + enhanced_current[1])
            
        else:
            player.foiling = False
        
        if player.foiling:
            if abs(player.weight_shift) > 0.7:
                player.foiling = False
                player.board_velocity = (player.board_velocity[0] * 0.75, player.board_velocity[1] * 0.75)
        
        v_target = polar_max_ratio(rel_aw_deg) * self.game_state.wind_strength  # ~<= 2.5× wind
        
        speed_now = vector_magnitude(player.board_velocity)
        speed_err = max(0.0, v_target - speed_now)
        
        kp = 18.0  # N per (speed unit); raise -> faster ramp, lower -> smoother
        control_force = (hx * kp * speed_err, hz * kp * speed_err)
        
        total_force = (total_force[0] + control_force[0], total_force[1] + control_force[1])
        
        if 'w' in keys:
            wind_factor = self.calculate_wind_effect(player.sail_angle, self.game_state.wind_direction, ry)
            acc = (total_force[0] / mass * wind_factor, total_force[1] / mass * wind_factor)
            if player.id == "ai_simulator":
                wave_curr = compute_wave_current(player.position, current_time, self.game_state.waves)
                print(f"AI: wind_factor={wind_factor:.2f}, speed={vector_magnitude(player.board_velocity):.2f}, foiling={player.foiling}, weight_shift={player.weight_shift:.2f}, wave_current=({wave_curr[0]:.2f},{wave_curr[1]:.2f})")
            player.board_velocity = (
                player.board_velocity[0] + acc[0] * dt,
                player.board_velocity[1] + acc[1] * dt
            )
        elif 's' in keys:
            player.board_velocity = damp(player.board_velocity, rate=2.0, dt=dt)
        else:
            player.board_velocity = damp(player.board_velocity, rate=0.5, dt=dt)
        
        max_speed_scaled = 2.6 * self.game_state.wind_strength
        player.board_velocity = clamp_speed(player.board_velocity, max_speed_scaled)
        player.speed = math.hypot(*player.board_velocity)
        
        effective_velocity = (
            player.board_velocity[0] + wave_current[0] * 0.1,  # Small direct current push
            player.board_velocity[1] + wave_current[1] * 0.1
        )
        
        x += effective_velocity[0] * dt
        z += effective_velocity[1] * dt
            
        y = compute_enhanced_wave_height(player.position, current_time, self.game_state.waves, player.foiling)
        
        player.position = (x, y, z)
        player.rotation = (rx, ry, rz)
        player.last_update = current_time
        
    def calculate_wind_effect(self, sail_angle: float, wind_direction: float, boat_heading: float) -> float:
        relative_wind = wrap_deg(wind_direction - boat_heading)
        optimal_sail_angle = relative_wind * 0.5
        angle_diff = abs(wrap_deg(sail_angle - optimal_sail_angle))
        efficiency = max(0.1, 1.0 - (angle_diff / 45.0))
        return efficiency
        
    async def update_wind(self):
        current_time = time.time()
        
        base_wind_shift = math.sin(current_time * 0.1) * 0.8
        gust_factor = math.sin(current_time * 0.15) * 0.3
        self.game_state.wind_direction = wrap_deg(self.game_state.wind_direction + base_wind_shift + gust_factor)
        
        base_strength = 15 + math.sin(current_time * 0.05) * 5
        gust_strength = math.sin(current_time * 0.2) * 3
        self.game_state.wind_strength = max(5, base_strength + gust_strength)
        
        wind_wave_factor = (self.game_state.wind_strength - 10) * 0.1
        wave_period = math.sin(current_time * 0.03) * 1.5
        swell_component = math.sin(current_time * 0.008) * 0.8  # Long period swell
        
        self.game_state.waves = max(0.5, 2 + wind_wave_factor + wave_period + swell_component)
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
                "sailAngle": player.sail_angle,
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
        # self.create_ai_player()
        last = time.time()
        
        while self.running:
            now = time.time()
            dt = max(1/120, min(1/20, now - last))  # clamp dt
            last = now
            
            # if self.ai_player_id:
            #     ai_keys = self.simulate_ai_input()
            #     if ai_keys:
            #         self.update_player_input(self.ai_player_id, ai_keys)
            
            await self.update_wind()

            for p in list(self.game_state.players.values()):
                # Apply passive drag and small wave current push
                wave_current = compute_wave_current(p.position, now, self.game_state.waves)
                drag = compute_water_drag(p.board_velocity)
                mass = 80.0

                ax = (drag[0] + 0.1 * wave_current[0]) / mass
                ay = (drag[1] + 0.1 * wave_current[1]) / mass
                p.board_velocity = (p.board_velocity[0] + ax * dt, p.board_velocity[1] + ay * dt)
                p.board_velocity = clamp_speed(p.board_velocity, 25.0)

                x, y, z = p.position
                x += p.board_velocity[0] * dt + 0.1 * wave_current[0] * dt
                z += p.board_velocity[1] * dt + 0.1 * wave_current[1] * dt
                y = compute_enhanced_wave_height((x, y, z), now, self.game_state.waves, p.foiling)
                p.position = (x, y, z)
                p.last_update = now

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
                mouse_data = message.get("mouse", None)
                if player_id != "ai_simulator":  # Don't log AI input to reduce spam
                    print(f"DEBUG: Received input message - player_id={player_id}, keys={keys}, mouse={mouse_data}")
                game_manager.update_player_input(player_id, keys, mouse_data)
                
    except WebSocketDisconnect:
        if player_id:
            game_manager.disconnect(player_id)
    except Exception as e:
        print(f"WebSocket error: {e}")
        if player_id:
            game_manager.disconnect(player_id)
