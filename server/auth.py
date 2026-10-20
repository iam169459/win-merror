"""
Authentication and Access Control Module
Handles user authentication, session management, and authorization
"""

import hashlib
import hmac
import json
import logging
import os
import secrets
import time
from typing import Dict, Optional, Set, List, Any
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import ipaddress

logger = logging.getLogger(__name__)


@dataclass
class User:
    """User account information"""
    username: str
    password_hash: str
    salt: str
    permissions: List[str] = field(default_factory=lambda: ["view", "control"])
    is_admin: bool = False
    created_at: float = field(default_factory=time.time)
    last_login: Optional[float] = None
    login_attempts: int = 0
    locked_until: Optional[float] = None


@dataclass
class Session:
    """User session information"""
    session_id: str
    user_id: str
    created_at: float = field(default_factory=time.time)
    expires_at: float = 0
    ip_address: str = ""
    user_agent: str = ""
    last_activity: float = field(default_factory=time.time)
    permissions: List[str] = field(default_factory=list)


@dataclass
class RateLimitEntry:
    """Rate limiting tracking"""
    ip_address: str
    request_count: int = 0
    last_request: float = 0
    banned_until: Optional[float] = None


class AccessControl:
    """
    Main access control system
    Manages authentication, sessions, and authorization
    """
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config.get("security", {})
        self.users: Dict[str, User] = {}
        self.sessions: Dict[str, Session] = {}
        self.rate_limits: Dict[str, RateLimitEntry] = {}
        self.active_connections: Dict[str, Any] = {}
        
        # Initialize with default user if configured
        auth_config = self.config.get("authentication", {})
        if auth_config.get("enabled", True):
            self._initialize_default_user(auth_config)
        
        # Initialize IP filtering
        self._ip_networks: List[ipaddress.IPv4Network] = []
        self._ip_networks_v6: List[ipaddress.IPv6Network] = []
        self._allowed_ips: Set[str] = set()
        self._blocked_ips: Set[str] = set()
        self._load_ip_filters()
        
        logger.info("Access control system initialized")
    
    def _initialize_default_user(self, auth_config: Dict[str, Any]):
        """Initialize default user from configuration"""
        username = auth_config.get("username", "admin")
        password = auth_config.get("password", "admin123")
        password_hash = auth_config.get("password_hash")
        
        if password_hash:
            # Use pre-computed hash
            self.users[username] = User(
                username=username,
                password_hash=password_hash,
                salt="",
                permissions=["view", "control", "admin"],
                is_admin=True
            )
        else:
            # Hash the password
            salt = secrets.token_hex(16)
            hashed = self._hash_password(password, salt)
            self.users[username] = User(
                username=username,
                password_hash=hashed,
                salt=salt,
                permissions=["view", "control", "admin"],
                is_admin=True
            )
        
        logger.info(f"Default user '{username}' initialized")
    
    def _load_ip_filters(self):
        """Load IP filtering rules from configuration"""
        ip_config = self.config.get("ip_filtering", {})
        if not ip_config.get("enabled", False):
            return
        
        for ip_str in ip_config.get("allowed_ips", []):
            try:
                if '/' in ip_str:
                    # It's a network
                    network = ipaddress.ip_network(ip_str, strict=False)
                    if network.version == 4:
                        self._ip_networks.append(network)
                    else:
                        self._ip_networks_v6.append(network)
                else:
                    # Single IP
                    self._allowed_ips.add(ip_str)
            except ValueError as e:
                logger.warning(f"Invalid IP/network in allowed_ips: {ip_str} ({e})")
        
        for ip_str in ip_config.get("blocked_ips", []):
            self._blocked_ips.add(ip_str)
        
        logger.info(f"Loaded IP filters: {len(self._allowed_ips)} allowed IPs, "
                   f"{len(self._blocked_ips)} blocked IPs, "
                   f"{len(self._ip_networks)} IPv4 networks, "
                   f"{len(self._ip_networks_v6)} IPv6 networks")
    
    def _hash_password(self, password: str, salt: str) -> str:
        """Hash password using PBKDF2-HMAC-SHA256"""
        import hashlib
        import binascii
        
        # Use a strong hash function
        dk = hashlib.pbkdf2_hmac(
            'sha256',
            password.encode('utf-8'),
            salt.encode('utf-8'),
            100000  # Number of iterations
        )
        return binascii.hexlify(dk).decode('utf-8')
    
    def _verify_password(self, password: str, stored_hash: str, salt: str) -> bool:
        """Verify password against stored hash"""
        new_hash = self._hash_password(password, salt)
        return hmac.compare_digest(stored_hash, new_hash)
    
    # Authentication methods
    def authenticate(self, username: str, password: str, ip_address: str = "") -> Optional[User]:
        """
        Authenticate a user
        Returns User object if successful, None otherwise
        """
        if not self.config.get("authentication", {}).get("enabled", True):
            # Authentication disabled, return default user
            if self.users:
                return next(iter(self.users.values()))
            return None
        
        user = self.users.get(username)
        if not user:
            logger.warning(f"Authentication failed: user '{username}' not found")
            return None
        
        # Check if account is locked
        if user.locked_until and user.locked_until > time.time():
            logger.warning(f"Authentication failed: user '{username}' is locked")
            return None
        
        # Verify password
        if not self._verify_password(password, user.password_hash, user.salt):
            user.login_attempts += 1
            
            # Lock account after 5 failed attempts
            if user.login_attempts >= 5:
                user.locked_until = time.time() + 300  # 5 minutes
                logger.warning(f"User '{username}' locked due to too many failed attempts")
            
            logger.warning(f"Authentication failed: invalid password for '{username}'")
            return None
        
        # Successful login
        user.login_attempts = 0
        user.locked_until = None
        user.last_login = time.time()
        
        logger.info(f"User '{username}' authenticated successfully from {ip_address}")
        return user
    
    def create_session(self, user: User, ip_address: str = "", 
                       user_agent: str = "") -> Optional[Session]:
        """
        Create a new session for a user
        Returns Session object if successful
        """
        if not self.config.get("sessions", {}).get("enabled", True):
            return None
        
        session_id = secrets.token_urlsafe(32)
        expiry = time.time() + self.config.get("sessions", {}).get("token_expiry", 3600)
        
        session = Session(
            session_id=session_id,
            user_id=user.username,
            expires_at=expiry,
            ip_address=ip_address,
            user_agent=user_agent,
            permissions=user.permissions.copy()
        )
        
        self.sessions[session_id] = session
        logger.info(f"Session created: {session_id} for user '{user.username}'")
        return session
    
    def get_session(self, session_id: str) -> Optional[Session]:
        """Get session by ID"""
        session = self.sessions.get(session_id)
        if not session:
            return None
        
        # Check if session is expired
        if session.expires_at < time.time():
            del self.sessions[session_id]
            logger.info(f"Session expired: {session_id}")
            return None
        
        # Update last activity
        session.last_activity = time.time()
        return session
    
    def invalidate_session(self, session_id: str):
        """Invalidate a session"""
        if session_id in self.sessions:
            del self.sessions[session_id]
            logger.info(f"Session invalidated: {session_id}")
    
    def invalidate_all_sessions(self, user_id: str = None):
        """Invalidate all sessions, optionally for a specific user"""
        if user_id:
            # Invalidate sessions for specific user
            to_delete = [sid for sid, s in self.sessions.items() if s.user_id == user_id]
            for sid in to_delete:
                del self.sessions[sid]
            logger.info(f"Invalidated {len(to_delete)} sessions for user '{user_id}'")
        else:
            # Invalidate all sessions
            count = len(self.sessions)
            self.sessions.clear()
            logger.info(f"Invalidated all {count} sessions")
    
    def generate_token(self, session: Session) -> str:
        """Generate a JWT-like token for a session"""
        import json
        import base64
        
        # Create token payload
        payload = {
            "sid": session.session_id,
            "user": session.user_id,
            "exp": int(session.expires_at),
            "iat": int(session.created_at),
            "permissions": session.permissions
        }
        
        # Sign the token
        secret = self.config.get("secret_key", "win-merror-secret")
        payload_json = json.dumps(payload, sort_keys=True)
        signature = hmac.new(
            secret.encode('utf-8'),
            payload_json.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        # Encode as base64
        encoded_payload = base64.urlsafe_b64encode(payload_json.encode('utf-8')).decode('utf-8')
        
        return f"{encoded_payload}.{signature}"
    
    def verify_token(self, token: str) -> Optional[Session]:
        """Verify a token and return the session"""
        import json
        import base64
        
        try:
            parts = token.split('.')
            if len(parts) != 2:
                return None
            
            encoded_payload, signature = parts
            
            # Decode payload
            payload_json = base64.urlsafe_b64decode(encoded_payload.encode('utf-8')).decode('utf-8')
            payload = json.loads(payload_json)
            
            # Verify signature
            secret = self.config.get("secret_key", "win-merror-secret")
            expected_signature = hmac.new(
                secret.encode('utf-8'),
                payload_json.encode('utf-8'),
                hashlib.sha256
            ).hexdigest()
            
            if not hmac.compare_digest(signature, expected_signature):
                logger.warning("Token verification failed: invalid signature")
                return None
            
            # Check expiration
            if payload.get('exp', 0) < time.time():
                logger.warning("Token verification failed: token expired")
                return None
            
            # Get session
            session_id = payload.get('sid')
            session = self.get_session(session_id)
            
            if not session:
                logger.warning("Token verification failed: session not found")
                return None
            
            # Verify user matches
            if session.user_id != payload.get('user'):
                logger.warning("Token verification failed: user mismatch")
                return None
            
            return session
            
        except Exception as e:
            logger.warning(f"Token verification failed: {e}")
            return None
    
    # Authorization methods
    def has_permission(self, session: Session, permission: str) -> bool:
        """Check if session has a specific permission"""
        return permission in session.permissions or "admin" in session.permissions
    
    def is_admin(self, session: Session) -> bool:
        """Check if session user is an admin"""
        user = self.users.get(session.user_id)
        return user and user.is_admin
    
    # IP Filtering methods
    def is_ip_allowed(self, ip_address: str) -> bool:
        """Check if an IP address is allowed"""
        ip_config = self.config.get("ip_filtering", {})
        if not ip_config.get("enabled", False):
            return True
        
        # Check blocked IPs first
        if ip_address in self._blocked_ips:
            logger.warning(f"Connection blocked: IP {ip_address} is in block list")
            return False
        
        # Check allowed IPs
        if ip_address in self._allowed_ips:
            return True
        
        # Check networks
        try:
            ip = ipaddress.ip_address(ip_address)
            if ip.version == 4:
                for network in self._ip_networks:
                    if ip in network:
                        return True
            else:
                for network in self._ip_networks_v6:
                    if ip in network:
                        return True
        except ValueError:
            logger.warning(f"Invalid IP address: {ip_address}")
            return False
        
        # If we have allowed networks but IP doesn't match, block it
        if self._ip_networks or self._ip_networks_v6 or self._allowed_ips:
            logger.warning(f"Connection blocked: IP {ip_address} not in allowed list")
            return False
        
        return True
    
    # Rate Limiting methods
    def check_rate_limit(self, ip_address: str) -> bool:
        """
        Check rate limit for an IP address
        Returns True if request is allowed, False if rate limited
        """
        rate_config = self.config.get("rate_limiting", {})
        if not rate_config.get("enabled", True):
            return True
        
        now = time.time()
        entry = self.rate_limits.get(ip_address)
        
        if not entry:
            entry = RateLimitEntry(ip_address=ip_address)
            self.rate_limits[ip_address] = entry
            return True
        
        # Check if currently banned
        if entry.banned_until and entry.banned_until > now:
            logger.warning(f"Rate limit: IP {ip_address} is banned until {entry.banned_until}")
            return False
        
        # Check if ban has expired
        if entry.banned_until and entry.banned_until <= now:
            entry.banned_until = None
            entry.request_count = 0
        
        # Check window
        window = rate_config.get("window_seconds", 60)
        if now - entry.last_request > window:
            entry.request_count = 0
            entry.last_request = now
        
        # Increment count
        entry.request_count += 1
        entry.last_request = now
        
        max_requests = rate_config.get("max_requests", 100)
        if entry.request_count > max_requests:
            ban_duration = rate_config.get("ban_duration", 300)
            entry.banned_until = now + ban_duration
            logger.warning(f"Rate limit exceeded: IP {ip_address} banned for {ban_duration}s")
            return False
        
        return True
    
    # Connection tracking
    def register_connection(self, connection_id: str, ip_address: str, 
                           connection_type: str = "viewer"):
        """Register a new connection"""
        self.active_connections[connection_id] = {
            "ip_address": ip_address,
            "type": connection_type,
            "connected_at": time.time(),
            "last_activity": time.time()
        }
        logger.info(f"Connection registered: {connection_id} ({connection_type}) from {ip_address}")
    
    def unregister_connection(self, connection_id: str):
        """Unregister a connection"""
        if connection_id in self.active_connections:
            del self.active_connections[connection_id]
            logger.info(f"Connection unregistered: {connection_id}")
    
    def get_connection_info(self, connection_id: str) -> Optional[Dict[str, Any]]:
        """Get connection information"""
        conn = self.active_connections.get(connection_id)
        if conn:
            conn["last_activity"] = time.time()
        return conn
    
    def get_all_connections(self) -> List[Dict[str, Any]]:
        """Get all active connections"""
        return list(self.active_connections.values())
    
    def cleanup_expired(self):
        """Clean up expired sessions and rate limit entries"""
        now = time.time()
        
        # Clean up expired sessions
        expired_sessions = [sid for sid, s in self.sessions.items() if s.expires_at < now]
        for sid in expired_sessions:
            del self.sessions[sid]
        
        if expired_sessions:
            logger.info(f"Cleaned up {len(expired_sessions)} expired sessions")
        
        # Clean up old rate limit entries
        old_entries = [ip for ip, e in self.rate_limits.items() 
                      if e.banned_until and e.banned_until < now and 
                      now - e.last_request > 3600]
        for ip in old_entries:
            del self.rate_limits[ip]
        
        if old_entries:
            logger.info(f"Cleaned up {len(old_entries)} old rate limit entries")
    
    # User management
    def add_user(self, username: str, password: str, permissions: List[str] = None,
                 is_admin: bool = False) -> bool:
        """Add a new user"""
        if username in self.users:
            logger.warning(f"User '{username}' already exists")
            return False
        
        salt = secrets.token_hex(16)
        password_hash = self._hash_password(password, salt)
        
        self.users[username] = User(
            username=username,
            password_hash=password_hash,
            salt=salt,
            permissions=permissions or ["view", "control"],
            is_admin=is_admin
        )
        
        logger.info(f"User '{username}' added")
        return True
    
    def remove_user(self, username: str) -> bool:
        """Remove a user"""
        if username not in self.users:
            return False
        
        # Invalidate all sessions for this user
        self.invalidate_all_sessions(username)
        
        del self.users[username]
        logger.info(f"User '{username}' removed")
        return True
    
    def update_user_password(self, username: str, new_password: str) -> bool:
        """Update user password"""
        user = self.users.get(username)
        if not user:
            return False
        
        salt = secrets.token_hex(16)
        password_hash = self._hash_password(new_password, salt)
        
        user.password_hash = password_hash
        user.salt = salt
        
        logger.info(f"Password updated for user '{username}'")
        return True
    
    def list_users(self) -> List[Dict[str, Any]]:
        """List all users"""
        users = []
        for username, user in self.users.items():
            users.append({
                "username": username,
                "permissions": user.permissions,
                "is_admin": user.is_admin,
                "created_at": user.created_at,
                "last_login": user.last_login,
                "locked": user.locked_until is not None and user.locked_until > time.time()
            })
        return users


# Global access control instance
_access_control: Optional[AccessControl] = None


def get_access_control(config: Dict[str, Any] = None) -> AccessControl:
    """Get the global access control instance"""
    global _access_control
    if _access_control is None:
        _access_control = AccessControl(config or {})
    return _access_control


def init_access_control(config: Dict[str, Any]):
    """Initialize the global access control instance"""
    global _access_control
    _access_control = AccessControl(config)
    return _access_control
