import streamlit as st
import bcrypt
import extra_streamlit_components as stx
from datetime import datetime, timedelta
import re
import time

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

    def register_user(self, name, phone, pin, grades=None, gender=None, colorblind=None, disability=None, email=None):
        """Creates a new user with Hashed PIN and optional Initial Grades."""
        # Validate name (strip whitespace, min 2 chars, max 100)
        name = (name or "").strip()
        if len(name) < 2:
            return False, "❌ Please enter your name (at least 2 characters)"
        if len(name) > 100:
            return False, "❌ Name is too long (max 100 characters)"

        if not self.validate_phone(phone):
            return False, "❌ Invalid Phone Format"
        if not pin.isdigit() or len(pin) != 6:
            return False, "❌ PIN must be 6 digits"

        try:
            # Check if phone already exists (UNIQUE enforcement)
            existing = self.supabase.table("student_profiles").select("id").eq("phone", phone).execute()
            if existing.data:
                return False, "❌ Phone number already registered. Please login instead."

            # Phone is unique - proceed with registration
            hashed = self.hash_pin(pin)
            grades = grades or {}

            data = {
                "full_name": name,
                "phone": phone,
                "pin_hash": hashed,
                "email": email,
                "grades": grades,
                "gender": gender,
                "colorblind": colorblind,
                "disability": disability
            }

            res = self.supabase.table("student_profiles").insert(data).execute()

            # Handle Response
            if res.data:
                user = res.data[0]
                self.set_session(user)
                return True, user

            # FALLBACK: Sometimes insert doesn't return rows depending on headers/RLS
            # Verify if user was created
            verify = self.supabase.table("student_profiles").select("*").eq("phone", phone).execute()
            if verify.data:
                user = verify.data[0]
                self.set_session(user)
                return True, user

            return False, "Registration failed. Please try again."

        except Exception as e:
            return False, f"Error: {e}"

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
        try:
            # Force expire the cookie by setting it to empty with past date
            self.cookie_manager.set(self.COOKIE_NAME, "", expires_at=datetime.now() - timedelta(days=1))
            # Also try delete for good measure
            self.cookie_manager.delete(self.COOKIE_NAME)
        except KeyError:
            pass # Cookie already gone
            
        st.session_state['logged_in'] = False
        st.session_state['user'] = None
        
        # CRITICAL: Clear persistence artifacts to prevent "Ghost Grades"
        # where User B inherits User A's fallback inputs
        keys_to_clear = ['guest_grades', 'dash', 'last_calc_user']
        for k in keys_to_clear:
            if k in st.session_state:
                del st.session_state[k]
                
        # Give frontend time to process
        time.sleep(2)  # Increased to 2s to be safe
        st.rerun()

    def update_profile(self, user_id, updates):
        """Updates specific profile fields with validation"""
        try:
            # Validate name if being updated
            if 'full_name' in updates:
                name = (updates['full_name'] or "").strip()
                if len(name) < 2:
                    return False, "❌ Name must be at least 2 characters"
                if len(name) > 100:
                    return False, "❌ Name is too long (max 100 characters)"
                updates['full_name'] = name  # Use cleaned version

            res = self.supabase.table("student_profiles").update(updates).eq("id", user_id).execute()
            
            if res.data:
                st.session_state['user'].update(updates)
                return True, "Profile Updated!"
                
            # Fallback: If update returns empty (possible RLS issue), verify persistence
            # explicitly by fetching the specific columns we tried to update.
            verify = self.supabase.table("student_profiles").select("*").eq("id", user_id).execute()
            if verify.data:
                 actual_data = verify.data[0]
                 # Validation: Check if values match
                 all_match = True
                 for k, v in updates.items():
                     if actual_data.get(k) != v:
                         all_match = False
                         break
                 
                 if all_match:
                     st.session_state['user'].update(updates)
                     return True, "Profile Updated!"
                 else:
                     return False, "Update execution failed (RLS or Schema Mismatch)"
                  
            return False, "Update returned no data and verification failed"
        except Exception as e:
            return False, str(e)

    def save_quiz_results(self, user_id, signals):
        """Saves values from the Discovery Quiz"""
        return self.update_profile(user_id, {"student_signals": signals})
