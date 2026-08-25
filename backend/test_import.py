import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

print("Testing imports...")

try:
    from app.core.config import settings
    print(f"[OK] config - DATABASE_URL: {settings.DATABASE_URL}")
except Exception as e:
    print(f"[FAIL] config: {e}")
    sys.exit(1)

try:
    from app.core.database import engine, Base
    print("[OK] database")
except Exception as e:
    print(f"[FAIL] database: {e}")
    sys.exit(1)

try:
    from app.core.auth import create_access_token, get_current_user
    print("[OK] auth")
except Exception as e:
    print(f"[FAIL] auth: {e}")
    sys.exit(1)

try:
    from app.api.v1.training import router as training_router
    print("[OK] training router")
except Exception as e:
    print(f"[FAIL] training router: {e}")
    sys.exit(1)

try:
    from app.api.v1.auth import router as auth_router
    print("[OK] auth router")
except Exception as e:
    print(f"[FAIL] auth router: {e}")
    sys.exit(1)

try:
    from main import app
    print("[OK] main app")
except Exception as e:
    print(f"[FAIL] main app: {e}")
    sys.exit(1)

print("\n=== ALL IMPORTS OK ===")
