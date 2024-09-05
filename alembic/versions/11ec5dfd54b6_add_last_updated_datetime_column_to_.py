"""add last_updated datetime column to Item table

Revision ID: 11ec5dfd54b6
Revises: 
Create Date: 2024-09-05 15:32:59.041646

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = '11ec5dfd54b6'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('items', sa.Column('last_updated', sa.DateTime(), nullable=True))
    # ### end Alembic commands ###

def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('items', 'last_updated')
    # ### end Alembic commands ###
