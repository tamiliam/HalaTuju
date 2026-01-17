import streamlit as st
import bcrypt
import extra_streamlit_components as stx
from datetime import datetime, timedelta
import re

# Initialize Cookie Manager (Must be unique key)
# This handles the browser-side persistence
def get_manager():
    return stx.CookieManager()

class AuthManager:
    def __init__(self, supabase_client):
        self.supabase = supabase_client
        self.cookie_manager = get_manager()
        # Session Key for Cookie
        self.COOKIE_NAME = "halatuju_auth_v1"
        self.EXPIRE_DAYS = 30

    def hash_pin(self, pin: str) -> str:
        """Hashes the 6-digit PIN securely."""
        return bcrypt.hashpw(pin.encode(), bcrypt.gensalt()).decode()

    def verify_pin(self, pin: str, hashed_pin: str) -> bool:
        """Verifies input PIN against stored hash."""
        if not hashed_pin: return False # Handle None/Empty legacy records
        return bcrypt.checkpw(pin.encode(), hashed_pin.encode())
    
    def validate_phone(self, phone: str) -> bool:
        """Validates Malaysia phone number format (Basic)"""
        # Strict: 01x-xxxxxxx or +601x
        pattern = r"^(?:\+?60|0)1[0-9]{1}-?[0-9]{7,8}$"
        return bool(re.match(pattern, phone.strip().replace(" ", "")))

    def register_user(self, name, phone, pin, grades=None, email=None):
        """Creates a new user with Hashed PIN and optional Initial Grades."""
        if not self.validate_phone(phone):
            return False, "❌ Invalid Phone Format"
        if not pin.isdigit() or len(pin) != 6:
            return False, "❌ PIN must be 6 digits"
            
        hashed = self.hash_pin(pin)
        grades = grades or {}
        
        data = {
            "full_name": name,
            "phone": phone,
            "pin_hash": hashed,
            "email": email,
            "grades": grades, # User confirmed we MUST save the current grades
            # "updated_at": "now()" 
        }
        
        try:
            # Use Upsert to allow existing users to set their PIN
            # We explicitly exclude 'grades' from data so we don't wipe them if they existed
            # But Supabase update will only update provided columns.
            
            # Better strategy:
            # 1. Check if user exists
            existing = self.supabase.table("student_profiles").select("id").eq("phone", phone).execute()
            if existing.data:
                 # Update PIN, Name, AND Grades (Since user explicitly submitted them)
                 res = self.supabase.table("student_profiles").update({
                     "full_name": name,
                     "pin_hash": hashed,
                     "grades": grades
                     # "updated_at": "now()" 
                 }).eq("phone", phone).execute()
            else:
                 # Insert New
                 res = self.supabase.table("student_profiles").insert(data).execute()

            # Handle Response
            if res.data:
                user = res.data[0]
                self.set_session(user)
                return True, user
            
            # FALLBACK: Sometimes update/insert doesn't return rows depending on headers/RLS
            # Verify if user exists manually
            verify = self.supabase.table("student_profiles").select("*").eq("phone", phone).execute()
            if verify.data:
                 user = verify.data[0]
                 self.set_session(user)
                 return True, user
                 
            return False, f"Debug: Op Success but No Data returned. Res: {res}"
            
        except Exception as e:
            return False, f"Error: {e}"
        except Exception as e:
            return False, f"Error: {e}"
        return False, "Unknown Error"

    def login_user(self, phone, pin):
        """Standard Login Flow"""
        try:
            res = self.supabase.table("student_profiles").select("*").eq("phone", phone).execute()
            if not res.data:
                return False, "❌ User not found"
            
            user = res.data[0]
            if self.verify_pin(pin, user.get('pin_hash', '')):
                self.set_session(user)
                return True, user
            else:
                return False, "❌ Invalid PIN"
        except Exception as e:
            return False, f"Login Error: {e}"

    def set_session(self, user):
        """Sets browser cookie and session_state"""
        # 1. Update DB last_login
        try:
            self.supabase.table("student_profiles").update({"last_login": "now()"}).eq("id", user['id']).execute()
        except: pass
        
        # 2. Set Cookie (Expires in 30 days)
        # We store the ID. In production, use a signed token.
        self.cookie_manager.set(self.COOKIE_NAME, user['phone'], expires_at=datetime.now() + timedelta(days=self.EXPIRE_DAYS))
        
        # 3. Set Session State
        st.session_state['user'] = user
        st.session_state['logged_in'] = True

    def check_session(self):
        """Checks for existing cookie on app load"""
        # CRITICAL: Always read cookie to keep component active/synced
        cookie_val = self.cookie_manager.get(self.COOKIE_NAME)
        
        # 1. If already in session, trust it
        if st.session_state.get('logged_in'):
            return True
            
        # 2. If not in session but cookie exists, verify
        if cookie_val:
            # Token found (Phone), verify against DB
            try:
                res = self.supabase.table("student_profiles").select("*").eq("phone", cookie_val).execute()
                if res.data:
                    user = res.data[0]
                    st.session_state['user'] = user
                    st.session_state['logged_in'] = True
                    return True
            except:
                pass
        return False

    def logout(self):
        """Clears session and cookies"""
        self.cookie_manager.delete(self.COOKIE_NAME)
        st.session_state['logged_in'] = False
        st.session_state['user'] = None
        # Give frontend time to process cookie deletion
        time.sleep(1) 
        st.rerun()
