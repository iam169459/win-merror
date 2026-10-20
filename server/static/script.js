/**
 * Win-Merror Web Client
 * Handles WebSocket connection, video streaming, and control input
 */

class ScreenControl {
    constructor() {
        // WebSocket connection
        this.ws = null;
        this.reconnectAttempts = 0;
        this.maxReconnectAttempts = 10;
        this.reconnectDelay = 1000;
        
        // State
        this.connected = false;
        this.clientConnected = false;
        this.screenWidth = 0;
        this.screenHeight = 0;
        this.quality = 80;
        this.showCursor = true;
        this.latency = 0;
        this.lastPingTime = 0;
        
        // Mouse tracking
        this.isMouseDown = false;
        this.mouseButton = 0; // 0=left, 1=middle, 2=right
        this.lastMouseX = 0;
        this.lastMouseY = 0;
        
        // Touch tracking
        this.touchActive = false;
        this.touchStartX = 0;
        this.touchStartY = 0;
        
        // Video display
        this.videoDisplay = document.getElementById('videoDisplay');
        this.videoOverlay = document.getElementById('videoOverlay');
        this.overlayMessage = document.getElementById('overlayMessage');
        
        // Status elements
        this.serverStatus = document.getElementById('serverStatus');
        this.clientStatus = document.getElementById('clientStatus');
        this.latencyValue = document.getElementById('latencyValue');
        this.websocketUrl = document.getElementById('websocketUrl');
        this.clientWsUrl = document.getElementById('clientWsUrl');
        
        // Control elements
        this.leftClickBtn = document.getElementById('leftClick');
        this.rightClickBtn = document.getElementById('rightClick');
        this.doubleClickBtn = document.getElementById('doubleClick');
        this.scrollUpBtn = document.getElementById('scrollUp');
        this.scrollDownBtn = document.getElementById('scrollDown');
        this.keyboardInput = document.getElementById('keyboardInput');
        this.sendTextBtn = document.getElementById('sendText');
        this.ctrlAltDelBtn = document.getElementById('ctrlAltDel');
        this.winKeyBtn = document.getElementById('winKey');
        this.altTabBtn = document.getElementById('altTab');
        this.showCursorCheckbox = document.getElementById('showCursor');
        this.fullscreenCheckbox = document.getElementById('fullscreen');
        this.qualitySlider = document.getElementById('qualitySlider');
        this.qualityValue = document.getElementById('qualityValue');
        
        // Touch controls
        this.touchControls = document.getElementById('touchControls');
        this.touchPad = document.getElementById('touchPad');
        this.touchIndicator = document.getElementById('touchIndicator');
        this.touchLeftClick = document.getElementById('touchLeftClick');
        this.touchRightClick = document.getElementById('touchRightClick');
        
        // Initialize
        this.init();
    }
    
    init() {
        this.setupEventListeners();
        this.updateStatus('Connecting...');
        this.connect();
        this.updateUrlDisplay();
        
        // Check if on mobile
        this.checkMobile();
    }
    
    checkMobile() {
        const isMobile = /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(
            navigator.userAgent
        );
        if (isMobile) {
            this.touchControls.classList.add('active');
        }
    }
    
    updateUrlDisplay() {
        const host = window.location.hostname;
        const port = window.location.port || (window.location.protocol === 'https:' ? 443 : 80);
        const wsPort = parseInt(port) + 1;
        
        this.websocketUrl.textContent = `${window.location.protocol === 'https:' ? 'wss' : 'ws'}://${host}:${port}`;
        this.clientWsUrl.textContent = `${host}:${wsPort + 1}`;
    }
    
    setupEventListeners() {
        // Mouse controls on video
        this.videoDisplay.addEventListener('mousedown', this.handleMouseDown.bind(this));
        this.videoDisplay.addEventListener('mouseup', this.handleMouseUp.bind(this));
        this.videoDisplay.addEventListener('mousemove', this.handleMouseMove.bind(this));
        this.videoDisplay.addEventListener('wheel', this.handleMouseWheel.bind(this));
        this.videoDisplay.addEventListener('contextmenu', (e) => e.preventDefault());
        this.videoDisplay.addEventListener('dblclick', this.handleDoubleClick.bind(this));
        
        // Control buttons
        this.leftClickBtn.addEventListener('click', () => this.sendMouseClick(0));
        this.rightClickBtn.addEventListener('click', () => this.sendMouseClick(2));
        this.doubleClickBtn.addEventListener('click', () => this.sendDoubleClick());
        this.scrollUpBtn.addEventListener('click', () => this.sendScroll(120));
        this.scrollDownBtn.addEventListener('click', () => this.sendScroll(-120));
        
        // Keyboard
        this.keyboardInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') {
                this.sendText();
            }
        });
        this.sendTextBtn.addEventListener('click', () => this.sendText());
        
        // Shortcuts
        this.ctrlAltDelBtn.addEventListener('click', () => this.sendShortcut('ctrl_alt_del'));
        this.winKeyBtn.addEventListener('click', () => this.sendShortcut('win'));
        this.altTabBtn.addEventListener('click', () => this.sendShortcut('alt_tab'));
        
        // Settings
        this.showCursorCheckbox.addEventListener('change', (e) => {
            this.showCursor = e.target.checked;
            this.sendSettings();
        });
        
        this.fullscreenCheckbox.addEventListener('change', (e) => {
            if (e.target.checked) {
                this.enterFullscreen();
            } else {
                this.exitFullscreen();
            }
        });
        
        this.qualitySlider.addEventListener('input', (e) => {
            this.quality = parseInt(e.target.value);
            this.qualityValue.textContent = `${this.quality}%`;
            this.sendSettings();
        });
        
        // Touch controls
        this.touchPad.addEventListener('touchstart', this.handleTouchStart.bind(this), { passive: false });
        this.touchPad.addEventListener('touchmove', this.handleTouchMove.bind(this), { passive: false });
        this.touchPad.addEventListener('touchend', this.handleTouchEnd.bind(this));
        this.touchLeftClick.addEventListener('click', () => this.sendMouseClick(0));
        this.touchRightClick.addEventListener('click', () => this.sendMouseClick(2));
        
        // Keyboard shortcuts on the page
        document.addEventListener('keydown', this.handleGlobalKeydown.bind(this));
        
        // Window events
        window.addEventListener('beforeunload', () => {
            this.disconnect();
        });
    }
    
    connect() {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const host = window.location.hostname;
        const port = window.location.port || (protocol === 'wss:' ? 443 : 80);
        
        // Try to connect to the WebSocket server
        // The server runs on the same host, port 8080 (or 8081 for HTTPS)
        const wsUrl = `${protocol}//${host}:${parseInt(port) === 443 || parseInt(port) === 80 ? (protocol === 'wss:' ? 8443 : 8080) : parseInt(port)}`;
        
        console.log(`Connecting to WebSocket: ${wsUrl}`);
        
        try {
            this.ws = new WebSocket(wsUrl);
            
            this.ws.onopen = () => {
                this.reconnectAttempts = 0;
                this.connected = true;
                this.updateStatus('Connected', 'connected');
                this.videoOverlay.classList.remove('visible');
                
                // Send initial settings
                this.sendSettings();
                
                // Start ping for latency measurement
                this.startPing();
            };
            
            this.ws.onmessage = (event) => {
                this.handleMessage(event.data);
            };
            
            this.ws.onclose = () => {
                this.connected = false;
                this.clientConnected = false;
                this.updateStatus('Disconnected', 'disconnected');
                this.videoOverlay.classList.add('visible');
                this.overlayMessage.textContent = 'Disconnected from server';
                
                // Attempt to reconnect
                this.scheduleReconnect();
            };
            
            this.ws.onerror = (error) => {
                console.error('WebSocket error:', error);
            };
        } catch (error) {
            console.error('Failed to create WebSocket:', error);
            this.scheduleReconnect();
        }
    }
    
    scheduleReconnect() {
        if (this.reconnectAttempts < this.maxReconnectAttempts) {
            this.reconnectAttempts++;
            const delay = this.reconnectDelay * this.reconnectAttempts;
            
            this.videoOverlay.classList.add('visible');
            this.overlayMessage.textContent = `Reconnecting in ${Math.round(delay / 1000)}s...`;
            
            setTimeout(() => {
                this.connect();
            }, delay);
        } else {
            this.videoOverlay.classList.add('visible');
            this.overlayMessage.textContent = 'Failed to connect. Please refresh the page.';
        }
    }
    
    disconnect() {
        if (this.ws) {
            this.ws.close();
            this.ws = null;
        }
        this.connected = false;
        this.clientConnected = false;
    }
    
    handleMessage(data) {
        try {
            const message = JSON.parse(data);
            const type = message.type;
            
            switch (type) {
                case 'connected':
                    this.clientConnected = true;
                    this.updateClientStatus('Connected', 'connected');
                    break;
                    
                case 'client_connected':
                    this.clientConnected = true;
                    this.updateClientStatus('Connected', 'connected');
                    this.videoOverlay.classList.remove('visible');
                    break;
                    
                case 'client_disconnected':
                    this.clientConnected = false;
                    this.updateClientStatus('Disconnected', 'disconnected');
                    this.videoOverlay.classList.add('visible');
                    this.overlayMessage.textContent = 'Client disconnected. Waiting for screen...';
                    break;
                    
                case 'frame':
                    this.handleVideoFrame(message);
                    break;
                    
                case 'screen_info':
                    this.screenWidth = message.width;
                    this.screenHeight = message.height;
                    this.adjustVideoDisplay();
                    break;
                    
                case 'pong':
                    this.handlePong();
                    break;
                    
                default:
                    console.log('Unknown message type:', type);
            }
        } catch (error) {
            console.error('Error parsing message:', error);
        }
    }
    
    handleVideoFrame(message) {
        if (!this.clientConnected) return;
        
        const frameData = message.data;
        const width = message.width || this.screenWidth;
        const height = message.height || this.screenHeight;
        
        // Update screen dimensions if received
        if (message.width && message.height) {
            this.screenWidth = message.width;
            this.screenHeight = message.height;
            this.adjustVideoDisplay();
        }
        
        // Display the frame
        this.videoDisplay.src = `data:image/jpeg;base64,${frameData}`;
        this.videoDisplay.alt = `Screen: ${width}x${height}`;
    }
    
    adjustVideoDisplay() {
        if (this.screenWidth && this.screenHeight) {
            this.videoDisplay.style.aspectRatio = `${this.screenWidth}/${this.screenHeight}`;
        }
    }
    
    startPing() {
        // Send ping every 5 seconds
        this.pingInterval = setInterval(() => {
            if (this.ws && this.ws.readyState === WebSocket.OPEN) {
                this.lastPingTime = Date.now();
                this.ws.send(JSON.stringify({ type: 'ping' }));
            }
        }, 5000);
    }
    
    handlePong() {
        if (this.lastPingTime > 0) {
            this.latency = Date.now() - this.lastPingTime;
            this.latencyValue.textContent = `${this.latency} ms`;
        }
    }
    
    updateStatus(text, statusClass = '') {
        this.serverStatus.textContent = text;
        this.serverStatus.className = `status-value ${statusClass}`;
    }
    
    updateClientStatus(text, statusClass = '') {
        this.clientStatus.textContent = text;
        this.clientStatus.className = `status-value ${statusClass}`;
    }
    
    // Mouse Event Handlers
    handleMouseDown(e) {
        if (!this.clientConnected) return;
        
        this.isMouseDown = true;
        
        // Determine which button was pressed
        if (e.button === 0) {
            this.mouseButton = 0; // Left
        } else if (e.button === 2) {
            this.mouseButton = 2; // Right
        } else {
            this.mouseButton = 1; // Middle
        }
        
        // Calculate position relative to video
        const rect = this.videoDisplay.getBoundingClientRect();
        const x = e.clientX - rect.left;
        const y = e.clientY - rect.top;
        
        // Scale to screen coordinates
        const scaleX = this.screenWidth / rect.width;
        const scaleY = this.screenHeight / rect.height;
        
        this.lastMouseX = Math.round(x * scaleX);
        this.lastMouseY = Math.round(y * scaleY);
        
        // Send mouse down event
        this.sendMouseEvent('down', this.lastMouseX, this.lastMouseY, this.mouseButton);
    }
    
    handleMouseUp(e) {
        if (!this.isMouseDown) return;
        
        this.isMouseDown = false;
        
        // Send mouse up event
        this.sendMouseEvent('up', this.lastMouseX, this.lastMouseY, this.mouseButton);
    }
    
    handleMouseMove(e) {
        if (!this.clientConnected) return;
        
        // Calculate position relative to video
        const rect = this.videoDisplay.getBoundingClientRect();
        const x = e.clientX - rect.left;
        const y = e.clientY - rect.top;
        
        // Scale to screen coordinates
        const scaleX = this.screenWidth / rect.width;
        const scaleY = this.screenHeight / rect.height;
        
        const screenX = Math.round(x * scaleX);
        const screenY = Math.round(y * scaleY);
        
        this.lastMouseX = screenX;
        this.lastMouseY = screenY;
        
        // Send mouse move event
        if (this.isMouseDown) {
            this.sendMouseEvent('move', screenX, screenY, this.mouseButton);
        } else {
            this.sendMouseEvent('move', screenX, screenY, 0);
        }
    }
    
    handleMouseWheel(e) {
        if (!this.clientConnected) return;
        
        // Prevent page scroll
        e.preventDefault();
        
        // Send scroll event
        const delta = e.deltaY > 0 ? -120 : 120; // Negative for down, positive for up
        this.sendScroll(delta);
    }
    
    handleDoubleClick(e) {
        if (!this.clientConnected) return;
        
        // Calculate position
        const rect = this.videoDisplay.getBoundingClientRect();
        const x = e.clientX - rect.left;
        const y = e.clientY - rect.top;
        
        const scaleX = this.screenWidth / rect.width;
        const scaleY = this.screenHeight / rect.height;
        
        const screenX = Math.round(x * scaleX);
        const screenY = Math.round(y * scaleY);
        
        // Send double click
        this.sendMouseEvent('double_click', screenX, screenY, 0);
    }
    
    sendMouseEvent(type, x, y, button) {
        if (!this.ws || this.ws.readyState !== WebSocket.OPEN) return;
        
        this.ws.send(JSON.stringify({
            type: 'control',
            command: 'mouse',
            data: {
                action: type,
                x: x,
                y: y,
                button: button
            }
        }));
    }
    
    sendMouseClick(button) {
        if (!this.clientConnected) return;
        
        // Use the last known position
        this.sendMouseEvent('click', this.lastMouseX, this.lastMouseY, button);
    }
    
    sendDoubleClick() {
        if (!this.clientConnected) return;
        
        this.sendMouseEvent('double_click', this.lastMouseX, this.lastMouseY, 0);
    }
    
    sendScroll(delta) {
        if (!this.clientConnected) return;
        
        if (this.ws && this.ws.readyState === WebSocket.OPEN) {
            this.ws.send(JSON.stringify({
                type: 'control',
                command: 'scroll',
                data: {
                    delta: delta
                }
            }));
        }
    }
    
    // Touch Event Handlers
    handleTouchStart(e) {
        if (!this.clientConnected) return;
        
        this.touchActive = true;
        const touch = e.touches[0];
        const rect = this.touchPad.getBoundingClientRect();
        
        this.touchStartX = touch.clientX - rect.left;
        this.touchStartY = touch.clientY - rect.top;
        
        // Update indicator
        this.updateTouchIndicator(this.touchStartX, this.touchStartY);
        
        // Calculate relative position on video
        const videoRect = this.videoDisplay.getBoundingClientRect();
        const relativeX = (this.touchStartX / rect.width) * videoRect.width;
        const relativeY = (this.touchStartY / rect.height) * videoRect.height;
        
        const scaleX = this.screenWidth / videoRect.width;
        const scaleY = this.screenHeight / videoRect.height;
        
        this.lastMouseX = Math.round(relativeX * scaleX);
        this.lastMouseY = Math.round(relativeY * scaleY);
        
        // Send mouse move
        this.sendMouseEvent('move', this.lastMouseX, this.lastMouseY, 0);
        
        e.preventDefault();
    }
    
    handleTouchMove(e) {
        if (!this.touchActive) return;
        
        const touch = e.touches[0];
        const rect = this.touchPad.getBoundingClientRect();
        
        const currentX = touch.clientX - rect.left;
        const currentY = touch.clientY - rect.top;
        
        // Update indicator
        this.updateTouchIndicator(currentX, currentY);
        
        // Calculate delta
        const deltaX = currentX - this.touchStartX;
        const deltaY = currentY - this.touchStartY;
        
        // Update start position for continuous movement
        this.touchStartX = currentX;
        this.touchStartY = currentY;
        
        // Calculate new position on video
        const videoRect = this.videoDisplay.getBoundingClientRect();
        const relativeX = (currentX / rect.width) * videoRect.width;
        const relativeY = (currentY / rect.height) * videoRect.height;
        
        const scaleX = this.screenWidth / videoRect.width;
        const scaleY = this.screenHeight / videoRect.height;
        
        this.lastMouseX = Math.round(relativeX * scaleX);
        this.lastMouseY = Math.round(relativeY * scaleY);
        
        // Send mouse move
        this.sendMouseEvent('move', this.lastMouseX, this.lastMouseY, 0);
        
        e.preventDefault();
    }
    
    handleTouchEnd(e) {
        if (!this.touchActive) return;
        
        this.touchActive = false;
        
        // Send click at the last position
        this.sendMouseClick(0);
        
        // Hide indicator
        this.touchIndicator.style.opacity = '0';
    }
    
    updateTouchIndicator(x, y) {
        this.touchIndicator.style.left = `${x}px`;
        this.touchIndicator.style.top = `${y}px`;
        this.touchIndicator.style.opacity = '0.7';
    }
    
    // Keyboard Handlers
    sendText() {
        const text = this.keyboardInput.value;
        if (!text || !this.clientConnected) return;
        
        if (this.ws && this.ws.readyState === WebSocket.OPEN) {
            this.ws.send(JSON.stringify({
                type: 'control',
                command: 'keyboard',
                data: {
                    action: 'type',
                    text: text
                }
            }));
        }
        
        // Clear input
        this.keyboardInput.value = '';
    }
    
    sendShortcut(shortcut) {
        if (!this.clientConnected) return;
        
        if (this.ws && this.ws.readyState === WebSocket.OPEN) {
            this.ws.send(JSON.stringify({
                type: 'control',
                command: 'keyboard',
                data: {
                    action: 'shortcut',
                    shortcut: shortcut
                }
            }));
        }
    }
    
    handleGlobalKeydown(e) {
        // Don't intercept if typing in input
        if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') {
            return;
        }
        
        // Handle special keys
        const specialKeys = {
            'Escape': 'escape',
            'Tab': 'tab',
            'Enter': 'enter',
            ' ': 'space',
            'Backspace': 'backspace',
            'Delete': 'delete',
            'ArrowUp': 'arrow_up',
            'ArrowDown': 'arrow_down',
            'ArrowLeft': 'arrow_left',
            'ArrowRight': 'arrow_right',
            'Control': 'ctrl',
            'Alt': 'alt',
            'Shift': 'shift',
            'Meta': 'win' // Windows/Command key
        };
        
        if (e.key in specialKeys && this.clientConnected) {
            this.sendKeyPress(specialKeys[e.key], e.ctrlKey, e.altKey, e.shiftKey, e.metaKey);
            e.preventDefault();
        }
    }
    
    sendKeyPress(key, ctrl = false, alt = false, shift = false, meta = false) {
        if (!this.clientConnected) return;
        
        if (this.ws && this.ws.readyState === WebSocket.OPEN) {
            this.ws.send(JSON.stringify({
                type: 'control',
                command: 'keyboard',
                data: {
                    action: 'key_press',
                    key: key,
                    modifiers: {
                        ctrl: ctrl,
                        alt: alt,
                        shift: shift,
                        meta: meta
                    }
                }
            }));
        }
    }
    
    sendSettings() {
        if (!this.ws || this.ws.readyState !== WebSocket.OPEN) return;
        
        this.ws.send(JSON.stringify({
            type: 'settings',
            quality: this.quality,
            show_cursor: this.showCursor
        }));
    }
    
    // Fullscreen Handlers
    enterFullscreen() {
        if (this.videoDisplay.requestFullscreen) {
            this.videoDisplay.requestFullscreen().then(() => {
                document.body.classList.add('fullscreen');
            }).catch(err => {
                console.error('Error entering fullscreen:', err);
                this.fullscreenCheckbox.checked = false;
            });
        }
    }
    
    exitFullscreen() {
        if (document.exitFullscreen) {
            document.exitFullscreen().then(() => {
                document.body.classList.remove('fullscreen');
            }).catch(err => {
                console.error('Error exiting fullscreen:', err);
            });
        }
    }
}

// Initialize when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    new ScreenControl();
});
