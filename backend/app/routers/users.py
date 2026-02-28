from fastapi import APIRouter, HTTPException, Depends
import logging

from app.middleware.auth import require_admin

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/users", tags=["users"])


def get_auth_service():
    """Dependency to get auth service instance."""
    from app.main import auth_service
    return auth_service


@router.get("")
async def get_all_users(current_user: dict = Depends(require_admin), auth_service=Depends(get_auth_service)):
    """Get all users (Admin only)."""
    try:
        users = auth_service.get_all_users()
        return users
    except Exception as e:
        logger.error(f"Failed to get users: {e}")
        raise HTTPException(status_code=500, detail="Failed to get users")
