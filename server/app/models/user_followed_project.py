import uuid
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from app.extensions import db


class UserFollowedProject(db.Model):
    __tablename__ = 'user_followed_projects'

    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = db.Column(
        UUID(as_uuid=True),
        db.ForeignKey('users.id', ondelete='CASCADE'),
        nullable=False,
        index=True,
    )
    project_id = db.Column(
        UUID(as_uuid=True),
        db.ForeignKey('new_projects.id', ondelete='CASCADE'),
        nullable=False,
        index=True,
    )
    followed_at = db.Column(db.DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        db.UniqueConstraint('user_id', 'project_id', name='uq_user_followed_project'),
    )

    def __repr__(self):
        return f"<UserFollowedProject user={self.user_id} project={self.project_id}>"
