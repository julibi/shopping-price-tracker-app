"""Change price column type to float

Revision ID: 66593fc49f84
Revises: 11ec5dfd54b6
Create Date: 2024-09-12 10:33:13.017702

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '66593fc49f84'
down_revision: Union[str, None] = '11ec5dfd54b6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Define the new schema with FLOAT type
def upgrade():
    # Step 1: Create a new table with the updated schema
    op.create_table(
        'items_new',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('url', sa.String, unique=True),
        sa.Column('product_name', sa.String, unique=True),
        sa.Column('price', sa.Float, index=True),  # Updated column type
        sa.Column('currency', sa.String, index=True),
        sa.Column('last_updated', sa.DateTime, default=sa.func.now(), nullable=False)
    )

    # Step 2: Copy data from the old table to the new table
    op.execute(
        """
        INSERT INTO items_new (id, url, product_name, price, currency, last_updated)
        SELECT id, url, product_name, CAST(price AS FLOAT), currency, last_updated FROM items
        """
    )

    # Step 3: Drop the old table
    op.drop_table('items')

    # Step 4: Rename the new table to the old table's name
    op.rename_table('items_new', 'items')

def downgrade():
    # Define the downgrade steps if needed
    pass
