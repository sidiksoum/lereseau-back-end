"""add_otp_codes_table_and_isEmailVerified

Revision ID: 7e4fe7e4bbfa
Revises: 075c8d95a145
Create Date: 2026-04-28 08:56:56.891799

"""
from typing import Sequence, Union
from alembic import op
# pyrefly: ignore [missing-import]
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7e4fe7e4bbfa'
down_revision: Union[str, Sequence[str], None] = '075c8d95a145'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""

    # 1. Ajouter isEmailVerified avec server_default pour les lignes existantes
    #    (les anciens comptes sont considérés vérifiés : server_default='true')
    op.add_column(
        'users',
        sa.Column(
            'isEmailVerified',
            sa.Boolean(),
            nullable=False,
            server_default=sa.text('true'),
        ),
    )

    # 2. Créer la table otp_codes
    op.create_table(
        'otp_codes',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('email', sa.String(), nullable=False),
        sa.Column('code', sa.String(), nullable=False),
        sa.Column(
            'purpose',
            sa.Enum('EMAIL_VERIFICATION', 'PASSWORD_RESET', name='otppurposeenum'),
            nullable=False,
        ),
        sa.Column('is_used', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_otp_codes_id', 'otp_codes', ['id'], unique=False)
    op.create_index('ix_otp_codes_email', 'otp_codes', ['email'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_otp_codes_email', table_name='otp_codes')
    op.drop_index('ix_otp_codes_id', table_name='otp_codes')
    op.drop_table('otp_codes')
    op.drop_column('users', 'isEmailVerified')
    # Supprimer l'enum PostgreSQL
    sa.Enum(name='otppurposeenum').drop(op.get_bind(), checkfirst=True)
