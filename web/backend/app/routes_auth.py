"""Authentication routes: register, login, session check."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from . import auth
from .deps import require_user

router = APIRouter(prefix="/api/auth", tags=["auth"])


class RegisterPayload(BaseModel):

    email: str
    password: str


class LoginPayload(BaseModel):

    email: str
    password: str


@router.post("/register", status_code=201)
def register(payload: RegisterPayload):

    try:

        user = auth.register(payload.email, payload.password)

    except auth.AuthError as error:

        raise HTTPException(
            status_code=error.status,
            detail=str(error)
        )

    token, expires_in = auth.create_token(user["email"])

    return {
        "token": token,
        "email": user["email"],
        "expires_in": expires_in
    }


@router.post("/login")
def login(payload: LoginPayload):

    try:

        user = auth.authenticate(payload.email, payload.password)

    except auth.AuthError as error:

        raise HTTPException(
            status_code=error.status,
            detail=str(error)
        )

    token, expires_in = auth.create_token(user["email"])

    return {
        "token": token,
        "email": user["email"],
        "expires_in": expires_in
    }


@router.get("/me")
def me(operator: str = Depends(require_user)):

    return {"email": operator}
