from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Optional, Dict
import logging

logger = logging.getLogger(__name__)

# Security scheme
security = HTTPBearer()


def get_auth_service():
    """Dependency to get auth service."""
    from app.main import auth_service
    return auth_service


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    auth_service = Depends(get_auth_service)
) -> Dict:
    """Get current authenticated user from JWT token."""
    token = credentials.credentials

    # Verify token
    payload = auth_service.verify_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Get user from database
    user = auth_service.get_user_by_id(payload['user_id'])
    if not user or not user.get('is_active', False):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
        )

    return user


async def get_current_active_user(
    current_user: Dict = Depends(get_current_user)
) -> Dict:
    """Get current active user."""
    if not current_user.get('is_active', False):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inactive user"
        )
    return current_user


def require_role(required_roles: list):
    """Dependency to check if user has required role."""
    async def check_role(current_user: Dict = Depends(get_current_active_user)):
        user_role = current_user.get('role')
        if user_role not in required_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Insufficient permissions. Required roles: {required_roles}"
            )
        return current_user
    return check_role


# Role-based dependencies
async def require_admin(current_user: Dict = Depends(get_current_active_user)):
    """Require admin role."""
    if current_user.get('role') != 'admin':
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    return current_user


async def require_team_lead_or_admin(current_user: Dict = Depends(get_current_active_user)):
    """Require team lead or admin role."""
    role = current_user.get('role')
    if role not in ['admin', 'team_lead']:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Team lead or admin access required"
        )
    return current_user


def check_video_permission(video_metadata: Dict, current_user: Dict) -> bool:
    """Check if user has permission to modify/delete video."""
    user_role = current_user.get('role')
    user_id = current_user.get('user_id')
    author_id = video_metadata.get('author_id')

    # Admin can do anything
    if user_role == 'admin':
        return True

    # Team lead can manage team videos
    if user_role == 'team_lead':
        user_team = current_user.get('team_id')
        video_team = video_metadata.get('team_id')
        if user_team == video_team:
            return True

    # Author can manage their own videos
    if author_id == user_id:
        return True

    return False
