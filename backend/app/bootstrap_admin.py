
from sqlalchemy import select

from app.config import settings
from app.core.security import hash_password
from app.database import SessionLocal
from app.models.user import User


def bootstrap_admin() -> None:
    email = (settings.initial_admin_email or "").strip().lower()
    password = settings.initial_admin_password

    if not email or not password:
        raise RuntimeError(
            "INITIAL_ADMIN_EMAIL and INITIAL_ADMIN_PASSWORD "
            "must be configured in .env"
        )

    if len(password) < 16:
        raise RuntimeError(
            "Initial administrator password must contain "
            "at least 16 characters."
        )

    with SessionLocal() as db:
        try:
            # Refuse to create another administrator.
            existing_admin = db.scalar(
                select(User.id)
                .where(User.role == "administrator")
                .limit(1)
            )

            if existing_admin is not None:
                raise RuntimeError(
                    "An administrator already exists. "
                    "Bootstrap refused."
                )

            # Never overwrite or promote an existing account.
            existing_user = db.scalar(
                select(User.id)
                .where(User.email == email)
            )

            if existing_user is not None:
                raise RuntimeError(
                    "An account with the configured admin email "
                    "already exists. Bootstrap refused."
                )

            admin = User(
                email=email,
                password_hash=hash_password(password),
                first_name=settings.initial_admin_first_name,
                last_name=settings.initial_admin_last_name,
                role="administrator",
                is_active=True,
                is_email_verified=False,
            )

            db.add(admin)
            db.commit()

            print("Initial administrator created successfully.")
            print(f"Administrator email: {email}")
            print("Role: administrator")
            print("Account active: True")

        except Exception:
            db.rollback()
            raise


if __name__ == "__main__":
    bootstrap_admin()
