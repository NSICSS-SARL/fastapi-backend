import fastapi as _fastapi
import fastapi.security as _security
import jwt as _jwt
import datetime as _dt
import sqlalchemy.orm as _orm
import passlib.hash as _hash

import app.database as _database
import app.models as _models
import app.schemas as _schemas
from app.config import Configs

oauth2schema = _security.OAuth2PasswordBearer(tokenUrl="/api/token")

JWT_SECRET = Configs.JWT_SECRET


def create_database():
    return _database.Base.metadata.create_all(bind=_database.engine)


def get_db():
    db = _database.SessionLocal()
    try:
        yield db
    finally:
        db.close()


def close_db():
    db = _database.SessionLocal()
    if db is not None:
        db.close()


async def get_user_by_email(email: str, db: _orm.Session):
    return db.query(_models.User).filter(_models.User.email == email).first()

async def get_lead_by_email(email: str, db: _orm.Session):
    return db.query(_models.Lead).filter(_models.Lead.email == email).first()


async def create_user(user: _schemas.UserCreate, db: _orm.Session):
    user_obj = _models.User(email=user.email, hashed_password=_hash.bcrypt.hash(user.hashed_password),
                            
                            )
    db.add(user_obj)
    db.commit()
    db.refresh(user_obj)    
    lead_obj = _models.Lead(owner_id = user_obj.id, first_name=user.first_name, last_name=user.last_name,email=user.email)
    db.add(lead_obj)
    db.commit()
    db.refresh(lead_obj)
    return user_obj


async def authenticate_user(email: str, password: str, db: _orm.Session):
    user = await get_user_by_email(db=db, email=email)

    if not user:
        return False

    if not user.verify_password(password):
        return False

    return user


async def create_token(user: _models.User, db: _orm.Session):    
    user_obj = _schemas.User.from_orm(user)    
    token = _jwt.encode(user_obj.dict(), JWT_SECRET)
    user = db.query(_models.User).get(user_obj.id)   
    db.commit()
    return dict(access_token=token, token_type="bearer")


async def get_current_user(db: _orm.Session = _fastapi.Depends(get_db), token: str = _fastapi.Depends(oauth2schema),
                           ):
    try:
        payload = _jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
        user = db.query(_models.User).get(payload["id"])
    except:
        raise _fastapi.HTTPException(
            status_code=401, detail="Invalid Email or Password"
        )

    return _schemas.User.from_orm(user)


async def parse_user(token: str, db: _orm.Session = _fastapi.Depends(get_db), ):
    try:
        payload = _jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
        user = db.query(_models.User).get(payload["id"])
    except:
        raise _fastapi.HTTPException(
            status_code=401, detail="Invalid Email or Password"
        )
    return _schemas.User.from_orm(user)


async def create_lead(user: _schemas.User, db: _orm.Session, lead: _schemas.LeadCreate):
    lead = _models.Lead(**lead.dict(), owner_id=user.id)
    db.add(lead)
    db.commit()
    db.refresh(lead)
    return _schemas.Lead.from_orm(lead)


async def get_leads(user: _schemas.User, db: _orm.Session):
    leads = db.query(_models.Lead).filter_by(owner_id=user.id)

    return list(map(_schemas.Lead.from_orm, leads))


async def _lead_selector(lead_id: int, user: _schemas.User, db: _orm.Session):
    lead = (
        db.query(_models.Lead)
            .filter_by(owner_id=user.id)
            .filter(_models.Lead.id == lead_id)
            .first()
    )

    if lead is None:
        raise _fastapi.HTTPException(status_code=404, detail="Lead does not exist")

    return lead


async def get_lead(lead_id: int, user: _schemas.User, db: _orm.Session):
    lead = await _lead_selector(lead_id=lead_id, user=user, db=db)

    return _schemas.Lead.from_orm(lead)


async def delete_lead(lead_id: int, user: _schemas.User, db: _orm.Session):
    lead = await _lead_selector(lead_id, user, db)

    db.delete(lead)
    db.commit()


async def update_lead(lead_id: int, lead: _schemas.LeadCreate, user: _schemas.User, db: _orm.Session):
    lead_db = await _lead_selector(lead_id, user, db)

    lead_db.first_name = lead.first_name
    lead_db.last_name = lead.last_name
    lead_db.email = lead.email
    lead_db.company = lead.company
    lead_db.note = lead.note
    lead_db.date_last_updated = _dt.datetime.utcnow()

    db.commit()
    db.refresh(lead_db)

    return _schemas.Lead.from_orm(lead_db)
