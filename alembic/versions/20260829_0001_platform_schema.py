"""Initial product platform schema.

Revision ID: 20260829_0001
"""
from alembic import op
from shopilot.infra.models import Base

revision = "20260829_0001"
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    Base.metadata.create_all(bind=op.get_bind())

def downgrade():
    Base.metadata.drop_all(bind=op.get_bind())
