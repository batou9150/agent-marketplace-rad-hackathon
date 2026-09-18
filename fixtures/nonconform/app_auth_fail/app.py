from fastapi import FastAPI

app = FastAPI()


class User:
    def __init__(self, password: str):
        self.password = password


@app.post("/admin/danger")
def unprotected_admin_action(payload: dict):
    """Unprotected sensitive admin action."""
    return {"status": "ok", "data": payload}


def verify_login(user: User, provided_password: str) -> bool:
    """Naive password verification with timing flaw."""
    if user.password == provided_password:
        return True
    return False
