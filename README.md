# Win-Merror: Windows Screen Mirroring with Web Control

A Windows client application that streams your desktop to a web browser, with full mouse and keyboard control.

## Architecture

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Client    │────▶│    Server   │◀────│    Web      │
│  (Windows)  │     │  (Python)   │     │  (Browser)  │
│             │◀────│             │────▶│             │
└─────────────┘     └─────────────┘     └─────────────┘
     │                     │                    │
     ▼                     ▼                    ▼
 Captures screen      Relays video +       Displays video
 & sends to server    control commands    & sends inputs
```

## Features

- **Real-time screen streaming** from Windows to any web browser
- **Mouse control**: Move, click, scroll from the web interface
- **Keyboard control**: Send keystrokes from the web interface
- **Low latency** WebSocket-based communication
- **Cross-platform viewing**: Works on any device with a modern browser (Mac, Linux, mobile)

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
pip install -r requirements.txt
```

### Running

1. **Start the server** (in one terminal):
```bash
cd server
python server.py
```

2. **Start the client** (in another terminal):
```bash
cd client
python client.py
```

3. **Open the web interface**:
   - Navigate to `http://localhost:8080` in your browser
   - Or from another device: `http://<windows-ip>:8080`

## Usage

- **View**: The web page will show the Windows desktop in real-time
- **Mouse Control**:
  - Click and drag on the video to move the mouse
  - Use the mouse buttons on the web interface
- **Keyboard Control**:
  - Type in the text input and press Enter to send keystrokes
  - Or click the virtual keyboard buttons

## Configuration

Edit `server/config.json` to change:
- Port settings
- Frame rate
- Quality settings

## Security Note

⚠️ **This tool provides remote control of your desktop.**
- Only run on trusted networks
- Do not expose the server to the public internet without authentication
- Use a firewall to restrict access to trusted IPs

## Project Structure

```
win-merror/
├── client/
│   ├── client.py          # Main client application
│   └── requirements.txt
├── server/
│   ├── server.py          # WebSocket server
│   ├── static/            # Web assets
│   │   ├── index.html     # Web control interface
│   │   ├── style.css      # Styling
│   │   └── script.js      # WebSocket client & controls
│   └── requirements.txt
├── web/                   # (Symlink to server/static)
└── README.md
```

## Technologies

- **Client**: Python, PIL/Pillow, pywin32, websockets
- **Server**: Python, asyncio, websockets
- **Web**: HTML5, CSS3, JavaScript, WebSocket API

## License

MIT License
