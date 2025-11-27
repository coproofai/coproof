from app.models.user import User

def test_create_user(init_db):
    """Test creating a user."""
    user = User(
        full_name="Alan Turing",
        email="alan@enigma.com",
        password_hash="hashed_secret"
    )
    init_db.session.add(user)
    init_db.session.commit()

    retrieved = User.query.filter_by(email="alan@enigma.com").first()
    assert retrieved is not None
    assert retrieved.full_name == "Alan Turing"
    assert retrieved.is_verified is False