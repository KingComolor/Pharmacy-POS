import os
from replit import db as replit_db

class DatabaseManager:
    """Database abstraction layer for switching between PostgreSQL and Replit DB"""
    
    def __init__(self):
        self.use_postgres = bool(os.environ.get("DATABASE_URL"))
    
    def get(self, key, default=None):
        """Get value from database"""
        if self.use_postgres:
            # PostgreSQL queries handled by SQLAlchemy models
            return default
        else:
            # Replit DB fallback
            try:
                return replit_db[key]
            except KeyError:
                return default
    
    def set(self, key, value):
        """Set value in database"""
        if not self.use_postgres:
            replit_db[key] = value
    
    def delete(self, key):
        """Delete key from database"""
        if not self.use_postgres:
            try:
                del replit_db[key]
            except KeyError:
                pass
    
    def keys(self, prefix=""):
        """Get all keys with prefix"""
        if not self.use_postgres:
            return [k for k in replit_db.keys() if k.startswith(prefix)]
        return []

# Global database manager instance
db_manager = DatabaseManager()
