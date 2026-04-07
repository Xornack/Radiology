from cryptography.fernet import Fernet

def generate_key() -> bytes:
    """
    Generates a new encryption key.
    """
    return Fernet.generate_key()

def encrypt(data: str, key: bytes) -> bytes:
    """
    Encrypts a string using the provided key.
    """
    f = Fernet(key)
    return f.encrypt(data.encode())

def decrypt(token: bytes, key: bytes) -> str:
    """
    Decrypts a token back to a string using the provided key.
    """
    f = Fernet(key)
    return f.decrypt(token).decode()
