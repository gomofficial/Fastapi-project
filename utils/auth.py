from datetime import datetime, timedelta
from typing import Annotated
import jwt
from fastapi import Depends, status
from fastapi.exceptions import HTTPException
from schema.jwt import JWTPayload, JWTResponsePayload
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError
from settings import settings
from sqlalchemy import select
from db.models import User
from db.engine import SessionLocal
from .redis_utils import token_whitelist, verify_device

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/account/token")

class JWTHandler:
    @staticmethod
    def generate(username: str, exp_timestamp: int | None = None) -> JWTResponsePayload:
        expire_time = int(settings.ACCESS_TOKEN_EXPIRE_MINUTES)

        secret_key = settings.SECRET_KEY

        expires_delta = datetime.utcnow() + timedelta(minutes=expire_time)

        to_encode = {
            "exp": exp_timestamp if exp_timestamp else expires_delta,
            "username": username,
        }
        encoded_jwt = jwt.encode(to_encode, secret_key, settings.ALGORITHM)
        return encoded_jwt

    @staticmethod
    async def verify_token(auth_token: Annotated[str, Depends(oauth2_scheme)]) -> JWTPayload:
        jwt_token = auth_token
        credentials_exception = HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
        if not jwt_token:
            raise credentials_exception
        try:
            token_data = jwt.decode(jwt_token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
            if datetime.fromtimestamp(token_data["exp"])+timedelta(days=1) < datetime.now():
                raise credentials_exception
            username: str = token_data.get("username")
            if username is None:
                raise credentials_exception
        except jwt.exceptions.PyJWTError as e:
            print(e)
            raise credentials_exception
        except JWTError as e:
            print(e)
            raise credentials_exception
        await token_whitelist(username)
        await verify_device(jwt_token,username)
        stmt = select(User).where(User.username==username)
        async with SessionLocal() as session:
            user = (await session.execute(stmt)).scalars().first()

        if user is None:
            raise credentials_exception

        return JWTPayload(**token_data)