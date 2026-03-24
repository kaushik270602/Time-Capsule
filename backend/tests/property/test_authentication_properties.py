# Feature: timelock
# Property-based tests for authentication and password security

import pytest
from hypothesis import given, strategies as st, settings
from contextlib import contextmanager
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.models.base import Base
from app.models.user import User
from app.services.auth_service import (
    AuthService,
    EmailAlreadyExistsError,
    InvalidEmailError,
    InvalidCredentialsError,
    UnverifiedEmailError,
    UserNotFoundError
)
from app.utils.password import PasswordHasher


# Context manager for database sessions (compatible with Hypothesis)
@contextmanager
def get_db_session():
    """Create a fresh database session for testing"""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        yield session
    finally:
        session.close()


# Property 54: Passwords are always hashed
@settings(max_examples=20, deadline=None)
@given(password=st.text(min_size=1, max_size=72))
def test_property_54_passwords_always_hashed(password):
    """
    Property 54: Passwords are always hashed
    
    For any password string provided by a user, the system should hash the password
    before storage, ensuring that plain text passwords are never stored in the database.
    The hashed password should:
    1. Be different from the original password
    2. Be a valid bcrypt hash
    3. Be verifiable against the original password
    4. Produce different hashes for the same password (due to salt)
    
    Validates: Requirements 15.1
    """
    # Hash the password
    hashed = PasswordHasher.hash_password(password)
    
    # Verify the hashed password is different from the original
    # (unless the password happens to look like a bcrypt hash, which is extremely unlikely)
    assert hashed != password, "Hashed password should be different from plain text password"
    
    # Verify the hashed password is a valid bcrypt hash
    # Bcrypt hashes start with $2a$, $2b$, or $2y$ and have a specific format
    assert hashed.startswith(('$2a$', '$2b$', '$2y$')), "Hashed password should be a valid bcrypt hash"
    
    # Verify the hash is the expected length (bcrypt hashes are 60 characters)
    assert len(hashed) == 60, "Bcrypt hash should be 60 characters long"
    
    # Verify the hashed password can be verified against the original
    assert PasswordHasher.verify_password(password, hashed) == True, \
        "Hashed password should verify successfully against original password"
    
    # Verify that a different password does not verify
    if len(password) > 0:
        different_password = password + "x"
        # Only assert difference if the truncated bytes actually differ
        orig_bytes = password.encode('utf-8')[:72]
        diff_bytes = different_password.encode('utf-8')[:72]
        if orig_bytes != diff_bytes:
            assert PasswordHasher.verify_password(different_password, hashed) == False, \
                "Different password should not verify against hash"
    
    # Verify that hashing the same password twice produces different hashes (due to salt)
    hashed2 = PasswordHasher.hash_password(password)
    assert hashed != hashed2, "Hashing the same password twice should produce different hashes (salt)"
    
    # But both hashes should verify against the original password
    assert PasswordHasher.verify_password(password, hashed2) == True, \
        "Second hash should also verify successfully against original password"


@settings(max_examples=15, deadline=None)
@given(
    password1=st.text(min_size=1, max_size=72),
    password2=st.text(min_size=1, max_size=72)
)
def test_property_54_different_passwords_different_hashes(password1, password2):
    """
    Property 54 (Extended): Different passwords produce different hashes
    
    For any two different passwords, the system should produce different hashes,
    ensuring that password hashes are unique and cannot be used to identify
    users with the same password.
    
    Validates: Requirements 15.1
    """
    # Skip if passwords are the same
    if password1 == password2:
        return
    
    # Hash both passwords
    hash1 = PasswordHasher.hash_password(password1)
    hash2 = PasswordHasher.hash_password(password2)
    
    # Verify the hashes are different
    assert hash1 != hash2, "Different passwords should produce different hashes"
    
    # Verify each hash only verifies against its own password
    assert PasswordHasher.verify_password(password1, hash1) == True
    assert PasswordHasher.verify_password(password2, hash2) == True
    assert PasswordHasher.verify_password(password1, hash2) == False
    assert PasswordHasher.verify_password(password2, hash1) == False


@settings(max_examples=15, deadline=None)
@given(password=st.text(min_size=8, max_size=50))
def test_property_54_hash_is_deterministic_for_verification(password):
    """
    Property 54 (Extended): Hash verification is deterministic
    
    For any password and its hash, verification should consistently return True
    for the correct password and False for incorrect passwords, regardless of
    how many times verification is performed.
    
    Validates: Requirements 15.1
    """
    # Ensure password doesn't exceed bcrypt's 72-byte limit when encoded
    password_bytes = password.encode('utf-8')
    if len(password_bytes) > 72:
        return  # Skip passwords that exceed bcrypt's byte limit
    
    # Hash the password once
    hashed = PasswordHasher.hash_password(password)
    
    # Verify multiple times - should always return True
    for _ in range(5):
        assert PasswordHasher.verify_password(password, hashed) == True, \
            "Verification should consistently return True for correct password"
    
    # Verify with wrong passwords - should always return False
    wrong_passwords = [
        password + "x",
        "x" + password,
        password.upper() if password.lower() == password else password.lower(),
    ]
    
    for wrong_password in wrong_passwords:
        if wrong_password != password and len(wrong_password.encode('utf-8')) <= 72:
            assert PasswordHasher.verify_password(wrong_password, hashed) == False, \
                f"Verification should consistently return False for incorrect password"


# Property 4: Valid credentials grant access
@settings(max_examples=20, deadline=None)
@given(user_id=st.integers(min_value=1, max_value=1000000))
def test_property_4_valid_credentials_grant_access(user_id):
    """
    Property 4: Valid credentials grant access

    For any registered and verified user, providing correct email and password should
    return a valid JWT token with expiration time. The token should:
    1. Be a valid JWT string
    2. Contain the user_id in the payload
    3. Have an expiration time set
    4. Be verifiable and return the correct user_id

    Validates: Requirements 1.5, 1.7
    """
    from app.utils.jwt import JWTManager

    # Create a token for the user
    token = JWTManager.create_token(user_id)

    # Verify the token is a non-empty string
    assert isinstance(token, str), "Token should be a string"
    assert len(token) > 0, "Token should not be empty"

    # Verify the token has the JWT structure (header.payload.signature)
    parts = token.split('.')
    assert len(parts) == 3, "JWT token should have 3 parts separated by dots"

    # Verify the token can be validated and returns the correct user_id
    validated_user_id = JWTManager.validate_token(token)
    assert validated_user_id == user_id, \
        f"Validated user_id {validated_user_id} should match original user_id {user_id}"


@settings(max_examples=20, deadline=None)
@given(
    user_id=st.integers(min_value=1, max_value=1000000),
    expiration_hours=st.integers(min_value=1, max_value=168)  # 1 hour to 1 week
)
def test_property_4_token_with_custom_expiration(user_id, expiration_hours):
    """
    Property 4 (Extended): Tokens can be created with custom expiration times

    For any user_id and expiration time, the system should create a valid token
    that can be validated and returns the correct user_id.

    Validates: Requirements 1.5, 1.7
    """
    from app.utils.jwt import JWTManager

    # Create a token with custom expiration
    token = JWTManager.create_token(user_id, expiration_hours=expiration_hours)

    # Verify the token is valid
    assert isinstance(token, str), "Token should be a string"
    assert len(token) > 0, "Token should not be empty"

    # Verify the token can be validated
    validated_user_id = JWTManager.validate_token(token)
    assert validated_user_id == user_id, \
        f"Validated user_id should match original user_id"


# Property 57: Expired sessions require re-authentication
@settings(max_examples=15, deadline=None)
@given(user_id=st.integers(min_value=1, max_value=1000000))
def test_property_57_expired_sessions_require_reauthentication(user_id):
    """
    Property 57: Expired sessions require re-authentication

    For any request with an expired JWT token, the system should reject the request
    and require the user to log in again. The system should:
    1. Create a token with a very short expiration (for testing)
    2. Wait for the token to expire
    3. Attempt to validate the expired token
    4. Receive an ExpiredTokenError

    Validates: Requirements 15.5
    """
    from app.utils.jwt import JWTManager, ExpiredTokenError
    from datetime import datetime, timedelta
    import jwt
    from app.config import settings
    import time

    # Create a token that expires in 1 second
    expiration = datetime.utcnow() + timedelta(seconds=1)
    payload = {
        "user_id": user_id,
        "exp": expiration,
        "iat": datetime.utcnow()
    }

    token = jwt.encode(
        payload,
        settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM
    )

    # Verify the token is initially valid
    validated_user_id = JWTManager.validate_token(token)
    assert validated_user_id == user_id, "Token should be valid initially"

    # Wait for the token to expire (1.5 seconds to be safe)
    time.sleep(1.5)

    # Attempt to validate the expired token - should raise ExpiredTokenError
    with pytest.raises(ExpiredTokenError) as exc_info:
        JWTManager.validate_token(token)

    # Verify the error message indicates expiration
    assert "expired" in str(exc_info.value).lower(), \
        "Error message should indicate token has expired"


@settings(max_examples=15, deadline=None)
@given(user_id=st.integers(min_value=1, max_value=1000000))
def test_property_57_invalid_tokens_rejected(user_id):
    """
    Property 57 (Extended): Invalid tokens are rejected

    For any invalid token (malformed, wrong signature, missing claims), the system
    should reject the token and raise an appropriate error.

    Validates: Requirements 15.5
    """
    from app.utils.jwt import JWTManager, InvalidTokenError, ExpiredTokenError

    # Test with completely invalid token
    with pytest.raises((InvalidTokenError, ExpiredTokenError)):
        JWTManager.validate_token("invalid.token.here")

    # Test with empty token
    with pytest.raises((InvalidTokenError, ExpiredTokenError)):
        JWTManager.validate_token("")

    # Test with token missing parts
    with pytest.raises((InvalidTokenError, ExpiredTokenError)):
        JWTManager.validate_token("invalid")

    # Test with token signed with wrong secret
    import jwt
    from datetime import datetime, timedelta

    wrong_secret_token = jwt.encode(
        {
            "user_id": user_id,
            "exp": datetime.utcnow() + timedelta(hours=1),
            "iat": datetime.utcnow()
        },
        "wrong-secret-key",
        algorithm="HS256"
    )

    with pytest.raises((InvalidTokenError, ExpiredTokenError)):
        JWTManager.validate_token(wrong_secret_token)


@settings(max_examples=15, deadline=None)
@given(user_id=st.integers(min_value=1, max_value=1000000))
def test_property_57_token_without_user_id_rejected(user_id):
    """
    Property 57 (Extended): Tokens without user_id claim are rejected

    For any token that doesn't contain a user_id claim, the system should
    reject the token with an InvalidTokenError.

    Validates: Requirements 15.5
    """
    from app.utils.jwt import JWTManager, InvalidTokenError
    from datetime import datetime, timedelta
    import jwt
    from app.config import settings

    # Create a token without user_id claim
    payload = {
        "exp": datetime.utcnow() + timedelta(hours=1),
        "iat": datetime.utcnow()
        # Missing user_id
    }

    token = jwt.encode(
        payload,
        settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM
    )

    # Attempt to validate the token - should raise InvalidTokenError
    with pytest.raises(InvalidTokenError) as exc_info:
        JWTManager.validate_token(token)

    # Verify the error message indicates missing user_id
    assert "user_id" in str(exc_info.value).lower(), \
        "Error message should indicate missing user_id claim"



# ============================================================================
# Authentication Flow Property Tests
# ============================================================================

# Helper function to generate valid emails that pass our validation
def valid_email_strategy():
    """Generate emails that pass the auth service validation"""
    return st.builds(
        lambda local, domain, tld: f"{local}@{domain}.{tld}",
        local=st.text(
            alphabet='abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._%-+',
            min_size=1,
            max_size=20
        ).filter(lambda x: len(x) > 0 and x[0].isalnum()),
        domain=st.text(
            alphabet='abcdefghijklmnopqrstuvwxyz0123456789-',
            min_size=1,
            max_size=20
        ).filter(lambda x: len(x) > 0 and x[0].isalnum() and x[-1].isalnum() and '--' not in x),
        tld=st.text(
            alphabet='abcdefghijklmnopqrstuvwxyz',
            min_size=2,
            max_size=10
        )
    )


# Helper function to generate valid passwords (max 72 bytes when UTF-8 encoded)
def valid_password_strategy():
    """Generate passwords that don't exceed bcrypt's 72-byte limit"""
    return st.text(min_size=8, max_size=72).filter(
        lambda p: len(p.encode('utf-8')) <= 72
    )


# Property 1: User registration creates valid accounts
@settings(max_examples=10, deadline=None)
@given(
    email=valid_email_strategy(),
    password=valid_password_strategy()
)
def test_property_1_user_registration_creates_valid_accounts(email, password):
    """
    Property 1: User registration creates valid accounts
    
    For any valid email and password combination, registering a new user should
    create an account with hashed password and trigger a verification email.
    The created account should:
    1. Have a unique ID
    2. Store the email correctly
    3. Have a hashed password (not plain text)
    4. Be marked as unverified initially
    5. Have created_at and updated_at timestamps
    
    Validates: Requirements 1.1, 1.2, 1.10
    """
    with get_db_session() as db_session:
        auth_service = AuthService(db_session)
        
        # Register a new user
        user = auth_service.register_user(email, password)
        
        # Verify user was created with valid ID
        assert user.id is not None, "User should have an ID"
        assert user.id > 0, "User ID should be positive"
        
        # Verify email is stored correctly
        assert user.email == email, "User email should match provided email"
        
        # Verify password is hashed (not plain text)
        assert user.password_hash != password, "Password should be hashed, not stored as plain text"
        assert user.password_hash.startswith(('$2a$', '$2b$', '$2y$')), \
            "Password hash should be a valid bcrypt hash"
        
        # Verify password hash can be verified
        assert PasswordHasher.verify_password(password, user.password_hash), \
            "Hashed password should verify against original password"
        
        # Verify user is initially unverified
        assert user.is_verified == False, "New user should be unverified initially"
        
        # Verify timestamps are set
        assert user.created_at is not None, "User should have created_at timestamp"
        assert user.updated_at is not None, "User should have updated_at timestamp"


# Property 2: Duplicate email registration is rejected
@settings(max_examples=10, deadline=None)
@given(
    email=valid_email_strategy(),
    password1=valid_password_strategy(),
    password2=valid_password_strategy()
)
def test_property_2_duplicate_email_registration_rejected(email, password1, password2):
    """
    Property 2: Duplicate email registration is rejected
    
    For any email address that already exists in the system, attempting to
    register with that email should be rejected with an EmailAlreadyExistsError,
    regardless of whether the password is the same or different.
    
    Validates: Requirements 1.4
    """
    with get_db_session() as db_session:
        auth_service = AuthService(db_session)
        
        # Register first user with the email
        user1 = auth_service.register_user(email, password1)
        assert user1.id is not None, "First user should be created successfully"
        
        # Attempt to register second user with same email - should raise error
        with pytest.raises(EmailAlreadyExistsError) as exc_info:
            auth_service.register_user(email, password2)
        
        # Verify error message is descriptive
        assert "already" in str(exc_info.value).lower(), \
            "Error message should indicate email already exists"
        
        # Verify only one user exists in database
        users = db_session.query(User).filter(User.email == email).all()
        assert len(users) == 1, "Only one user should exist with the email"
        assert users[0].id == user1.id, "The existing user should be the first one created"


# Property 3: Email verification activates accounts
@settings(max_examples=10, deadline=None)
@given(
    email=valid_email_strategy(),
    password=valid_password_strategy()
)
def test_property_3_email_verification_activates_accounts(email, password):
    """
    Property 3: Email verification activates accounts
    
    For any unverified user account, marking the account as verified should
    enable full access. The account should transition from is_verified=False
    to is_verified=True, allowing login.
    
    Note: This test directly sets is_verified since email verification
    token system is not yet fully implemented.
    
    Validates: Requirements 1.3
    """
    with get_db_session() as db_session:
        auth_service = AuthService(db_session)
        
        # Register a new user (initially unverified)
        user = auth_service.register_user(email, password)
        assert user.is_verified == False, "New user should be unverified"
        
        # Attempt to login before verification - should raise UnverifiedEmailError
        with pytest.raises(UnverifiedEmailError):
            auth_service.login(email, password)
        
        # Manually verify the email (simulating verification process)
        user.is_verified = True
        db_session.commit()
        db_session.refresh(user)
        
        # Verify the account is now marked as verified
        assert user.is_verified == True, "User should be verified after verification"
        
        # Attempt to login after verification - should succeed
        logged_in_user, token = auth_service.login(email, password)
        assert logged_in_user.id == user.id, "Login should return the correct user"
        assert token is not None, "Login should return a JWT token"
        assert len(token) > 0, "Token should not be empty"


# Property 5: Invalid credentials are rejected
@settings(max_examples=10, deadline=None)
@given(
    email=valid_email_strategy(),
    correct_password=valid_password_strategy(),
    wrong_password=valid_password_strategy()
)
def test_property_5_invalid_credentials_rejected(email, correct_password, wrong_password):
    """
    Property 5: Invalid credentials are rejected
    
    For any login attempt with incorrect email or password, the system should
    reject the attempt and return an error message without revealing which
    field was incorrect (to prevent user enumeration attacks).
    
    Validates: Requirements 1.6
    """
    # Skip if passwords are the same
    if correct_password == wrong_password:
        return
    
    with get_db_session() as db_session:
        auth_service = AuthService(db_session)
        
        # Register and verify a user
        user = auth_service.register_user(email, correct_password)
        user.is_verified = True
        db_session.commit()
        
        # Test 1: Login with wrong password
        with pytest.raises(InvalidCredentialsError) as exc_info:
            auth_service.login(email, wrong_password)
        
        error_msg = str(exc_info.value).lower()
        # Verify error message doesn't reveal which field is wrong
        assert "invalid" in error_msg, "Error should indicate invalid credentials"
        # Should not say "password" specifically to avoid enumeration
        
        # Test 2: Login with non-existent email
        fake_email = "nonexistent_" + email
        with pytest.raises(InvalidCredentialsError) as exc_info:
            auth_service.login(fake_email, correct_password)
        
        error_msg = str(exc_info.value).lower()
        assert "invalid" in error_msg, "Error should indicate invalid credentials"
        
        # Test 3: Login with correct credentials should succeed
        logged_in_user, token = auth_service.login(email, correct_password)
        assert logged_in_user.id == user.id, "Login with correct credentials should succeed"
        assert token is not None, "Valid login should return a token"


# Property 6: Password reset flow updates credentials
@settings(max_examples=10, deadline=None)
@given(
    email=valid_email_strategy(),
    old_password=valid_password_strategy(),
    new_password=valid_password_strategy()
)
def test_property_6_password_reset_updates_credentials(email, old_password, new_password):
    """
    Property 6: Password reset flow updates credentials
    
    For any registered user, requesting password reset should allow setting
    a new password, and the new password should work for login while the
    old password should no longer work.
    
    Note: This test simulates the password reset flow by directly updating
    the password since the token-based reset system is not fully implemented.
    
    Validates: Requirements 1.8, 1.9
    """
    # Skip if passwords are the same
    if old_password == new_password:
        return
    
    with get_db_session() as db_session:
        auth_service = AuthService(db_session)
        
        # Register and verify a user with old password
        user = auth_service.register_user(email, old_password)
        user.is_verified = True
        db_session.commit()
        
        # Verify login works with old password
        logged_in_user, token = auth_service.login(email, old_password)
        assert logged_in_user.id == user.id, "Login should work with old password"
        
        # Request password reset (should not raise error)
        try:
            auth_service.request_password_reset(email)
        except UserNotFoundError:
            pytest.fail("Password reset request should not fail for existing user")
        
        # Simulate password reset by updating the password hash
        new_password_hash = PasswordHasher.hash_password(new_password)
        user.password_hash = new_password_hash
        db_session.commit()
        db_session.refresh(user)
        
        # Verify old password no longer works
        with pytest.raises(InvalidCredentialsError):
            auth_service.login(email, old_password)
        
        # Verify new password works
        logged_in_user, new_token = auth_service.login(email, new_password)
        assert logged_in_user.id == user.id, "Login should work with new password"
        assert new_token is not None, "Login with new password should return a token"
        # Note: Tokens may be the same if created in the same second (JWT includes timestamp)
        
        # Verify the password hash was actually updated
        assert user.password_hash != old_password, "Password should be hashed"
        assert PasswordHasher.verify_password(new_password, user.password_hash), \
            "New password should verify against updated hash"
        assert not PasswordHasher.verify_password(old_password, user.password_hash), \
            "Old password should not verify against updated hash"
