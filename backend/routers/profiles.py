from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import os
import sqlite3
from database import active_profile
from config import DB_PATH

router = APIRouter(prefix="/api/profiles", tags=["profiles"])

class ProfileIn(BaseModel):
    id: str
    name: str

@router.get("")
def list_profiles():
    profiles = []
    base_dir = os.path.dirname(DB_PATH)
    
    # Ensure default database exists, create if not
    if not os.path.exists(os.path.join(base_dir, "portfolio.db")):
        from database import db
        # Active profile defaults to 'default'
        with db() as conn:
            conn.execute("INSERT OR REPLACE INTO portfolio_settings (key, value) VALUES ('portfolio_name', 'Default')")

    for f in os.listdir(base_dir):
        if f == "portfolio.db":
            profile_id = "default"
        elif f.startswith("portfolio_") and f.endswith(".db"):
            profile_id = f[len("portfolio_"):-len(".db")]
        else:
            continue
            
        path = os.path.join(base_dir, f)
        conn = sqlite3.connect(path)
        try:
            name_row = conn.execute("SELECT value FROM portfolio_settings WHERE key='portfolio_name'").fetchone()
            name = name_row[0] if name_row else profile_id.capitalize()
        except sqlite3.OperationalError:
            # Table might not exist yet if it's completely empty or corrupted
            name = profile_id.capitalize()
        finally:
            conn.close()
            
        profiles.append({"id": profile_id, "name": name})
        
    return profiles


@router.post("")
def create_profile(data: ProfileIn):
    safe_id = "".join(c for c in data.id if c.isalnum() or c in "-_").lower()
    if not safe_id:
        raise HTTPException(400, "Invalid profile ID")
        
    # Check if exists
    base_dir = os.path.dirname(DB_PATH)
    db_name = f"portfolio_{safe_id}.db" if safe_id != "default" else "portfolio.db"
    if os.path.exists(os.path.join(base_dir, db_name)):
        raise HTTPException(400, "Profile already exists")
        
    # Set contextvar so get_conn initializes the right DB
    token = active_profile.set(safe_id)
    try:
        from database import db
        with db() as conn:
            conn.execute("INSERT OR REPLACE INTO portfolio_settings (key, value) VALUES ('portfolio_name', ?)", (data.name,))
    finally:
        active_profile.reset(token)
    
    return {"id": safe_id, "name": data.name}


@router.put("/{profile_id}")
def update_profile(profile_id: str, data: ProfileIn):
    safe_id = "".join(c for c in profile_id if c.isalnum() or c in "-_").lower()
    if not safe_id:
        raise HTTPException(400, "Invalid profile ID")
        
    token = active_profile.set(safe_id)
    try:
        from database import db
        with db() as conn:
            conn.execute("INSERT OR REPLACE INTO portfolio_settings (key, value) VALUES ('portfolio_name', ?)", (data.name,))
    finally:
        active_profile.reset(token)
        
    return {"id": safe_id, "name": data.name}


@router.delete("/{profile_id}")
def delete_profile(profile_id: str):
    safe_id = "".join(c for c in profile_id if c.isalnum() or c in "-_").lower()
    if safe_id == "default":
        raise HTTPException(400, "Cannot delete default profile")
        
    base_dir = os.path.dirname(DB_PATH)
    db_name = f"portfolio_{safe_id}.db"
    path = os.path.join(base_dir, db_name)
    
    if os.path.exists(path):
        try:
            os.remove(path)
        except Exception as e:
            raise HTTPException(500, f"Could not delete database file: {str(e)}")
            
    return {"status": "ok"}
