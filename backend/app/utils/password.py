import bcrypt

# bcrypt has a maximum input length of 72 bytes
_BCRYPT_MAX_BYTES = 72


class PasswordHasher:
    """Handles password hashing and verification using bcrypt"""
    
    @staticmethod
    def _truncate_password(password: str) -> bytes:
        """Encode and truncate password to bcrypt's 72-byte limit."""
        return password.encode('utf-8')[:_BCRYPT_MAX_BYTES]
    
    @staticmethod
    def hash_password(password: str) -> str:
        """
        Hash a password using bcrypt.
        
        Args:
            password: Plain text password
            
        Returns:
            Hashed password as string
        """
        password_bytes = PasswordHasher._truncate_password(password)
        salt = bcrypt.gensalt()
        hashed = bcrypt.hashpw(password_bytes, salt)
        return hashed.decode('utf-8')
    
    @staticmethod
    def verify_password(plain_password: str, hashed_password: str) -> bool:
        """
        Verify a password against its hash.
        
        Args:
            plain_password: Plain text password to verify
            hashed_password: Hashed password to compare against
            
        Returns:
            True if password matches, False otherwise
        """
        password_bytes = PasswordHasher._truncate_password(plain_password)
        hashed_bytes = hashed_password.encode('utf-8')
        return bcrypt.checkpw(password_bytes, hashed_bytes)
