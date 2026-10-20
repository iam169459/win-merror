"""
Win-Merror Client
Windows screen capture and control client
"""

import asyncio
import json
import logging
import sys
import time
import base64
import io
from typing import Optional

import websockets
import numpy as np
import cv2
from PIL import ImageGrab, Image
import win32api
import win32con

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class Config:
    """Client configuration"""
    SERVER_HOST = "localhost"
    SERVER_PORT = 8081  # WebSocket port for client connection
    FRAME_INTERVAL = 0.05  # ~20 FPS (1/20 = 0.05)
    JPEG_QUALITY = 85
    SCREENSHOT_SCALE = 1.0  # Scale factor (0.5 = 50% size)
    SHOW_CURSOR = True
    MOUSE_MOVE_THRESHOLD = 5  # Minimum mouse movement to send


class ScreenCapture:
    """Handles screen capture and encoding"""
    
    def __init__(self):
        self.last_frame: Optional[np.ndarray] = None
        self.frame_count = 0
        self.last_capture_time = 0
        
    def capture_screen(self) -> tuple[bytes, int, int]:
        """Capture screen and return as JPEG bytes with dimensions"""
        try:
            # Capture screen
            screenshot = ImageGrab.grab()
            
            # Convert to numpy array (BGR format for OpenCV)
            img_np = np.array(screenshot)
            img_np = cv2.cvtColor(img_np, cv2.COLOR_RGB2BGR)
            
            # Scale if needed
            if Config.SCREENSHOT_SCALE != 1.0:
                height, width = img_np.shape[:2]
                new_width = int(width * Config.SCREENSHOT_SCALE)
                new_height = int(height * Config.SCREENSHOT_SCALE)
                img_np = cv2.resize(img_np, (new_width, new_height), 
                                   interpolation=cv2.INTER_AREA)
            
            # Encode as JPEG
            encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), Config.JPEG_QUALITY]
            _, buffer = cv2.imencode('.jpg', img_np, encode_param)
            
            # Get dimensions
            height, width = img_np.shape[:2]
            
            return buffer.tobytes(), width, height
            
        except Exception as e:
            logger.error(f"Error capturing screen: {e}")
            # Return empty frame
            return b'', 0, 0
    
    def capture_screen_region(self, x: int, y: int, width: int, height: int) -> tuple[bytes, int, int]:
        """Capture a specific region of the screen"""
        try:
            screenshot = ImageGrab.grab(bbox=(x, y, x + width, y + height))
            img_np = np.array(screenshot)
            img_np = cv2.cvtColor(img_np, cv2.COLOR_RGB2BGR)
            
            encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), Config.JPEG_QUALITY]
            _, buffer = cv2.imencode('.jpg', img_np, encode_param)
            
            return buffer.tobytes(), width, height
            
        except Exception as e:
            logger.error(f"Error capturing screen region: {e}")
            return b'', 0, 0


class MouseController:
    """Handles mouse control on the Windows desktop"""
    
    def __init__(self):
        self.screen_width = win32api.GetSystemMetrics(win32con.SM_CXSCREEN)
        self.screen_height = win32api.GetSystemMetrics(win32con.SM_CYSCREEN)
        self.last_x = 0
        self.last_y = 0
        
    def move_to(self, x: int, y: int):
        """Move mouse to absolute position"""
        try:
            # Clamp to screen bounds
            x = max(0, min(x, self.screen_width - 1))
            y = max(0, min(y, self.screen_height - 1))
            
            win32api.SetCursorPos((x, y))
            self.last_x = x
            self.last_y = y
        except Exception as e:
            logger.error(f"Error moving mouse: {e}")
    
    def move_relative(self, dx: int, dy: int):
        """Move mouse relative to current position"""
        try:
            win32api.mouse_event(win32con.MOUSEEVENTF_MOVE, dx, dy, 0, 0)
            self.last_x += dx
            self.last_y += dy
        except Exception as e:
            logger.error(f"Error moving mouse relative: {e}")
    
    def click(self, button: int = 0):
        """Perform mouse click (0=left, 1=middle, 2=right)"""
        try:
            if button == 0:  # Left
                win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
                time.sleep(0.05)
                win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
            elif button == 1:  # Middle
                win32api.mouse_event(win32con.MOUSEEVENTF_MIDDLEDOWN, 0, 0, 0, 0)
                time.sleep(0.05)
                win32api.mouse_event(win32con.MOUSEEVENTF_MIDDLEUP, 0, 0, 0, 0)
            elif button == 2:  # Right
                win32api.mouse_event(win32con.MOUSEEVENTF_RIGHTDOWN, 0, 0, 0, 0)
                time.sleep(0.05)
                win32api.mouse_event(win32con.MOUSEEVENTF_RIGHTUP, 0, 0, 0, 0)
        except Exception as e:
            logger.error(f"Error clicking mouse: {e}")
    
    def double_click(self, button: int = 0):
        """Perform double click"""
        try:
            self.click(button)
            time.sleep(0.1)
            self.click(button)
        except Exception as e:
            logger.error(f"Error double clicking: {e}")
    
    def mouse_down(self, button: int = 0):
        """Mouse button down"""
        try:
            if button == 0:
                win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
            elif button == 1:
                win32api.mouse_event(win32con.MOUSEEVENTF_MIDDLEDOWN, 0, 0, 0, 0)
            elif button == 2:
                win32api.mouse_event(win32con.MOUSEEVENTF_RIGHTDOWN, 0, 0, 0, 0)
        except Exception as e:
            logger.error(f"Error mouse down: {e}")
    
    def mouse_up(self, button: int = 0):
        """Mouse button up"""
        try:
            if button == 0:
                win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
            elif button == 1:
                win32api.mouse_event(win32con.MOUSEEVENTF_MIDDLEUP, 0, 0, 0, 0)
            elif button == 2:
                win32api.mouse_event(win32con.MOUSEEVENTF_RIGHTUP, 0, 0, 0, 0)
        except Exception as e:
            logger.error(f"Error mouse up: {e}")
    
    def scroll(self, delta: int):
        """Scroll mouse wheel (positive = up, negative = down)"""
        try:
            win32api.mouse_event(win32con.MOUSEEVENTF_WHEEL, 0, 0, delta, 0)
        except Exception as e:
            logger.error(f"Error scrolling: {e}")


class KeyboardController:
    """Handles keyboard input on the Windows desktop"""
    
    def __init__(self):
        self.vk_map = self._create_vk_map()
        
    def _create_vk_map(self) -> dict:
        """Create mapping from key names to virtual key codes"""
        return {
            'escape': win32con.VK_ESCAPE,
            'tab': win32con.VK_TAB,
            'enter': win32con.VK_RETURN,
            'space': win32con.VK_SPACE,
            'backspace': win32con.VK_BACK,
            'delete': win32con.VK_DELETE,
            'arrow_up': win32con.VK_UP,
            'arrow_down': win32con.VK_DOWN,
            'arrow_left': win32con.VK_LEFT,
            'arrow_right': win32con.VK_RIGHT,
            'ctrl': win32con.VK_CONTROL,
            'alt': win32con.VK_MENU,
            'shift': win32con.VK_SHIFT,
            'win': win32con.VK_LWIN,
            'f1': win32con.VK_F1,
            'f2': win32con.VK_F2,
            'f3': win32con.VK_F3,
            'f4': win32con.VK_F4,
            'f5': win32con.VK_F5,
            'f6': win32con.VK_F6,
            'f7': win32con.VK_F7,
            'f8': win32con.VK_F8,
            'f9': win32con.VK_F9,
            'f10': win32con.VK_F10,
            'f11': win32con.VK_F11,
            'f12': win32con.VK_F12,
        }
    
    def press_key(self, key: str, ctrl: bool = False, alt: bool = False, 
                  shift: bool = False, meta: bool = False):
        """Press a single key"""
        try:
            # Handle modifiers
            if ctrl:
                win32api.keybd_event(win32con.VK_CONTROL, 0, 0, 0)
            if alt:
                win32api.keybd_event(win32con.VK_MENU, 0, 0, 0)
            if shift:
                win32api.keybd_event(win32con.VK_SHIFT, 0, 0, 0)
            if meta:
                win32api.keybd_event(win32con.VK_LWIN, 0, 0, 0)
            
            # Press the key
            if key in self.vk_map:
                vk = self.vk_map[key]
                win32api.keybd_event(vk, 0, 0, 0)
                time.sleep(0.05)
                win32api.keybd_event(vk, 0, win32con.KEYEVENTF_KEYUP, 0)
            else:
                # Try to send as character
                self.type_text(key)
            
            # Release modifiers
            if meta:
                win32api.keybd_event(win32con.VK_LWIN, 0, win32con.KEYEVENTF_KEYUP, 0)
            if shift:
                win32api.keybd_event(win32con.VK_SHIFT, 0, win32con.KEYEVENTF_KEYUP, 0)
            if alt:
                win32api.keybd_event(win32con.VK_MENU, 0, win32con.KEYEVENTF_KEYUP, 0)
            if ctrl:
                win32api.keybd_event(win32con.VK_CONTROL, 0, win32con.KEYEVENTF_KEYUP, 0)
                
        except Exception as e:
            logger.error(f"Error pressing key: {e}")
    
    def type_text(self, text: str):
        """Type a string of text"""
        try:
            for char in text:
                # Handle special characters
                if char == '\n':
                    win32api.keybd_event(win32con.VK_RETURN, 0, 0, 0)
                    time.sleep(0.05)
                    win32api.keybd_event(win32con.VK_RETURN, 0, win32con.KEYEVENTF_KEYUP, 0)
                elif char == '\t':
                    win32api.keybd_event(win32con.VK_TAB, 0, 0, 0)
                    time.sleep(0.05)
                    win32api.keybd_event(win32con.VK_TAB, 0, win32con.KEYEVENTF_KEYUP, 0)
                else:
                    # Send as Unicode character
                    win32api.keybd_event(ord(char), 0, 0, 0)
                    time.sleep(0.05)
                    win32api.keybd_event(ord(char), 0, win32con.KEYEVENTF_KEYUP, 0)
                    time.sleep(0.02)
        except Exception as e:
            logger.error(f"Error typing text: {e}")
    
    def send_shortcut(self, shortcut: str):
        """Send a keyboard shortcut"""
        try:
            if shortcut == 'ctrl_alt_del':
                # Ctrl+Alt+Del requires special handling
                win32api.keybd_event(win32con.VK_CONTROL, 0, 0, 0)
                win32api.keybd_event(win32con.VK_MENU, 0, 0, 0)
                win32api.keybd_event(win32con.VK_DELETE, 0, 0, 0)
                time.sleep(0.1)
                win32api.keybd_event(win32con.VK_DELETE, 0, win32con.KEYEVENTF_KEYUP, 0)
                win32api.keybd_event(win32con.VK_MENU, 0, win32con.KEYEVENTF_KEYUP, 0)
                win32api.keybd_event(win32con.VK_CONTROL, 0, win32con.KEYEVENTF_KEYUP, 0)
                
            elif shortcut == 'alt_tab':
                win32api.keybd_event(win32con.VK_MENU, 0, 0, 0)
                time.sleep(0.1)
                win32api.keybd_event(win32con.VK_TAB, 0, 0, 0)
                time.sleep(0.1)
                win32api.keybd_event(win32con.VK_TAB, 0, win32con.KEYEVENTF_KEYUP, 0)
                win32api.keybd_event(win32con.VK_MENU, 0, win32con.KEYEVENTF_KEYUP, 0)
                
            elif shortcut == 'win':
                win32api.keybd_event(win32con.VK_LWIN, 0, 0, 0)
                time.sleep(0.1)
                win32api.keybd_event(win32con.VK_LWIN, 0, win32con.KEYEVENTF_KEYUP, 0)
                
        except Exception as e:
            logger.error(f"Error sending shortcut: {e}")


class ClientApp:
    """Main client application"""
    
    def __init__(self):
        self.screen_capture = ScreenCapture()
        self.mouse_controller = MouseController()
        self.keyboard_controller = KeyboardController()
        self.websocket: Optional[websockets.WebSocketClientProtocol] = None
        self.running = False
        self.client_id: Optional[str] = None
        
    async def connect(self, host: str = None, port: int = None):
        """Connect to the WebSocket server"""
        host = host or Config.SERVER_HOST
        port = port or Config.SERVER_PORT
        
        uri = f"ws://{host}:{port}"
        logger.info(f"Connecting to server at {uri}")
        
        try:
            self.websocket = await websockets.connect(
                uri,
                ping_interval=20,
                ping_timeout=60
            )
            
            # Get connection info
            message = await self.websocket.recv()
            data = json.loads(message)
            
            if data.get('type') == 'connected':
                self.client_id = data.get('client_id')
                logger.info(f"Connected to server with client ID: {self.client_id}")
                
                # Send screen info
                width = win32api.GetSystemMetrics(win32con.SM_CXSCREEN)
                height = win32api.GetSystemMetrics(win32con.SM_CYSCREEN)
                await self.send_message({
                    'type': 'screen_info',
                    'width': width,
                    'height': height
                })
                
                return True
            else:
                logger.error(f"Connection failed: {data.get('message', 'Unknown error')}")
                return False
                
        except Exception as e:
            logger.error(f"Connection error: {e}")
            return False
    
    async def disconnect(self):
        """Disconnect from the server"""
        if self.websocket:
            await self.websocket.close()
            self.websocket = None
            self.client_id = None
            logger.info("Disconnected from server")
    
    async def send_message(self, message: dict):
        """Send a message to the server"""
        if self.websocket and not self.websocket.closed:
            try:
                await self.websocket.send(json.dumps(message))
            except Exception as e:
                logger.error(f"Error sending message: {e}")
    
    async def send_frame(self):
        """Capture and send a video frame"""
        try:
            frame_data, width, height = self.screen_capture.capture_screen()
            
            if frame_data and width > 0 and height > 0:
                # Encode as base64
                frame_b64 = base64.b64encode(frame_data).decode('utf-8')
                
                await self.send_message({
                    'type': 'frame',
                    'data': frame_b64,
                    'width': width,
                    'height': height,
                    'timestamp': time.time()
                })
        except Exception as e:
            logger.error(f"Error sending frame: {e}")
    
    async def handle_control_message(self, data: dict):
        """Handle control messages from the server"""
        command = data.get('command')
        
        if command == 'mouse':
            action = data.get('action')
            x = data.get('x', 0)
            y = data.get('y', 0)
            button = data.get('button', 0)
            
            if action == 'move':
                self.mouse_controller.move_to(x, y)
            elif action == 'down':
                self.mouse_controller.mouse_down(button)
            elif action == 'up':
                self.mouse_controller.mouse_up(button)
            elif action == 'click':
                self.mouse_controller.move_to(x, y)
                self.mouse_controller.click(button)
            elif action == 'double_click':
                self.mouse_controller.move_to(x, y)
                self.mouse_controller.double_click(button)
                
        elif command == 'scroll':
            delta = data.get('delta', 0)
            self.mouse_controller.scroll(delta)
            
        elif command == 'keyboard':
            action = data.get('action')
            
            if action == 'type':
                text = data.get('text', '')
                self.keyboard_controller.type_text(text)
                
            elif action == 'key_press':
                key = data.get('key', '')
                modifiers = data.get('modifiers', {})
                self.keyboard_controller.press_key(
                    key,
                    ctrl=modifiers.get('ctrl', False),
                    alt=modifiers.get('alt', False),
                    shift=modifiers.get('shift', False),
                    meta=modifiers.get('meta', False)
                )
                
            elif action == 'shortcut':
                shortcut = data.get('shortcut', '')
                self.keyboard_controller.send_shortcut(shortcut)
    
    async def handle_settings(self, data: dict):
        """Handle settings updates from server"""
        if 'quality' in data:
            Config.JPEG_QUALITY = int(data['quality'])
            logger.info(f"Quality updated to: {Config.JPEG_QUALITY}")
            
        if 'show_cursor' in data:
            Config.SHOW_CURSOR = bool(data['show_cursor'])
            logger.info(f"Show cursor: {Config.SHOW_CURSOR}")
    
    async def process_messages(self):
        """Process incoming WebSocket messages"""
        try:
            async for message in self.websocket:
                try:
                    data = json.loads(message)
                    msg_type = data.get('type')
                    
                    if msg_type == 'control':
                        await self.handle_control_message(data)
                        
                    elif msg_type == 'settings':
                        await self.handle_settings(data)
                        
                    elif msg_type == 'ping':
                        await self.send_message({'type': 'pong'})
                        
                    elif msg_type == 'error':
                        logger.error(f"Server error: {data.get('message', 'Unknown')}")
                        
                except json.JSONDecodeError:
                    logger.warning("Received invalid JSON message")
                except Exception as e:
                    logger.error(f"Error processing message: {e}")
                    
        except websockets.ConnectionClosed:
            logger.info("Connection closed by server")
            self.websocket = None
        except Exception as e:
            logger.error(f"Error in message processing: {e}")
            self.websocket = None
    
    async def capture_loop(self):
        """Main loop for capturing and sending frames"""
        while self.running and self.websocket and not self.websocket.closed:
            start_time = time.time()
            
            await self.send_frame()
            
            # Calculate sleep time to maintain frame rate
            elapsed = time.time() - start_time
            sleep_time = max(0, Config.FRAME_INTERVAL - elapsed)
            await asyncio.sleep(sleep_time)
    
    async def run(self, host: str = None, port: int = None):
        """Run the client application"""
        self.running = True
        
        # Connect to server
        if not await self.connect(host, port):
            logger.error("Failed to connect to server")
            return
        
        logger.info("Starting screen capture...")
        
        # Start message processing in background
        message_task = asyncio.create_task(self.process_messages())
        
        # Start capture loop
        try:
            await self.capture_loop()
        except KeyboardInterrupt:
            logger.info("Stopping...")
        except Exception as e:
            logger.error(f"Error in capture loop: {e}")
        finally:
            self.running = False
            message_task.cancel()
            
            try:
                await message_task
            except asyncio.CancelledError:
                pass
            
            await self.disconnect()
    
    def start(self, host: str = None, port: int = None):
        """Start the client (synchronous entry point)"""
        asyncio.run(self.run(host, port))


def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Win-Merror Client - Windows Screen Mirroring')
    parser.add_argument('--host', type=str, default=Config.SERVER_HOST,
                        help='Server host (default: localhost)')
    parser.add_argument('--port', type=int, default=Config.SERVER_PORT,
                        help='Server port (default: 8081)')
    parser.add_argument('--fps', type=int, default=20,
                        help='Target frames per second (default: 20)')
    parser.add_argument('--quality', type=int, default=85,
                        help='JPEG quality (0-100, default: 85)')
    parser.add_argument('--scale', type=float, default=1.0,
                        help='Screen capture scale factor (default: 1.0)')
    
    args = parser.parse_args()
    
    # Update config from arguments
    Config.SERVER_HOST = args.host
    Config.SERVER_PORT = args.port
    Config.FRAME_INTERVAL = 1.0 / args.fps
    Config.JPEG_QUALITY = args.quality
    Config.SCREENSHOT_SCALE = args.scale
    
    # Print configuration
    logger.info("=" * 60)
    logger.info("Win-Merror Client")
    logger.info("Windows Screen Mirroring & Control")
    logger.info("=" * 60)
    logger.info(f"Server: {Config.SERVER_HOST}:{Config.SERVER_PORT}")
    logger.info(f"Target FPS: {args.fps}")
    logger.info(f"JPEG Quality: {Config.JPEG_QUALITY}")
    logger.info(f"Scale: {Config.SCREENSHOT_SCALE}")
    logger.info("=" * 60)
    logger.info("Press Ctrl+C to stop")
    logger.info("=" * 60)
    
    # Start the client
    try:
        app = ClientApp()
        app.start()
    except KeyboardInterrupt:
        logger.info("Shutting down...")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
