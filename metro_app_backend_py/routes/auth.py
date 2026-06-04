"""认证路由 — 注册、登录、获取用户信息。"""

import bcrypt
from fastapi import APIRouter, Depends, HTTPException, status
from models.user import RegisterRequest, LoginRequest, UserResponse, create_user, find_user_by_phone
from middleware.auth import create_token, get_current_user

router = APIRouter(prefix="/api/auth", tags=["认证"])


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(body: RegisterRequest):
    hashed = bcrypt.hashpw(body.password.encode("utf-8"), bcrypt.gensalt())
    user = await create_user(body.phone, hashed.decode("utf-8"), body.nickname)
    if user is None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="手机号已注册")
    return UserResponse(phone=user["phone"], nickname=user["nickname"], created_at=user["created_at"])


@router.post("/login")
async def login(body: LoginRequest):
    user = await find_user_by_phone(body.phone)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="手机号或密码错误")
    if not bcrypt.checkpw(body.password.encode("utf-8"), user["hashed_password"].encode("utf-8")):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="手机号或密码错误")
    token = create_token(body.phone)
    return {"token": token, "user": {"phone": user["phone"], "nickname": user["nickname"]}}


@router.get("/me", response_model=UserResponse)
async def get_me(phone: str = Depends(get_current_user)):
    user = await find_user_by_phone(phone)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="用户不存在")
    return UserResponse(phone=user["phone"], nickname=user["nickname"], created_at=user["created_at"])
