import pytest
from src.security.encryption import encrypt, decrypt, generate_key

def test_encrypt_decrypt_cycle():
    key = generate_key()
    original_text = "Sensitive clinical data"
    
    encrypted = encrypt(original_text, key)
    assert encrypted != original_text
    
    decrypted = decrypt(encrypted, key)
    assert decrypted == original_text

def test_wrong_key_fails():
    key1 = generate_key()
    key2 = generate_key()
    original_text = "Data"
    
    encrypted = encrypt(original_text, key1)
    
    with pytest.raises(Exception):
        decrypt(encrypted, key2)
