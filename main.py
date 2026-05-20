from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from jose import jwt
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
import json

from database import SessionLocal, engine
from models import Base, User, Score, ActivityLog
from schemas import RegisterSchema, LoginSchema, ScoreSchema, AdminUserSchema
from auth import hash_password, verify_password


app = FastAPI(title="Maze Knight API")

SECRET_KEY = "maze_knight_ultra_secret_key"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60

security = HTTPBearer()

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
    "http://127.0.0.1:51264",
    "http://localhost:51264",
    "http://127.0.0.1:5500",
    "http://localhost:5500",
    "http://192.168.1.17:5500",
    "https://staging.d3v1t5u20qbnoh.amplifyapp.com"
],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

Base.metadata.create_all(bind=engine)

def create_default_admin():
    db = SessionLocal()

    try:
        admin_user = db.query(User).filter(
            User.username == "admin"
        ).first()

        if not admin_user:
            new_admin = User(
                username="admin",
                password_hash=hash_password("admin123"),
                is_admin=1,
                is_banned=0
            )

            db.add(new_admin)
            db.commit()

    finally:
        db.close()


create_default_admin()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def create_access_token(data: dict):
    to_encode = data.copy()

    expire = datetime.utcnow() + timedelta(
        minutes=ACCESS_TOKEN_EXPIRE_MINUTES
    )

    to_encode.update({"exp": expire})

    encoded_jwt = jwt.encode(
        to_encode,
        SECRET_KEY,
        algorithm=ALGORITHM
    )

    return encoded_jwt


def verify_admin_token(
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    token = credentials.credentials

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])

        if payload.get("is_admin") != 1:
            raise HTTPException(
                status_code=403,
                detail="Admin access required"
            )

        return payload

    except:
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired token"
        )


def add_activity_log(
    db: Session,
    action: str,
    username: str = "admin"
):
    log = ActivityLog(
        action=action,
        username=username
    )

    db.add(log)
    db.commit()


@app.get("/")
def root():
    return {
        "message": "Maze Knight Backend Running"
    }


@app.post("/api/v1/auth/register")
def register(
    data: RegisterSchema,
    db: Session = Depends(get_db)
):
    existing_user = db.query(User).filter(
        User.username == data.username
    ).first()

    if existing_user:
        raise HTTPException(
            status_code=400,
            detail="Username already exists"
        )

    new_user = User(
        username=data.username,
        password_hash=hash_password(data.password)
    )

    db.add(new_user)
    db.commit()

    add_activity_log(
        db,
        f"Registered new player: {data.username}",
        data.username
    )

    return {
        "message": "Registration successful"
    }

@app.post("/api/v1/auth/login")
def login(
    data: LoginSchema,
    db: Session = Depends(get_db)
):
    user = db.query(User).filter(
        User.username == data.username
    ).first()

    if not user or not verify_password(data.password, user.password_hash):
        raise HTTPException(
            status_code=401,
            detail="Invalid username or password"
        )

    if user.is_banned == 1:
        add_activity_log(
            db,
            f"Banned login attempt: {user.username}",
            user.username
        )

        raise HTTPException(
            status_code=403,
            detail="This account has been banned"
        )

    add_activity_log(
        db,
        f"Player logged in: {user.username}",
        user.username
    )

    token = create_access_token({
        "sub": user.username,
        "is_admin": user.is_admin
    })

    return {
        "message": "Login success",
        "username": user.username,
        "is_admin": user.is_admin,
        "access_token": token,
        "token_type": "bearer"
    }
@app.post("/api/v1/scores/save")
async def save_score(
    request: Request,
    db: Session = Depends(get_db)
):
    raw_body = await request.body()

    try:
        data = await request.json()
    except:
        data = json.loads(raw_body.decode("utf-8"))

    username = data.get("username")
    level_id = int(data.get("level_id"))
    clear_time = float(data.get("clear_time"))
    sanity_left = float(data.get("sanity_left"))
    pulses_used = int(float(data.get("pulses_used")))

    final_score = round(
        clear_time + (pulses_used * 30) + ((100 - sanity_left) * 2),
        2
    )

    new_score = Score(
        username=username,
        level_id=level_id,
        clear_time=clear_time,
        sanity_left=sanity_left,
        pulses_used=pulses_used,
        final_score=final_score
    )

    db.add(new_score)
    db.commit()

    add_activity_log(
    db,
    f"Score saved by {username} on Level {level_id} | Score: {final_score}",
    username
)

    return {
        "message": "Score saved",
        "final_score": final_score
    }


@app.get("/api/v1/leaderboard/{level_id}")
def leaderboard(
    level_id: int,
    db: Session = Depends(get_db)
):
    scores = db.query(Score)\
        .filter(Score.level_id == level_id)\
        .order_by(Score.final_score.asc())\
        .limit(20)\
        .all()

    return scores


@app.get("/api/v1/admin/users")
def get_users(
    db: Session = Depends(get_db),
    admin=Depends(verify_admin_token)
):
    users = db.query(User).order_by(User.id.asc()).all()

    return users


@app.post("/api/v1/admin/users/add")
def admin_add_user(
    data: AdminUserSchema,
    db: Session = Depends(get_db),
    admin=Depends(verify_admin_token)
):
    existing_user = db.query(User).filter(
        User.username == data.username
    ).first()

    if existing_user:
        raise HTTPException(
            status_code=400,
            detail="Username already exists"
        )

    new_user = User(
        username=data.username,
        password_hash=hash_password(data.password),
        is_admin=data.is_admin
    )

    db.add(new_user)
    db.commit()

    add_activity_log(
        db,
        f"Added user: {data.username}",
        admin.get("sub", "admin")
    )

    return {
        "message": "User added successfully"
    }


@app.put("/api/v1/admin/users/{user_id}")
def admin_update_user(
    user_id: int,
    data: AdminUserSchema,
    db: Session = Depends(get_db),
    admin=Depends(verify_admin_token)
):
    user = db.query(User).filter(
        User.id == user_id
    ).first()

    if not user:
        raise HTTPException(
            status_code=404,
            detail="User not found"
        )

    old_username = user.username

    user.username = data.username
    user.password_hash = hash_password(data.password)
    user.is_admin = data.is_admin

    db.commit()

    add_activity_log(
        db,
        f"Updated user: {old_username} to {data.username}",
        admin.get("sub", "admin")
    )

    return {
        "message": "User updated successfully"
    }


@app.delete("/api/v1/admin/users/{user_id}")
def admin_delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    admin=Depends(verify_admin_token)
):
    user = db.query(User).filter(
        User.id == user_id
    ).first()

    if not user:
        raise HTTPException(
            status_code=404,
            detail="User not found"
        )

    deleted_username = user.username

    db.delete(user)
    db.commit()

    add_activity_log(
        db,
        f"Deleted user: {deleted_username}",
        admin.get("sub", "admin")
    )

    return {
        "message": "User deleted successfully"
    }


latest_broadcast = {
    "title": "",
    "message": "",
    "created_at": ""
}

@app.put("/api/v1/admin/ban/{user_id}")
def ban_user(
    user_id: int,
    db: Session = Depends(get_db),
    admin=Depends(verify_admin_token)
):
    user = db.query(User).filter(
        User.id == user_id
    ).first()

    if not user:
        raise HTTPException(
            status_code=404,
            detail="User not found"
        )

    user.is_banned = 1

    db.commit()

    add_activity_log(
        db,
        f"Banned user: {user.username}",
        admin.get("sub", "admin")
    )

    return {
        "message": "User banned successfully"
    }


@app.put("/api/v1/admin/unban/{user_id}")
def unban_user(
    user_id: int,
    db: Session = Depends(get_db),
    admin=Depends(verify_admin_token)
):
    user = db.query(User).filter(
        User.id == user_id
    ).first()

    if not user:
        raise HTTPException(
            status_code=404,
            detail="User not found"
        )

    user.is_banned = 0

    db.commit()

    add_activity_log(
        db,
        f"Unbanned user: {user.username}",
        admin.get("sub", "admin")
    )

    return {
        "message": "User unbanned successfully"
    }

@app.post("/api/v1/admin/broadcast")
def create_broadcast(
    data: dict,
    db: Session = Depends(get_db),
    admin=Depends(verify_admin_token)
):
    latest_broadcast["title"] = data.get("title")
    latest_broadcast["message"] = data.get("message")
    latest_broadcast["created_at"] = str(datetime.now())

    add_activity_log(
        db,
        f"Sent broadcast: {data.get('title')}",
        admin.get("sub", "admin")
    )

    return {
        "message": "Broadcast sent"
    }


@app.get("/api/v1/broadcast/latest")
def get_latest_broadcast():
    return latest_broadcast


@app.get("/api/v1/admin/logs")
def get_activity_logs(
    db: Session = Depends(get_db),
    admin=Depends(verify_admin_token)
):
    logs = db.query(ActivityLog)\
        .order_by(ActivityLog.id.desc())\
        .limit(50)\
        .all()

    return logs
online_players = {}


@app.post("/api/v1/player/heartbeat")
async def player_heartbeat(request: Request):
    data = await request.json()

    username = data.get("username", "GuestPlayer")

    online_players[username] = datetime.now()

    return {
        "message": "heartbeat received"
    }


@app.get("/api/v1/admin/online")
def get_online_players(
    admin=Depends(verify_admin_token)
):
    now = datetime.now()

    active_players = []

    for username, last_seen in online_players.items():
        seconds_ago = (now - last_seen).total_seconds()

        if seconds_ago <= 30:
            active_players.append({
                "username": username,
                "last_seen_seconds_ago": round(seconds_ago, 1)
            })

    return {
        "online_count": len(active_players),
        "players": active_players
    }
@app.get("/api/v1/player/stats/{username}")
def get_player_stats(
    username: str,
    db: Session = Depends(get_db)
):

    scores = db.query(Score).filter(
        Score.username == username
    ).all()

    if len(scores) == 0:

        return {
            "username": username,
            "total_clears": 0,
            "best_score": 0,
            "best_time": 0,
            "average_sanity": 0,
            "total_pulses_used": 0,
            "levels_completed": []
        }

    total_clears = len(scores)

    best_score = min(
        score.final_score for score in scores
    )

    best_time = min(
        score.clear_time for score in scores
    )

    average_sanity = round(
        sum(score.sanity_left for score in scores)
        / total_clears,
        2
    )

    total_pulses_used = sum(
        score.pulses_used for score in scores
    )

    levels_completed = sorted(list(set(
        score.level_id for score in scores
    )))

    return {
        "username": username,
        "total_clears": total_clears,
        "best_score": best_score,
        "best_time": best_time,
        "average_sanity": average_sanity,
        "total_pulses_used": total_pulses_used,
        "levels_completed": levels_completed
    }
@app.get("/api/v1/player/achievements/{username}")
def get_player_achievements(
    username: str,
    db: Session = Depends(get_db)
):
    scores = db.query(Score).filter(
        Score.username == username
    ).all()

    achievements = []

    if not scores:
        return {
            "username": username,
            "achievements": []
        }

    if any(score.pulses_used == 0 for score in scores):
        achievements.append({
            "name": "Silent Knight",
            "description": "Clear a level without using pulse."
        })

    if any(score.clear_time <= 30 for score in scores):
        achievements.append({
            "name": "Speed Runner",
            "description": "Clear a level in 30 seconds or less."
        })

    if any(score.sanity_left <= 25 for score in scores):
        achievements.append({
            "name": "Madness Survivor",
            "description": "Clear a level with 25 sanity or lower."
        })

    if len(set(score.level_id for score in scores)) >= 5:
        achievements.append({
            "name": "Dungeon Conqueror",
            "description": "Clear all 5 levels."
        })

    if len(scores) >= 10:
        achievements.append({
            "name": "Maze Veteran",
            "description": "Complete 10 total runs."
        })

    best_score = min(score.final_score for score in scores)

    if best_score <= 50:
        achievements.append({
            "name": "Elite Escape",
            "description": "Earn a final score of 50 or lower."
        })

    return {
        "username": username,
        "achievements": achievements
    }
