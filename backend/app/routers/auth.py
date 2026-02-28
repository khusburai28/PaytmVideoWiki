from fastapi import APIRouter, HTTPException, Depends
from datetime import datetime
import logging

from app.models.auth_schemas import (
    UserCreate, UserLogin, UserResponse, TokenResponse, Role
)
from app.middleware.auth import get_current_active_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auth", tags=["authentication"])


def get_auth_service():
    """Dependency to get auth service instance."""
    from app.main import auth_service
    return auth_service


@router.post("/register", response_model=TokenResponse)
async def register(user_data: UserCreate, auth_service=Depends(get_auth_service)):
    """Register a new user."""
    try:
        # Create user
        user_id = auth_service.create_user(
            email=user_data.email,
            password=user_data.password,
            full_name=user_data.full_name,
            role=user_data.role.value,
            team_id=user_data.team_id
        )

        # Get created user
        user = auth_service.get_user_by_id(user_id)

        # Create access token
        access_token = auth_service.create_access_token(
            user_id=user['user_id'],
            email=user['email'],
            role=user['role']
        )

        # Get team name if user has a team
        team_name = None
        if user.get('team_id'):
            team = auth_service.get_team_by_id(user['team_id'])
            if team:
                team_name = team.get('team_name')

        return TokenResponse(
            access_token=access_token,
            user=UserResponse(
                user_id=user['user_id'],
                email=user['email'],
                full_name=user['full_name'],
                role=Role(user['role']),
                team_id=user.get('team_id'),
                team_name=team_name,
                created_at=datetime.fromisoformat(user['created_at']),
                is_active=user.get('is_active', True)
            )
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Registration failed: {e}")
        raise HTTPException(status_code=500, detail="Registration failed")


@router.post("/login", response_model=TokenResponse)
async def login(credentials: UserLogin, auth_service=Depends(get_auth_service)):
    """Login user."""
    user = auth_service.authenticate_user(credentials.email, credentials.password)
    if not user:
        raise HTTPException(status_code=401, detail="Incorrect email or password")

    access_token = auth_service.create_access_token(
        user_id=user['user_id'],
        email=user['email'],
        role=user['role']
    )

    # Get team name if user has a team
    team_name = None
    if user.get('team_id'):
        team = auth_service.get_team_by_id(user['team_id'])
        if team:
            team_name = team.get('team_name')

    return TokenResponse(
        access_token=access_token,
        user=UserResponse(
            user_id=user['user_id'],
            email=user['email'],
            full_name=user['full_name'],
            role=Role(user['role']),
            team_id=user.get('team_id'),
            team_name=team_name,
            created_at=datetime.fromisoformat(user['created_at']),
            is_active=user.get('is_active', True)
        )
    )


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(current_user: dict = Depends(get_current_active_user), auth_service=Depends(get_auth_service)):
    """Get current authenticated user information."""
    # Get team name if user has a team
    team_name = None
    if current_user.get('team_id'):
        team = auth_service.get_team_by_id(current_user['team_id'])
        if team:
            team_name = team.get('team_name')

    return UserResponse(
        user_id=current_user['user_id'],
        email=current_user['email'],
        full_name=current_user['full_name'],
        role=Role(current_user['role']),
        team_id=current_user.get('team_id'),
        team_name=team_name,
        created_at=datetime.fromisoformat(current_user['created_at']),
        is_active=current_user.get('is_active', True)
    )
