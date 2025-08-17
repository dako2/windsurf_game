# 🏄‍♂️ Windsurf Game

A 3D real-time multiplayer online windsurfing game built with React, Three.js, and FastAPI.

## 🎮 Live Demo

- **Frontend:** https://windsurfing-game-9ersyjyp.devinapps.com/
- **Backend API:** https://app-faernnul.fly.dev/

## 🚀 Features

- **Real-time multiplayer** - Multiple players can join and compete simultaneously
- **WebSocket communication** - Live updates for player positions, wind conditions, and game state
- **Realistic wind mechanics** - Dynamic wind direction and strength affecting gameplay
- **Player controls** - WASD movement with sail adjustment (Q/E keys)
- **Visual feedback** - Speed indicators, wind display, and player tracking
- **Responsive design** - Works across different screen sizes and browsers

## 🏗️ Architecture

### Frontend (`/frontend`)
- **React** with TypeScript
- **Vite** for build tooling
- **WebSocket client** for real-time communication
- **CSS3** with responsive design and animations

### Backend (`/backend`)
- **FastAPI** with Python
- **WebSocket server** for real-time multiplayer
- **Game physics** including wind simulation and player movement
- **CORS enabled** for cross-origin requests

## 🛠️ Development

### Frontend Setup
```bash
cd frontend
npm install
npm run dev
```

### Backend Setup
```bash
cd backend
poetry install
poetry run fastapi dev app/main.py
```

## 🎯 Game Controls

- **W/S** - Move forward/backward
- **A/D** - Turn left/right
- **Q/E** - Adjust sail angle
- **Real-time multiplayer** - See other players' positions and movements

## 🌊 Game Mechanics

- **Wind System** - Dynamic wind affects speed and direction
- **Sail Physics** - Optimal sail angle relative to wind direction
- **Wave Simulation** - Realistic water movement
- **Player Physics** - Speed, acceleration, and turning mechanics

## 🚀 Deployment

Both frontend and backend are deployed and fully functional:
- Frontend deployed via static hosting
- Backend deployed on Fly.io with WebSocket support

## 🐛 Bug Fixes Applied

- ✅ Fixed CSS styling conflicts causing UI invisibility
- ✅ Replaced inline styles with proper CSS classes
- ✅ Improved z-index hierarchy for proper element layering
- ✅ Added responsive design with better visual contrast
- ✅ Enhanced text readability with shadows and color coding

## 🤝 Contributing

This project was developed as a proof-of-concept for real-time multiplayer web games. The codebase demonstrates modern web development practices with React, TypeScript, and FastAPI.

---

**Link to Devin run:** https://app.devin.ai/sessions/2cd8d184da6f4ec7995ab05e311cf01f  
**Developed by:** @dako2
