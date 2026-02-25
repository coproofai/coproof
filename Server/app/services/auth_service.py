from datetime import datetime
import os
import time
from urllib.parse import urlencode
import jwt
import requests
from werkzeug.security import generate_password_hash, check_password_hash
from flask_jwt_extended import create_access_token, create_refresh_token
from app.models.user import User
from app.extensions import db
from app.exceptions import CoProofError

class AuthService:
    @staticmethod
    def register_user(data):
        """
        Registers a new user.
        Raises error if email exists.
        """
        if User.query.filter_by(email=data['email']).first():
            raise CoProofError("Email already exists", code=400)
        
        new_user = User(
            full_name=data['full_name'],
            email=data['email'],
            password_hash=generate_password_hash(data['password'])
        )
        
        db.session.add(new_user)
        db.session.commit()
        return new_user

    @staticmethod
    def login_user(email, password):
        """
        Authenticates user and returns JWT token.
        """
        user = User.query.filter_by(email=email).first()
        
        if not user or not check_password_hash(user.password_hash, password):
            raise CoProofError("Invalid credentials", code=401)
            
        # Create JWT (Identity is the UUID)
        access_token = create_access_token(identity=str(user.id))
        return {
            "access_token": access_token,
            "user": user
        }


    @staticmethod
    def github_login(code):
        """
        Exchanges code for token, gets user info, creates/updates User.
        """
        client_id = os.environ.get('GITHUB_CLIENT_ID')
        client_secret = os.environ.get('GITHUB_CLIENT_SECRET')
        
        # 1. Exchange Code for Token
        token_url = "https://github.com/login/oauth/access_token"
        payload = {
            'client_id': client_id,
            'client_secret': client_secret,
            'code': code
        }
        headers = {'Accept': 'application/json'}
        resp = requests.post(token_url, json=payload, headers=headers)
        if resp.status_code != 200:
             raise Exception("Failed to connect to GitHub")
             
        data = resp.json()
        access_token = data.get('access_token')
        refresh_token = data.get('refresh_token')
        expires_in = data.get('expires_in')

        if not access_token:
            raise Exception("No access token returned")

        # 2. Get User Profile
        user_resp = requests.get("https://api.github.com/user", headers={
            "Authorization": f"token {access_token}"
        })
        github_user = user_resp.json()
        github_id = str(github_user['id'])
        email = github_user.get('email') # Note: Might be null if private

        # 3. Upsert User in DB
        user = User.query.filter_by(github_id=github_id).first()
        
        if not user:
            # If not found by ID, try email logic or create new
            if not email:
                email = f"{github_user['login']}@users.noreply.github.com"
            
            user = User(
                full_name=github_user.get('name') or github_user['login'],
                email=email,
                password_hash="oauth_user", # Placeholder
                github_id=github_id
            )
            db.session.add(user)
        
        # 4. Update Tokens
        user.set_github_token(access_token, refresh_token, expires_in)
        db.session.commit()

        # 5. Generate JWT
        jwt = create_access_token(identity=str(user.id))
        return {"access_token": jwt, "user": user}

    @staticmethod
    def refresh_github_token_if_needed(user):
        """
        Checks expiration and refreshes token if necessary.
        """
        if user.token_expires_at and user.token_expires_at < datetime.now(datetime.timezone.utc):
            if not user.github_refresh_token:
                return None # Cannot refresh
            
            # Logic to call GitHub refresh endpoint would go here
            # For brevity, assuming success or implementing standard OAuth refresh flow
            pass
        return user.github_access_token


    @staticmethod
    def get_github_auth_url():
        """
        Returns the URL to redirect the user to GitHub for authorization.
        Includes the necessary scopes to Push Code.
        """
        base_url = "https://github.com/login/oauth/authorize"
        params = {
            "client_id": os.environ.get('GITHUB_CLIENT_ID'),
            "redirect_uri": os.environ.get('GITHUB_REDIRECT_URI'),
            "scope": os.environ.get('GITHUB_OAUTH_SCOPES', "repo,read:user,user:email"),
            "state": "random_string_to_prevent_csrf" # In prod, generate random string
        }
        return f"{base_url}?{urlencode(params)}"

    @staticmethod
    def handle_github_callback(code):
        """
        Step 2 of OAuth: Exchange code for User Access Token.
        """
        # 1. Exchange Code for Token
        token_url = "https://github.com/login/oauth/access_token"
        payload = {
            "client_id": os.environ.get('GITHUB_CLIENT_ID'),
            "client_secret": os.environ.get('GITHUB_CLIENT_SECRET'),
            "code": code,
            "redirect_uri": os.environ.get('GITHUB_REDIRECT_URI')
        }
        headers = {"Accept": "application/json"}
        
        resp = requests.post(token_url, json=payload, headers=headers)
        if resp.status_code != 200:
             raise CoProofError("Failed to communicate with GitHub", code=502)
             
        data = resp.json()
        if 'error' in data:
            raise CoProofError(f"GitHub Error: {data['error_description']}", code=400)

        access_token = data.get('access_token')
        # GitHub tokens don't always return refresh tokens unless configured in App settings
        # and using specific flows, but we store what we get.
        
        # 2. Get User Profile using the NEW Token
        user_resp = requests.get("https://api.github.com/user", headers={
            "Authorization": f"token {access_token}"
        })
        if user_resp.status_code != 200:
            raise CoProofError("Failed to fetch GitHub profile", code=502)
            
        gh_user = user_resp.json()
        gh_id = str(gh_user['id'])
        
        # 3. Get Email (if private)
        email = gh_user.get('email')
        if not email:
            email_resp = requests.get("https://api.github.com/user/emails", headers={
                "Authorization": f"token {access_token}"
            })
            if email_resp.status_code == 200:
                # Find primary email
                for e in email_resp.json():
                    if e['primary'] and e['verified']:
                        email = e['email']
                        break
        
        if not email:
            raise CoProofError("Could not verify GitHub email", code=400)

        # 4. Sync User in DB
        user = User.query.filter_by(github_id=gh_id).first()
        
        if not user:
            # Check if user exists by email to merge accounts
            user = User.query.filter_by(email=email).first()
            
        if not user:
            # Create new user
            user = User(
                full_name=gh_user.get('name') or gh_user.get('login'),
                email=email,
                password_hash="oauth_provider", # Flag that this is an OAuth user
                github_id=gh_id,
                is_verified=True
            )
            db.session.add(user)
        else:
            # Link existing user to GitHub
            user.github_id = gh_id
            
        # 5. CRITICAL: Store the Token. This allows us to git push later.
        user.github_access_token = access_token
        db.session.commit()
        
        # 6. Generate App JWT
        access_token = create_access_token(identity=str(user.id))
        refresh_token = create_refresh_token(identity=str(user.id)) # <-- NEW

        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "user": user,
            "github_connected": True
        }
    
    
    @staticmethod
    def _get_github_app_jwt():
        """
        Creates a short-lived JWT to authenticate as the GitHub App itself.
        """
        private_key = open(os.environ.get('GITHUB_PRIVATE_KEY_PATH'), 'r').read()
        app_id = os.environ.get('GITHUB_APP_ID')
        
        payload = {
            'iat': int(time.time()),
            'exp': int(time.time()) + (10 * 60), # 10 minute expiration
            'iss': app_id
        }
        return jwt.encode(payload, private_key, algorithm='RS256')

    @staticmethod
    def get_installation_access_token(installation_id):
        """
        Gets a temporary token for a specific installation.
        This allows the app to act on a user's repository.
        """
        app_jwt = AuthService._get_github_app_jwt()
        headers = {
            "Authorization": f"Bearer {app_jwt}",
            "Accept": "application/vnd.github.v3+json"
        }
        
        url = f"https://api.github.com/app/installations/{installation_id}/access_tokens"
        resp = requests.post(url, headers=headers)
        
        if resp.status_code != 201:
            raise Exception("Could not get installation access token")
            
        return resp.json()['token']
