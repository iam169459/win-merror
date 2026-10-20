"""
Win-Merror Server
WebSocket server for screen streaming and remote control
with full access control support
"""

import asyncio
import json
import logging
import os
import base64
import hashlib
import warnings
from typing import Dict, Set, Optional, List, Any, Union
from datetime import datetime

import websockets

# Suppress deprecation warnings for websockets
warnings.filterwarnings("ignore", category=DeprecationWarning)

# Import access control
from auth import get_access_control, init_access_control, AccessControl

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
    MAX_VIEWERS = 20
    FRAME_QUALITY = 85
    MAX_FRAME_SIZE = 2 * 1024 * 1024
    SECRET_KEY = "win-merror-secret-change-this"


class ServerState:
    """Track connected clients and viewers"""
    def __init__(self):
        self.viewers: Set = set()
        self.client = None
        self.client_id: str = None
        self.client_session: Optional[Any] = None
        self.viewer_sessions: Dict[str, Any] = {}

    async def broadcast_to_viewers(self, message: dict, exclude: Set[str] = None):
        """Send message to all connected viewers with proper permissions"""
        if not self.viewers:
            return
        
        access_control = get_access_control()
        message_str = json.dumps(message)
        disconnected = set()
        
        for viewer in self.viewers:
            try:
                # Check if viewer is authenticated and has view permission
                viewer_id = id(viewer)
                session = self.viewer_sessions.get(str(viewer_id))
                
                # If session tracking is enabled, check permissions
                if access_control.config.get("sessions", {}).get("enabled", True):
                    if session and access_control.has_permission(session, "view"):
                        await viewer.send(message_str)
                    elif not session and not access_control.config.get("authentication", {}).get("enabled", True):
                        # Authentication disabled, allow all
                        await viewer.send(message_str)
                else:
                    # Session tracking disabled, allow all
                    await viewer.send(message_str)
                    
            except (websockets.ConnectionClosed, Exception) as e:
                logger.warning(f"Error sending to viewer: {e}")
                disconnected.add(viewer)
        
        # Clean up disconnected viewers
        self.viewers -= disconnected
        for viewer in disconnected:
            viewer_id = str(id(viewer))
            if viewer_id in self.viewer_sessions:
                del self.viewer_sessions[viewer_id]

    async def send_to_client(self, message: dict):
        """Send message to the client (screen capture app)"""
        if self.client and not self.client.closed:
            try:
                # Check if client is authenticated
                if self.client_session:
                    access_control = get_access_control()
                    if access_control.has_permission(self.client_session, "control"):
                        await self.client.send(json.dumps(message))
                    else:
                        logger.warning("Client does not have control permission")
                else:
                    # No session tracking, allow all
                    await self.client.send(json.dumps(message))
            except (websockets.ConnectionClosed, Exception) as e:
                logger.warning(f"Error sending to client: {e}")
                self.client = None
                self.client_id = None
                self.client_session = None


state = ServerState()
access_control: Optional[AccessControl] = None


async def handle_viewer(websocket, path: str):
    """Handle web viewer connections"""
    viewer_id = f"viewer_{id(websocket)}"
    ip_address = get_ip_address(websocket)
    
    logger.info(f"Viewer connection attempt from {ip_address}")
    
    # Check IP filtering
    ac = get_access_control()
    if not ac.is_ip_allowed(ip_address):
        logger.warning(f"Viewer connection blocked from {ip_address}")
        await websocket.close(code=1008, reason="IP not allowed")
        return
    
    # Check rate limiting
    if not ac.check_rate_limit(ip_address):
        logger.warning(f"Viewer connection rate limited from {ip_address}")
        await websocket.close(code=1008, reason="Rate limit exceeded")
        return
    
    # Register connection
    ac.register_connection(viewer_id, ip_address, "viewer")
    
    try:
        state.viewers.add(websocket)
        
        # Send authentication challenge if required
        auth_config = ac.config.get("authentication", {})
        if auth_config.get("enabled", True):
            # Send auth challenge
            await websocket.send(json.dumps({
                "type": "auth_required",
                "message": "Authentication required"
            }))
        else:
            # No auth required
            await websocket.send(json.dumps({
                "type": "connected",
                "viewer_id": viewer_id,
                "client_connected": state.client is not None
            }))
        
        async for message in websocket:
            try:
                data = json.loads(message)
                msg_type = data.get("type")
                
                if msg_type == "authenticate":
                    # Handle authentication
                    username = data.get("username")
                    password = data.get("password")
                    token = data.get("token")
                    
                    if token:
                        # Token-based authentication
                        session = ac.verify_token(token)
                        if session:
                            state.viewer_sessions[str(id(websocket))] = session
                            await websocket.send(json.dumps({
                                "type": "auth_success",
                                "viewer_id": viewer_id,
                                "client_connected": state.client is not None,
                                "permissions": session.permissions
                            }))
                            logger.info(f"Viewer authenticated via token from {ip_address}")
                        else:
                            await websocket.send(json.dumps({
                                "type": "auth_failed",
                                "message": "Invalid token"
                            }))
                            logger.warning(f"Token authentication failed from {ip_address}")
                    elif username and password:
                        # Username/password authentication
                        user = ac.authenticate(username, password, ip_address)
                        if user:
                            session = ac.create_session(user, ip_address)
                            if session:
                                state.viewer_sessions[str(id(websocket))] = session
                                token = ac.generate_token(session)
                                await websocket.send(json.dumps({
                                    "type": "auth_success",
                                    "viewer_id": viewer_id,
                                    "client_connected": state.client is not None,
                                    "permissions": session.permissions,
                                    "token": token
                                }))
                                logger.info(f"Viewer authenticated as '{username}' from {ip_address}")
                            else:
                                await websocket.send(json.dumps({
                                    "type": "auth_success",
                                    "viewer_id": viewer_id,
                                    "client_connected": state.client is not None,
                                    "permissions": user.permissions
                                }))
                        else:
                            await websocket.send(json.dumps({
                                "type": "auth_failed",
                                "message": "Invalid username or password"
                            }))
                            logger.warning(f"Authentication failed from {ip_address}")
                    else:
                        await websocket.send(json.dumps({
                            "type": "auth_failed",
                            "message": "Username and password required"
                        }))
                        
                elif msg_type == "control":
                    # Forward control commands to client (with permission check)
                    session = state.viewer_sessions.get(str(id(websocket)))
                    
                    if session:
                        if ac.has_permission(session, "control"):
                            await state.send_to_client({
                                "type": "control",
                                "command": data.get("command"),
                                "data": data.get("data")
                            })
                        else:
                            await websocket.send(json.dumps({
                                "type": "error",
                                "message": "Permission denied: control not allowed"
                            }))
                    elif not auth_config.get("enabled", True):
                        # No auth required, allow control
                        await state.send_to_client({
                            "type": "control",
                            "command": data.get("command"),
                            "data": data.get("data")
                        })
                    else:
                        await websocket.send(json.dumps({
                            "type": "error",
                            "message": "Authentication required for control"
                        }))
                        
                elif msg_type == "ping":
                    await websocket.send(json.dumps({"type": "pong"}))
                    
                elif msg_type == "logout":
                    # Handle logout
                    viewer_id_str = str(id(websocket))
                    if viewer_id_str in state.viewer_sessions:
                        ac.invalidate_session(state.viewer_sessions[viewer_id_str].session_id)
                        del state.viewer_sessions[viewer_id_str]
                    await websocket.close()
                    
            except json.JSONDecodeError:
                logger.warning("Invalid JSON from viewer")
            except Exception as e:
                logger.error(f"Error processing viewer message: {e}")
    
    except websockets.ConnectionClosed:
        logger.info(f"Viewer disconnected: {viewer_id}")
    except Exception as e:
        logger.error(f"Viewer connection error: {e}")
    finally:
        state.viewers.discard(websocket)
        viewer_id_str = str(id(websocket))
        if viewer_id_str in state.viewer_sessions:
            del state.viewer_sessions[viewer_id_str]
        ac.unregister_connection(viewer_id)


async def handle_client(websocket, path: str):
    """Handle Windows client (screen capture) connections"""
    client_id = f"client_{id(websocket)}"
    ip_address = get_ip_address(websocket)
    
    logger.info(f"Client connection attempt from {ip_address}")
    
    # Check IP filtering
    ac = get_access_control()
    if not ac.is_ip_allowed(ip_address):
        logger.warning(f"Client connection blocked from {ip_address}")
        await websocket.close(code=1008, reason="IP not allowed")
        return
    
    # Check rate limiting
    if not ac.check_rate_limit(ip_address):
        logger.warning(f"Client connection rate limited from {ip_address}")
        await websocket.close(code=1008, reason="Rate limit exceeded")
        return
    
    # Register connection
    ac.register_connection(client_id, ip_address, "client")
    
    try:
        # Only allow one client at a time
        if state.client and not state.client.closed:
            await websocket.send(json.dumps({
                "type": "error",
                "message": "Another client is already connected"
            }))
            await websocket.close()
            return
        
        # Check authentication
        auth_config = ac.config.get("authentication", {})
        client_session = None
        
        if auth_config.get("enabled", True):
            # Wait for authentication
            auth_message = await asyncio.wait_for(websocket.recv(), timeout=10.0)
            try:
                auth_data = json.loads(auth_message)
                if auth_data.get("type") == "authenticate":
                    username = auth_data.get("username")
                    password = auth_data.get("password")
                    token = auth_data.get("token")
                    
                    if token:
                        client_session = ac.verify_token(token)
                    elif username and password:
                        user = ac.authenticate(username, password, ip_address)
                        if user:
                            client_session = ac.create_session(user, ip_address)
                    
                    if not client_session:
                        await websocket.send(json.dumps({
                            "type": "auth_failed",
                            "message": "Authentication required"
                        }))
                        await websocket.close(code=1008, reason="Authentication failed")
                        return
                    
                    # Check if client has permission to connect
                    if not ac.has_permission(client_session, "control"):
                        await websocket.send(json.dumps({
                            "type": "auth_failed",
                            "message": "Permission denied"
                        }))
                        await websocket.close(code=1008, reason="Permission denied")
                        return
                else:
                    # Not an auth message, check if it's a token in the path
                    await websocket.send(json.dumps({
                        "type": "auth_required",
                        "message": "Authentication required"
                    }))
                    await websocket.close(code=1008, reason="Authentication required")
                    return
            except json.JSONDecodeError:
                await websocket.send(json.dumps({
                    "type": "auth_required",
                    "message": "Authentication required"
                }))
                await websocket.close(code=1008, reason="Authentication required")
                return
        
        state.client = websocket
        state.client_id = client_id
        state.client_session = client_session
        
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
                    # Broadcast video frame to all viewers with view permission
                    await state.broadcast_to_viewers(data)
                    
                elif msg_type == "ping":
                    await websocket.send(json.dumps({"type": "pong"}))
                    
                elif msg_type == "screen_info":
                    # Forward screen dimensions to viewers
                    await state.broadcast_to_viewers(data)
                    
                elif msg_type == "authenticate":
                    # Handle delayed authentication
                    username = data.get("username")
                    password = data.get("password")
                    token = data.get("token")
                    
                    if token:
                        client_session = ac.verify_token(token)
                    elif username and password:
                        user = ac.authenticate(username, password, ip_address)
                        if user:
                            client_session = ac.create_session(user, ip_address)
                    
                    if client_session:
                        state.client_session = client_session
                        await websocket.send(json.dumps({
                            "type": "auth_success"
                        }))
                    else:
                        await websocket.send(json.dumps({
                            "type": "auth_failed",
                            "message": "Authentication failed"
                        }))
                        await websocket.close(code=1008, reason="Authentication failed")
                        return
                        
            except json.JSONDecodeError:
                logger.warning("Invalid JSON from client")
            except Exception as e:
                logger.error(f"Error processing client message: {e}")
    
    except websockets.ConnectionClosed:
        logger.info(f"Client disconnected: {client_id}")
    except asyncio.TimeoutError:
        logger.warning(f"Client connection timeout: {client_id}")
    except Exception as e:
        logger.error(f"Client connection error: {e}")
    finally:
        state.client = None
        state.client_id = None
        state.client_session = None
        await state.broadcast_to_viewers({
            "type": "client_disconnected"
        })
        ac.unregister_connection(client_id)


def get_ip_address(websocket) -> str:
    """Extract IP address from WebSocket connection"""
    try:
        # Try to get from remote address
        if hasattr(websocket, 'remote_address'):
            addr = websocket.remote_address
            if addr:
                return addr[0] if isinstance(addr, tuple) else str(addr)
        
        # Try to get from transport
        if hasattr(websocket, '_transport'):
            transport = websocket._transport
            if hasattr(transport, 'get_extra_info'):
                peername = transport.get_extra_info('peername')
                if peername:
                    return peername[0] if isinstance(peername, tuple) else str(peername)
        
        return "unknown"
    except Exception:
        return "unknown"


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
        
        # Get IP address
        ip_address = "unknown"
        try:
            if hasattr(writer, '_transport'):
                transport = writer._transport
                if hasattr(transport, 'get_extra_info'):
                    peername = transport.get_extra_info('peername')
                    if peername:
                        ip_address = peername[0] if isinstance(peername, tuple) else str(peername)
        except Exception:
            pass
        
        # Check IP filtering
        ac = get_access_control()
        if not ac.is_ip_allowed(ip_address):
            response = (
                "HTTP/1.1 403 Forbidden\r\n"
                "Content-Type: text/plain\r\n"
                "\r\n"
                "Access Denied"
            ).encode('utf-8')
            writer.write(response)
            await writer.drain()
            writer.close()
            await writer.wait_closed()
            return
        
        # Check rate limiting
        if not ac.check_rate_limit(ip_address):
            response = (
                "HTTP/1.1 429 Too Many Requests\r\n"
                "Content-Type: text/plain\r\n"
                "\r\n"
                "Rate Limit Exceeded"
            ).encode('utf-8')
            writer.write(response)
            await writer.drain()
            writer.close()
            await writer.wait_closed()
            return
        
        # Serve static files
        static_dir = os.path.join(os.path.dirname(__file__), 'static')
        
        if path == '/':
            path = '/index.html'
        
        # Handle API endpoints
        if path.startswith('/api/'):
            await handle_api_request(path, reader, writer, ip_address)
            return
        
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
            elif path.endswith('.json'):
                content_type = 'application/json'
            else:
                content_type = 'application/octet-stream'
            
            response = (
                f"HTTP/1.1 200 OK\r\n"
                f"Content-Type: {content_type}\r\n"
                f"Content-Length: {len(content)}\r\n"
                f"Access-Control-Allow-Origin: *\r\n"
                f"Cache-Control: no-cache\r\n"
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


async def handle_api_request(path: str, reader: asyncio.StreamReader, 
                           writer: asyncio.StreamWriter, ip_address: str):
    """Handle API requests"""
    ac = get_access_control()
    
    try:
        if path == '/api/status':
            # Get server status
            status = {
                "server": "running",
                "timestamp": datetime.now().isoformat(),
                "client_connected": state.client is not None,
                "viewer_count": len(state.viewers),
                "authentication_enabled": ac.config.get("authentication", {}).get("enabled", True),
                "active_sessions": len(ac.sessions)
            }
            
            response = (
                f"HTTP/1.1 200 OK\r\n"
                f"Content-Type: application/json\r\n"
                f"Access-Control-Allow-Origin: *\r\n"
                f"\r\n"
                f"{json.dumps(status, indent=2)}"
            ).encode('utf-8')
            writer.write(response)
            
        elif path == '/api/users':
            # List users (admin only)
            # Check if request has valid auth
            auth_header = None
            try:
                # Read headers
                headers = {}
                for line in reader._buffer:
                    if b': ' in line:
                        key, value = line.split(b': ', 1)
                        headers[key.decode('utf-8')] = value.decode('utf-8').strip()
                
                auth_header = headers.get('Authorization', '')
            except Exception:
                pass
            
            if auth_header and auth_header.startswith('Bearer '):
                token = auth_header[7:]
                session = ac.verify_token(token)
                if session and ac.is_admin(session):
                    users = ac.list_users()
                    response = (
                        f"HTTP/1.1 200 OK\r\n"
                        f"Content-Type: application/json\r\n"
                        f"Access-Control-Allow-Origin: *\r\n"
                        f"\r\n"
                        f"{json.dumps(users, indent=2)}"
                    ).encode('utf-8')
                    writer.write(response)
                else:
                    response = (
                        "HTTP/1.1 403 Forbidden\r\n"
                        "Content-Type: application/json\r\n"
                        "\r\n"
                        "{}"
                    ).encode('utf-8')
                    writer.write(response)
            else:
                response = (
                    "HTTP/1.1 401 Unauthorized\r\n"
                    "Content-Type: application/json\r\n"
                    "\r\n"
                    "{}"
                ).encode('utf-8')
                writer.write(response)
        
        elif path == '/api/connections':
            # List active connections
            connections = ac.get_all_connections()
            # Remove sensitive info
            safe_connections = []
            for conn in connections:
                safe_connections.append({
                    "ip_address": conn.get("ip_address", "unknown"),
                    "type": conn.get("type", "unknown"),
                    "connected_at": conn.get("connected_at")
                })
            
            response = (
                f"HTTP/1.1 200 OK\r\n"
                f"Content-Type: application/json\r\n"
                f"Access-Control-Allow-Origin: *\r\n"
                f"\r\n"
                f"{json.dumps(safe_connections, indent=2)}"
            ).encode('utf-8')
            writer.write(response)
        
        else:
            response = (
                "HTTP/1.1 404 Not Found\r\n"
                "Content-Type: application/json\r\n"
                "\r\n"
                "{}"
            ).encode('utf-8')
            writer.write(response)
            
    except Exception as e:
        logger.error(f"API error: {e}")
        response = (
            "HTTP/1.1 500 Internal Server Error\r\n"
            "Content-Type: application/json\r\n"
            "\r\n"
            "{}"
        ).encode('utf-8')
        writer.write(response)


async def start_websocket_server():
    """Start WebSocket server for real-time communication"""
    logger.info(f"Starting WebSocket server on ws://{Config.HOST}:{Config.PORT}")
    
    # Create SSL context if configured
    ssl_context = None
    ac = get_access_control()
    ssl_config = ac.config.get("ssl", {})
    
    if ssl_config.get("enabled", False):
        import ssl
        try:
            certfile = ssl_config.get("certfile", "cert.pem")
            keyfile = ssl_config.get("keyfile", "key.pem")
            
            if os.path.exists(certfile) and os.path.exists(keyfile):
                ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
                ssl_context.load_cert_chain(certfile, keyfile)
                logger.info(f"SSL enabled with cert: {certfile}")
            else:
                logger.warning(f"SSL cert files not found: {certfile}, {keyfile}")
        except Exception as e:
            logger.error(f"SSL error: {e}")
    
    # Start servers
    server_kwargs = {
        'ping_interval': 20,
        'ping_timeout': 60
    }
    if ssl_context:
        server_kwargs['ssl'] = ssl_context
    
    viewer_server = await websockets.serve(
        handle_viewer,
        Config.HOST,
        Config.PORT,
        **server_kwargs
    )
    
    client_server = await websockets.serve(
        handle_client,
        Config.HOST,
        Config.PORT + 1,  # Client connects on port+1
        **server_kwargs
    )
        
    # Create a simple HTTP server for the web interface
    http_server = await asyncio.start_server(
        handle_http,
        Config.HOST,
        Config.WEB_PORT
    )
    
    logger.info(f"HTTP server running on http://{Config.HOST}:{Config.WEB_PORT}")
    logger.info(f"Client server running on ws://{Config.HOST}:{Config.PORT + 1}")
    
    # Periodic cleanup
    asyncio.create_task(cleanup_task())
    
    await asyncio.gather(
        viewer_server.wait_closed,
        client_server.wait_closed,
        http_server.wait_closed
    )


async def cleanup_task():
    """Periodic cleanup of expired sessions and rate limits"""
    ac = get_access_control()
    while True:
        await asyncio.sleep(300)  # Clean up every 5 minutes
        ac.cleanup_expired()


async def main():
    """Main server entry point"""
    global access_control
    
    logger.info("=" * 60)
    logger.info("Win-Merror Server")
    logger.info("Screen Mirroring with Web Control")
    logger.info("=" * 60)
    
    try:
        # Load configuration
        config_path = os.path.join(os.path.dirname(__file__), 'config.json')
        config = {}
        if os.path.exists(config_path):
            with open(config_path, 'r') as f:
                import json
                config = json.load(f)
            logger.info(f"Configuration loaded from {config_path}")
        
        # Initialize access control
        access_control = init_access_control(config.get("security", {}))
        
        # Update Config from loaded config
        server_config = config.get("server", {})
        Config.HOST = server_config.get("host", Config.HOST)
        Config.PORT = server_config.get("port", Config.PORT)
        Config.WEB_PORT = server_config.get("web_port", Config.WEB_PORT)
        
        # Set secret key
        security_config = config.get("security", {})
        Config.SECRET_KEY = security_config.get("secret_key", Config.SECRET_KEY)
        
        # Start server
        await start_websocket_server()
    except KeyboardInterrupt:
        logger.info("Shutting down...")
    except Exception as e:
        logger.error(f"Server error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
