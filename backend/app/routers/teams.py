from fastapi import APIRouter, HTTPException, Depends
from datetime import datetime
from qdrant_client.models import PointStruct
import logging

from app.models.auth_schemas import (
    TeamCreate, TeamResponse, AddTeamMemberRequest, AssignUserToTeamRequest,
    UserResponse, TeamMemberResponse, Role
)
from app.middleware.auth import (
    get_current_active_user, require_admin, require_team_lead_or_admin
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/teams", tags=["teams"])


def get_auth_service():
    """Dependency to get auth service instance."""
    from app.main import auth_service
    return auth_service


@router.post("", response_model=TeamResponse)
async def create_team(
    team_data: TeamCreate,
    current_user: dict = Depends(require_admin),
    auth_service=Depends(get_auth_service)
):
    """Create a new team (Admin only)."""
    try:
        team_id = auth_service.create_team(
            team_name=team_data.team_name,
            description=team_data.description,
            created_by=current_user['user_id']
        )

        team = auth_service.get_team_by_id(team_id)
        members = auth_service.get_team_members(team_id)

        return TeamResponse(
            team_id=team['team_id'],
            team_name=team['team_name'],
            description=team.get('description'),
            created_by=team['created_by'],
            created_at=datetime.fromisoformat(team['created_at']),
            member_count=len(members)
        )

    except Exception as e:
        logger.error(f"Failed to create team: {e}")
        raise HTTPException(status_code=500, detail="Failed to create team")


@router.post("/{team_id}/members", response_model=UserResponse)
async def add_team_member(
    team_id: str,
    member_data: AddTeamMemberRequest,
    current_user: dict = Depends(require_team_lead_or_admin),
    auth_service=Depends(get_auth_service)
):
    """Add a member to team (Team Lead or Admin)."""
    try:
        # Verify team exists
        team = auth_service.get_team_by_id(team_id)
        if not team:
            raise HTTPException(status_code=404, detail="Team not found")

        # If team lead, verify they belong to this team
        if current_user['role'] == 'team_lead':
            if current_user.get('team_id') != team_id:
                raise HTTPException(
                    status_code=403,
                    detail="Team leads can only add members to their own team"
                )

        # Create user and add to team
        user_id = auth_service.create_user(
            email=member_data.email,
            password=member_data.password,
            full_name=member_data.full_name,
            role=member_data.role.value,
            team_id=team_id
        )

        user = auth_service.get_user_by_id(user_id)

        return UserResponse(
            user_id=user['user_id'],
            email=user['email'],
            full_name=user['full_name'],
            role=Role(user['role']),
            team_id=user.get('team_id'),
            team_name=team['team_name'],
            created_at=datetime.fromisoformat(user['created_at']),
            is_active=user.get('is_active', True)
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to add team member: {e}")
        raise HTTPException(status_code=500, detail="Failed to add team member")


@router.put("/{team_id}/assign", response_model=UserResponse)
async def assign_user_to_team(
    team_id: str,
    assign_data: AssignUserToTeamRequest,
    current_user: dict = Depends(require_team_lead_or_admin),
    auth_service=Depends(get_auth_service)
):
    """Assign existing user to team (Team Lead or Admin)."""
    try:
        # Verify team exists
        team = auth_service.get_team_by_id(team_id)
        if not team:
            raise HTTPException(status_code=404, detail="Team not found")

        # If team lead, verify they belong to this team
        if current_user['role'] == 'team_lead':
            if current_user.get('team_id') != team_id:
                raise HTTPException(
                    status_code=403,
                    detail="Team leads can only assign members to their own team"
                )

        # Get user
        user = auth_service.get_user_by_id(assign_data.user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        # Update user's team and role
        user['team_id'] = team_id
        user['role'] = assign_data.role.value

        # Update in Qdrant
        auth_service.qdrant_client.upsert(
            collection_name=auth_service.users_collection,
            points=[PointStruct(id=assign_data.user_id, vector=[0.0], payload=user)]
        )

        logger.info(f"Assigned user {assign_data.user_id} to team {team_id} with role {assign_data.role.value}")

        return UserResponse(
            user_id=user['user_id'],
            email=user['email'],
            full_name=user['full_name'],
            role=Role(user['role']),
            team_id=user.get('team_id'),
            team_name=team['team_name'],
            created_at=datetime.fromisoformat(user['created_at']),
            is_active=user.get('is_active', True)
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to assign user to team: {e}")
        raise HTTPException(status_code=500, detail="Failed to assign user to team")


@router.get("")
async def get_all_teams(
    current_user: dict = Depends(get_current_active_user),
    auth_service=Depends(get_auth_service)
):
    """Get all teams with their members."""
    try:
        teams = auth_service.get_all_teams()

        # Format teams with members
        result = []
        for team in teams:
            members = auth_service.get_team_members(team['team_id'])
            result.append({
                **team,
                'members': members
            })

        return result
    except Exception as e:
        logger.error(f"Failed to get teams: {e}")
        raise HTTPException(status_code=500, detail="Failed to get teams")


@router.get("/{team_id}/members", response_model=list[TeamMemberResponse])
async def get_team_members(
    team_id: str,
    current_user: dict = Depends(get_current_active_user),
    auth_service=Depends(get_auth_service)
):
    """Get all members of a specific team."""
    try:
        team = auth_service.get_team_by_id(team_id)
        if not team:
            raise HTTPException(status_code=404, detail="Team not found")

        members = auth_service.get_team_members(team_id)

        return [
            TeamMemberResponse(
                user_id=member['user_id'],
                email=member['email'],
                full_name=member['full_name'],
                role=Role(member['role']),
                joined_at=datetime.fromisoformat(member['created_at'])
            )
            for member in members
        ]

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get team members: {e}")
        raise HTTPException(status_code=500, detail="Failed to get team members")
