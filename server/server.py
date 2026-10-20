"""
Win-Merror Server
WebSocket server for screen streaming and remote control
"""

import asyncio
import json
import logging
import os
import base64
from typing import Dict, Set

import websockets

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Configuration
class Config:
    HOST = "0.0.0.0"
    PORT = 8080
    WEB_PORT = 8081
    MAX_CLIENTS = 10
    FRAME_QUALITY = 85  # JPEG quality (0-100)
    MAX_FRAME_SIZE = 2 * 1024 * 1024  # 2MB max frame size


class ServerState:
    """Track connected clients and viewers"""
    def __init__(self):
        self.viewers: Set[websockets.WebSocketServerProtocol] = set()
        self.client: websockets.WebSocketServerProtocol = None
        self.client_id: str = None

    async def broadcast_to_viewers(self, message: dict):
        """Send message to all connected viewers"""
        if not self.viewers:
            return
        
        message_str = json.dumps(message)
        disconnected = set()
        
        for viewer in self.viewers:
            try:
                await viewer.send(message_str)
            except (websockets.ConnectionClosed, Exception) as e:
                logger.warning(f"Error sending to viewer: {e}")
                disconnected.add(viewer)
        
        # Clean up disconnected viewers
        self.viewers -= disconnected

    async def send_to_client(self, message: dict):
        """Send message to the client (screen capture app)"""
        if self.client and not self.client.closed:
            try:
                await self.client.send(json.dumps(message))
            except (websockets.ConnectionClosed, Exception) as e:
                logger.warning(f"Error sending to client: {e}")
                self.client = None
                self.client_id = None


state = ServerState()


async def handle_viewer(websocket: websockets.WebSocketServerProtocol, path: str):
    """Handle web viewer connections"""
    viewer_id = f"viewer_{id(websocket)}"
    logger.info(f"Viewer connected: {viewer_id}")
    
    try:
        state.viewers.add(websocket)
        
        # Send initial info
        await websocket.send(json.dumps({
            "type": "connected",
            "viewer_id": viewer_id,
            "client_connected": state.client is not None
        }))
        
        async for message in websocket:
            try:
                data = json.loads(message)
                msg_type = data.get("type")
                
                if msg_type == "control":
                    # Forward control commands to client
                    await state.send_to_client({
                        "type": "control",
                        "command": data.get("command"),
                        "data": data.get("data")
                    })
                    
                elif msg_type == "ping":
                    await websocket.send(json.dumps({"type": "pong"}))
                    
            except json.JSONDecodeError:
                logger.warning("Invalid JSON from viewer")
            except Exception as e:
                logger.error(f"Error processing viewer message: {e}")
    
    except websockets.ConnectionClosed:
        logger.info(f"Viewer disconnected: {viewer_id}")
    finally:
        state.viewers.discard(websocket)


async def handle_client(websocket: websockets.WebSocketServerProtocol, path: str):
    """Handle Windows client (screen capture) connections"""
    client_id = f"client_{id(websocket)}"
    logger.info(f"Client connected: {client_id}")
    
    try:
        # Only allow one client at a time
        if state.client and not state.client.closed:
            await websocket.send(json.dumps({
                "type": "error",
                "message": "Another client is already connected"
            }))
            await websocket.close()
            return
        
        state.client = websocket
        state.client_id = client_id
        
        # Notify client it's connected
        await websocket.send(json.dumps({
            "type": "connected",
            "client_id": client_id
        }))
        
        # Notify viewers that client is connected
        await state.broadcast_to_viewers({
            "type": "client_connected"
        })
        
        async for message in websocket:
            try:
                data = json.loads(message)
                msg_type = data.get("type")
                
                if msg_type == "frame":
                    # Broadcast video frame to all viewers
                    await state.broadcast_to_viewers(data)
                    
                elif msg_type == "ping":
                    await websocket.send(json.dumps({"type": "pong"}))
                    
                elif msg_type == "screen_info":
                    # Forward screen dimensions to viewers
                    await state.broadcast_to_viewers(data)
                    
            except json.JSONDecodeError:
                logger.warning("Invalid JSON from client")
            except Exception as e:
                logger.error(f"Error processing client message: {e}")
    
    except websockets.ConnectionClosed:
        logger.info(f"Client disconnected: {client_id}")
    finally:
        state.client = None
        state.client_id = None
        await state.broadcast_to_viewers({
            "type": "client_disconnected"
        })


async def start_websocket_server():
    """Start WebSocket server for real-time communication"""
    logger.info(f"Starting WebSocket server on ws://{Config.HOST}:{Config.PORT}")
    
    async with websockets.serve(
        handle_viewer,
        Config.HOST,
        Config.PORT,
        ping_interval=20,
        ping_timeout=60
    ) as viewer_server, websockets.serve(
        handle_client,
        Config.HOST,
        Config.PORT + 1,  # Client connects on port+1
        ping_interval=20,
        ping_timeout=60
    ) as client_server:
        
        # Create a simple HTTP server for the web interface
        http_server = await asyncio.start_server(
            handle_http,
            Config.HOST,
            Config.WEB_PORT
        )
        
        logger.info(f"HTTP server running on http://{Config.HOST}:{Config.WEB_PORT}")
        logger.info(f"Client server running on ws://{Config.HOST}:{Config.PORT + 1}")
        
        async with http_server:
            await asyncio.Future()  # Run forever


async def handle_http(reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
    """Simple HTTP server to serve the web interface"""
    try:
        request = await reader.read(1024)
        request_str = request.decode('utf-8')
        
        # Parse request line
        lines = request_str.split('\r\n')
        if not lines:
            return
        
        request_line = lines[0].split()
        if len(request_line) < 2:
            method, path = request_line[0], '/'
        else:
            method, path = request_line[0], request_line[1]
        
        # Serve static files
        static_dir = os.path.join(os.path.dirname(__file__), 'static')
        
        if path == '/':
            path = '/index.html'
        
        file_path = os.path.join(static_dir, path.lstrip('/'))
        
        if os.path.exists(file_path) and os.path.isfile(file_path):
            with open(file_path, 'rb') as f:
                content = f.read()
            
            # Determine content type
            if path.endswith('.html'):
                content_type = 'text/html'
            elif path.endswith('.css'):
                content_type = 'text/css'
            elif path.endswith('.js'):
                content_type = 'application/javascript'
            elif path.endswith('.png'):
                content_type = 'image/png'
            elif path.endswith('.jpg') or path.endswith('.jpeg'):
                content_type = 'image/jpeg'
            else:
                content_type = 'application/octet-stream'
            
            response = (
                f"HTTP/1.1 200 OK\r\n"
                f"Content-Type: {content_type}\r\n"
                f"Content-Length: {len(content)}\r\n"
                f"Access-Control-Allow-Origin: *\r\n"
                f"\r\n"
            ).encode('utf-8') + content
            
            writer.write(response)
        else:
            # 404 Not Found
            response = (
                "HTTP/1.1 404 Not Found\r\n"
                "Content-Type: text/plain\r\n"
                "\r\n"
                "404 Not Found"
            ).encode('utf-8')
            writer.write(response)
    
    except Exception as e:
        logger.error(f"HTTP error: {e}")
    finally:
        await writer.drain()
        writer.close()
        await writer.wait_closed()


async def main():
    """Main server entry point"""
    logger.info("=" * 60)
    logger.info("Win-Merror Server")
    logger.info("Screen Mirroring with Web Control")
    logger.info("=" * 60)
    
    try:
        await start_websocket_server()
    except KeyboardInterrupt:
        logger.info("Shutting down...")
    except Exception as e:
        logger.error(f"Server error: {e}")


if __name__ == "__main__":
    asyncio.run(main())
