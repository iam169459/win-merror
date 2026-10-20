# Win-Merror: Windows Screen Mirroring with Web Control

A secure Windows client application that streams your desktop to a web browser, with full mouse and keyboard control and comprehensive access control.

## Architecture

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Client    │────▶│    Server   │◀────│    Web      │
│  (Windows)  │     │  (Python)   │     │  (Browser)  │
└─────────────┘     └─────────────┘     └─────────────┘
     │                     │                    │
     ▼                     ▼                    ▼
 Captures screen      Relays video +       Displays video
 & sends to server    control commands    & sends inputs
```

## ⚠️ Security Features

### Full Access Control System

Win-Merror now includes comprehensive security features:

- **🔐 Authentication**: Username/password or token-based authentication
- **🎫 Session Management**: Token-based sessions with expiry
- **🛡️ IP Filtering**: Allow/block specific IPs or networks
- **⚡ Rate Limiting**: Prevent abuse with request throttling
- **🔒 SSL/TLS**: Optional encrypted connections (HTTPS/WSS)
- **👮 Permission System**: Fine-grained access control (view, control, admin)

## Features

- **Real-time screen streaming** from Windows to any web browser
- **Mouse control**: Move, click, scroll from the web interface
- **Keyboard control**: Send keystrokes and shortcuts
- **Low latency** WebSocket-based communication
- **Cross-platform viewing**: Works on any device with a modern browser (Mac, Linux, mobile)
- **Secure by default**: Authentication required for all connections

## Quick Start

### Prerequisites

- Python 3.10+
- Windows 10/11

### Installation

```bash
# Clone the repository
git clone https://github.com/iam169459/win-merror.git
cd win-merror

# Install dependencies
# For Ubuntu/Linux VPS (server only):
pip install -r requirements-server.txt

# For Windows (client):
pip install -r requirements-client.txt

# Or for full development (Windows only):
pip install -r requirements.txt
```

### Configuration

Before running, configure the security settings in `server/config.json`:

```json
{
    "security": {
        "authentication": {
            "enabled": true,
            "username": "admin",
            "password": "your-secure-password"
        },
        "sessions": {
            "enabled": true,
            "token_expiry": 3600
        },
        "ip_filtering": {
            "enabled": false,
            "allowed_ips": ["127.0.0.1", "192.168.1.0/24"]
        },
        "rate_limiting": {
            "enabled": true,
            "max_requests": 100,
            "window_seconds": 60
        },
        "ssl": {
            "enabled": false,
            "certfile": "cert.pem",
            "keyfile": "key.pem"
        }
    }
}
```

### Running

1. **Start the server** (in one terminal):
```bash
cd server
python server.py
```

2. **Start the client** (in another terminal):
```bash
# With username/password authentication
cd client
python client.py --username admin --password your-secure-password

# Or with a token (generate via web interface)
cd client
python client.py --token your-auth-token
```

3. **Open the web interface**:
   - Navigate to `http://localhost:8080` in your browser
   - Login with your credentials
   - View and control the Windows desktop

## Usage

- **View**: The web page will show the Windows desktop in real-time
- **Mouse Control**:
  - Click and drag on the video to move the mouse
  - Use the mouse buttons on the web interface
- **Keyboard Control**:
  - Type in the text input and press Enter to send keystrokes
  - Or click the virtual keyboard buttons

## Command Line Options

### Client Options
```bash
python client.py [OPTIONS]

Options:
  --host HOST         Server host (default: localhost)
  --port PORT         Server port (default: 8081)
  --fps FPS           Target frames per second (default: 20)
  --quality QUALITY   JPEG quality (0-100, default: 85)
  --scale SCALE       Screen capture scale factor (default: 1.0)
  --username USER     Username for authentication
  --password PASS     Password for authentication
  --token TOKEN       Authentication token
```

### Example: Connect to remote server
```bash
python client.py --host 192.168.1.100 --port 8081 --username admin --password secret
```

## Security Configuration

### Authentication

The server supports multiple authentication methods:

1. **Username/Password**: Configure in `server/config.json`
2. **Token-based**: Users receive tokens after login that can be used for subsequent connections

### IP Filtering

Restrict access to specific IPs or networks:

```json
"ip_filtering": {
    "enabled": true,
    "allowed_ips": ["127.0.0.1", "::1"],
    "allowed_networks": ["192.168.1.0/24", "10.0.0.0/8"]
}
```

### Rate Limiting

Prevent abuse with request throttling:

```json
"rate_limiting": {
    "enabled": true,
    "max_requests": 100,
    "window_seconds": 60,
    "ban_duration": 300
}
```

### SSL/TLS Encryption

Enable encrypted connections:

```json
"ssl": {
    "enabled": true,
    "certfile": "path/to/cert.pem",
    "keyfile": "path/to/key.pem"
}
```

Generate self-signed certificates:
```bash
openssl req -x509 -newkey rsa:4096 -keyout key.pem -out cert.pem -days 365 -nodes
```

## API Endpoints

| Endpoint | Method | Description | Authentication |
|----------|--------|-------------|---------------|
| `/api/status` | GET | Server status | None |
| `/api/users` | GET | List users | Admin token |
| `/api/connections` | GET | Active connections | None |

## User Management

### Adding Users

Users can be added programmatically through the `AccessControl` class:

```python
from auth import get_access_control

ac = get_access_control()
ac.add_user(
    username="newuser",
    password="password123",
    permissions=["view", "control"],
    is_admin=False
)
```

### User Permissions

| Permission | Description |
|------------|-------------|
| `view` | Can view the screen stream |
| `control` | Can send control commands (mouse/keyboard) |
| `admin` | Full access, including user management |

## Project Structure

```
win-merror/
├── client/
│   ├── client.py          # Main client application
│   └── requirements.txt
├── server/
│   ├── server.py          # WebSocket server with access control
│   ├── auth.py            # Authentication and authorization module
│   ├── config.json        # Security configuration
│   ├── static/            # Web assets
│   │   ├── index.html     # Web control interface
│   │   ├── style.css      # Styling
│   │   ├── auth.css       # Authentication styles
│   │   └── script.js      # WebSocket client & controls
│   └── requirements.txt
├── web/                   # (Symlink to server/static)
└── README.md
```

## Technologies

- **Client**: Python, PIL/Pillow, pywin32, websockets
- **Server**: Python, asyncio, websockets
- **Web**: HTML5, CSS3, JavaScript, WebSocket API

## Security Best Practices

✅ **DO**:
- Change default credentials in `config.json`
- Enable IP filtering for trusted networks only
- Use SSL/TLS for connections over the internet
- Keep software updated
- Use strong, unique passwords

❌ **DON'T**:
- Expose the server to the public internet without authentication
- Use default credentials in production
- Disable rate limiting on public-facing servers
- Share authentication tokens

## 🚨 IMPORTANT SECURITY NOTICE

⚠️ **This tool provides remote control of your desktop.**

- **Only run on trusted networks**
- **Always use authentication** (enabled by default)
- **Do not expose to the public internet** without proper security measures
- **Use a firewall** to restrict access to trusted IPs
- **Monitor connections** regularly

The developers are not responsible for any misuse or unauthorized access resulting from improper configuration.

## License

MIT License
