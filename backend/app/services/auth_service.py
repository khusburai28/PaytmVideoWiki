import bcrypt
import jwt
import uuid
from datetime import datetime, timedelta
from typing import Optional, Dict
from qdrant_client import QdrantClient
from qdrant_client.models import VectorParams, Distance, PointStruct, Filter, FieldCondition, MatchValue
import logging

logger = logging.getLogger(__name__)


class AuthService:
    def __init__(
        self,
        qdrant_client: QdrantClient,
        secret_key: str,
        users_collection: str = "users",
        teams_collection: str = "teams"
    ):
        """Initialize authentication service."""
        self.qdrant_client = qdrant_client
        self.secret_key = secret_key
        self.users_collection = users_collection
        self.teams_collection = teams_collection
        self.algorithm = "HS256"
        self.access_token_expire_minutes = 60 * 24 * 7  # 7 days

        # Create collections if they don't exist
        self._ensure_collections_exist()

    def _ensure_collections_exist(self):
        """Create user and team collections if they don't exist."""
        try:
            collections = self.qdrant_client.get_collections().collections
            collection_names = [col.name for col in collections]

            # Create users collection
            if self.users_collection not in collection_names:
                logger.info(f"Creating collection: {self.users_collection}")
                self.qdrant_client.create_collection(
                    collection_name=self.users_collection,
                    vectors_config=VectorParams(size=1, distance=Distance.COSINE)
                )
                # Create default admin user
                self._create_default_admin()

            # Create teams collection
            if self.teams_collection not in collection_names:
                logger.info(f"Creating collection: {self.teams_collection}")
                self.qdrant_client.create_collection(
                    collection_name=self.teams_collection,
                    vectors_config=VectorParams(size=1, distance=Distance.COSINE)
                )

        except Exception as e:
            logger.error(f"Failed to create auth collections: {e}")
            raise

    def _create_default_admin(self):
        """Create default admin user if no users exist."""
        try:
            # Default admin credentials
            admin_email = "admin@example.com"
            admin_password = "Admin@123456"

            admin_id = str(uuid.uuid4())
            hashed_password = self.hash_password(admin_password)

            admin_user = PointStruct(
                id=admin_id,
                vector=[0.0],
                payload={
                    "user_id": admin_id,
                    "email": admin_email,
                    "full_name": "System Admin",
                    "password_hash": hashed_password,
                    "role": "admin",
                    "team_id": None,
                    "created_at": datetime.now().isoformat(),
                    "is_active": True
                }
            )

            self.qdrant_client.upsert(
                collection_name=self.users_collection,
                points=[admin_user]
            )
            logger.info(f"Created default admin user: {admin_email} / {admin_password}")

        except Exception as e:
            logger.error(f"Failed to create default admin: {e}")

    def hash_password(self, password: str) -> str:
        """Hash password using bcrypt."""
        salt = bcrypt.gensalt(rounds=12)
        hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
        return hashed.decode('utf-8')

    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """Verify password against hash."""
        return bcrypt.checkpw(
            plain_password.encode('utf-8'),
            hashed_password.encode('utf-8')
        )

    def create_access_token(self, user_id: str, email: str, role: str) -> str:
        """Create JWT access token."""
        expire = datetime.utcnow() + timedelta(minutes=self.access_token_expire_minutes)
        payload = {
            "user_id": user_id,
            "email": email,
            "role": role,
            "exp": expire
        }
        token = jwt.encode(payload, self.secret_key, algorithm=self.algorithm)
        return token

    def verify_token(self, token: str) -> Optional[Dict]:
        """Verify JWT token and return payload."""
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
            return payload
        except jwt.ExpiredSignatureError:
            logger.warning("Token has expired")
            return None
        except jwt.InvalidTokenError:
            logger.warning("Invalid token")
            return None

    def get_user_by_email(self, email: str) -> Optional[Dict]:
        """Get user by email."""
        try:
            results, _ = self.qdrant_client.scroll(
                collection_name=self.users_collection,
                scroll_filter=Filter(
                    must=[
                        FieldCondition(key="email", match=MatchValue(value=email))
                    ]
                ),
                limit=1,
                with_payload=True,
                with_vectors=False
            )

            if results:
                return results[0].payload
            return None

        except Exception as e:
            logger.error(f"Failed to get user by email: {e}")
            return None

    def get_user_by_id(self, user_id: str) -> Optional[Dict]:
        """Get user by ID."""
        try:
            result = self.qdrant_client.retrieve(
                collection_name=self.users_collection,
                ids=[user_id],
                with_payload=True,
                with_vectors=False
            )

            if result:
                return result[0].payload
            return None

        except Exception as e:
            logger.error(f"Failed to get user by ID: {e}")
            return None

    def create_user(
        self,
        email: str,
        password: str,
        full_name: str,
        role: str = "employee",
        team_id: Optional[str] = None
    ) -> str:
        """Create new user."""
        try:
            # Check if user already exists
            existing_user = self.get_user_by_email(email)
            if existing_user:
                raise ValueError("User with this email already exists")

            user_id = str(uuid.uuid4())
            hashed_password = self.hash_password(password)

            user = PointStruct(
                id=user_id,
                vector=[0.0],
                payload={
                    "user_id": user_id,
                    "email": email,
                    "full_name": full_name,
                    "password_hash": hashed_password,
                    "role": role,
                    "team_id": team_id,
                    "created_at": datetime.now().isoformat(),
                    "is_active": True
                }
            )

            self.qdrant_client.upsert(
                collection_name=self.users_collection,
                points=[user]
            )

            logger.info(f"Created user: {email}")
            return user_id

        except Exception as e:
            logger.error(f"Failed to create user: {e}")
            raise

    def authenticate_user(self, email: str, password: str) -> Optional[Dict]:
        """Authenticate user with email and password."""
        user = self.get_user_by_email(email)

        if not user:
            return None

        if not user.get('is_active', False):
            logger.warning(f"Inactive user attempted login: {email}")
            return None

        if not self.verify_password(password, user['password_hash']):
            return None

        return user

    def create_team(self, team_name: str, created_by: str, description: Optional[str] = None) -> str:
        """Create new team."""
        try:
            team_id = str(uuid.uuid4())

            team = PointStruct(
                id=team_id,
                vector=[0.0],
                payload={
                    "team_id": team_id,
                    "team_name": team_name,
                    "description": description,
                    "created_by": created_by,
                    "created_at": datetime.now().isoformat(),
                    "is_active": True
                }
            )

            self.qdrant_client.upsert(
                collection_name=self.teams_collection,
                points=[team]
            )

            logger.info(f"Created team: {team_name}")
            return team_id

        except Exception as e:
            logger.error(f"Failed to create team: {e}")
            raise

    def get_team_by_id(self, team_id: str) -> Optional[Dict]:
        """Get team by ID."""
        try:
            result = self.qdrant_client.retrieve(
                collection_name=self.teams_collection,
                ids=[team_id],
                with_payload=True,
                with_vectors=False
            )

            if result:
                return result[0].payload
            return None

        except Exception as e:
            logger.error(f"Failed to get team: {e}")
            return None

    def get_team_members(self, team_id: str) -> list:
        """Get all members of a team."""
        try:
            results, _ = self.qdrant_client.scroll(
                collection_name=self.users_collection,
                scroll_filter=Filter(
                    must=[
                        FieldCondition(key="team_id", match=MatchValue(value=team_id)),
                        FieldCondition(key="is_active", match=MatchValue(value=True))
                    ]
                ),
                limit=1000,
                with_payload=True,
                with_vectors=False
            )

            return [r.payload for r in results]

        except Exception as e:
            logger.error(f"Failed to get team members: {e}")
            return []

    def add_user_to_team(self, user_id: str, team_id: str):
        """Add user to a team."""
        try:
            user = self.get_user_by_id(user_id)
            if not user:
                raise ValueError("User not found")

            # Update user's team_id
            user['team_id'] = team_id

            self.qdrant_client.upsert(
                collection_name=self.users_collection,
                points=[PointStruct(id=user_id, vector=[0.0], payload=user)]
            )

            logger.info(f"Added user {user_id} to team {team_id}")

        except Exception as e:
            logger.error(f"Failed to add user to team: {e}")
            raise

    def get_all_teams(self) -> list:
        """Get all teams."""
        try:
            results, _ = self.qdrant_client.scroll(
                collection_name=self.teams_collection,
                scroll_filter=Filter(
                    must=[
                        FieldCondition(key="is_active", match=MatchValue(value=True))
                    ]
                ),
                limit=1000,
                with_payload=True,
                with_vectors=False
            )

            return [r.payload for r in results]

        except Exception as e:
            logger.error(f"Failed to get all teams: {e}")
            return []

    def get_all_users(self) -> list:
        """Get all users."""
        try:
            results, _ = self.qdrant_client.scroll(
                collection_name=self.users_collection,
                scroll_filter=Filter(
                    must=[
                        FieldCondition(key="is_active", match=MatchValue(value=True))
                    ]
                ),
                limit=1000,
                with_payload=True,
                with_vectors=False
            )

            # Remove password hash from results for security
            users = []
            for r in results:
                user_data = r.payload.copy()
                user_data.pop('password_hash', None)
                users.append(user_data)

            return users

        except Exception as e:
            logger.error(f"Failed to get all users: {e}")
            return []
