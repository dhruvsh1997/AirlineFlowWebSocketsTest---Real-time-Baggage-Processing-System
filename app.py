from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.responses import JSONResponse
import asyncio
import uuid
import json
from datetime import datetime
from typing import Dict, List
import random

app = FastAPI()

# Dictionary to store task statuses and active WebSocket connections
task_statuses: Dict[str, Dict] = {}
active_connections: Dict[str, List[WebSocket]] = {}

# Simulated baggage processing stages
PROCESSING_STAGES = [
    "Baggage Check-in",
    "Security Screening",
    "Baggage Sorting",
    "Loading onto Aircraft",
    "Processing Complete"
]

class ConnectionManager:
    """Manages WebSocket connections for each task"""
    def __init__(self):
        self.active_connections: Dict[str, List[WebSocket]] = {}
    
    async def connect(self, websocket: WebSocket, task_id: str):
        await websocket.accept()
        if task_id not in self.active_connections:
            self.active_connections[task_id] = []
        self.active_connections[task_id].append(websocket)
        
        # Send current status immediately upon connection
        if task_id in task_statuses:
            await self.send_personal_message(task_statuses[task_id], websocket)
    
    def disconnect(self, websocket: WebSocket, task_id: str):
        if task_id in self.active_connections:
            self.active_connections[task_id].remove(websocket)
            if not self.active_connections[task_id]:
                del self.active_connections[task_id]
    
    async def send_personal_message(self, message: dict, websocket: WebSocket):
        await websocket.send_text(json.dumps(message))
    
    async def broadcast_to_task(self, message: dict, task_id: str):
        """Broadcast status update to all connected clients for this task"""
        if task_id in self.active_connections:
            for connection in self.active_connections[task_id]:
                try:
                    await connection.send_text(json.dumps(message))
                except:
                    # Connection might be closed, remove it
                    self.active_connections[task_id].remove(connection)

manager = ConnectionManager()

async def simulate_baggage_processing(task_id: str):
    """Simulate the baggage processing stages with delays"""
    # Initialize task status
    task_statuses[task_id] = {
        "task_id": task_id,
        "stage": 0,
        "stage_name": PROCESSING_STAGES[0],
        "progress": 0,
        "status": "Processing",
        "start_time": datetime.now().isoformat(),
        "estimated_completion": (datetime.now().timestamp() + 120),  # ~2 minutes
        "baggage_details": {
            "baggage_id": f"BAG-{random.randint(10000, 99999)}",
            "flight_number": f"FL-{random.randint(100, 999)}",
            "destination": random.choice(["New York", "London", "Tokyo", "Paris", "Sydney"]),
            "weight": f"{random.uniform(10, 30):.1f} kg",
            "priority": random.choice(["Normal", "Priority", "Fragile"])
        }
    }
    
    # Broadcast initial status
    await manager.broadcast_to_task(task_statuses[task_id], task_id)
    
    # Simulate processing stages with appropriate delays
    # Total time will be between 1:20 and 2 minutes
    stage_times = [
        random.randint(20, 30),   # Stage 1: 20-30 seconds
        random.randint(25, 35),   # Stage 2: 25-35 seconds
        random.randint(20, 30),   # Stage 3: 20-30 seconds
        random.randint(25, 35)    # Stage 4: 25-35 seconds
    ]
    
    for stage in range(4):  # Only 4 stages of actual processing
        # Update status for current stage
        task_statuses[task_id]["stage"] = stage
        task_statuses[task_id]["stage_name"] = PROCESSING_STAGES[stage]
        task_statuses[task_id]["progress"] = (stage / 4) * 100  # 0-100%
        
        # Broadcast status update
        await manager.broadcast_to_task(task_statuses[task_id], task_id)
        
        # Simulate processing time for this stage
        await asyncio.sleep(stage_times[stage])
    
    # Final stage - Processing Complete
    task_statuses[task_id]["stage"] = 4
    task_statuses[task_id]["stage_name"] = PROCESSING_STAGES[4]
    task_statuses[task_id]["progress"] = 100
    task_statuses[task_id]["status"] = "Completed"
    task_statuses[task_id]["completion_time"] = datetime.now().isoformat()
    
    # Broadcast final status
    await manager.broadcast_to_task(task_statuses[task_id], task_id)
    
    # Keep the status for a while after completion
    await asyncio.sleep(300)  # 5 minutes
    if task_id in task_statuses:
        del task_statuses[task_id]

@app.post("/process")
async def start_processing():
    """Start the baggage processing task and return task ID"""
    task_id = str(uuid.uuid4())
    
    # Start the background task
    asyncio.create_task(simulate_baggage_processing(task_id))
    
    return JSONResponse({
        "task_id": task_id,
        "message": "Baggage processing started",
        "websocket_url": f"/ws/status/{task_id}",
        "instruction": "Connect to the WebSocket URL to receive real-time status updates"
    })

@app.websocket("/ws/status/{task_id}")
async def websocket_status(websocket: WebSocket, task_id: str):
    """WebSocket endpoint for real-time status updates"""
    await manager.connect(websocket, task_id)
    try:
        # Keep the connection open to receive updates
        while True:
            # This keeps the connection alive and allows the server to send messages
            await asyncio.sleep(1)
    except WebSocketDisconnect:
        manager.disconnect(websocket, task_id)

@app.get("/")
async def root():
    return {"message": "Airline Baggage Processing System API"}

# Optional: HTTP endpoint for status checking (fallback only)
@app.get("/status/{task_id}")
async def get_status(task_id: str):
    """Get current status of a task via HTTP (fallback for non-WebSocket clients)"""
    if task_id not in task_statuses:
        raise HTTPException(status_code=404, detail="Task not found")
    
    return task_statuses[task_id]


#pip install uvicorn[standard]
#ws://127.0.0.1:7000/ws/status/{task_id}