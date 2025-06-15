from functools import wraps
from flask import session, redirect, url_for, flash, g
from flask_login import current_user
from models import License
from datetime import datetime

def license_required(f):
    """Decorator to check if pharmacy has valid license"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if current_user.is_authenticated and current_user.role != 'superadmin':
            if not current_user.pharmacy_id:
                flash('No pharmacy associated with this account.', 'error')
                return redirect(url_for('auth.login'))
            
            # Check license status
            license = License.query.filter_by(
                pharmacy_id=current_user.pharmacy_id,
                status='active'
            ).first()
            
            if not license or license.is_expired():
                flash('Your license has expired. Please renew to continue.', 'error')
                return redirect(url_for('auth.pay_license'))
        
        return f(*args, **kwargs)
    return decorated_function

def role_required(*roles):
    """Decorator to check user role"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                return redirect(url_for('auth.login'))
            
            if current_user.role not in roles:
                flash('You do not have permission to access this page.', 'error')
                return redirect(url_for('main.dashboard'))
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def superadmin_required(f):
    """Decorator to check if user is superadmin"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != 'superadmin':
            flash('Superadmin access required.', 'error')
            return redirect(url_for('main.index'))
        return f(*args, **kwargs)
    return decorated_function

def same_pharmacy_required(f):
    """Decorator to ensure users can only access their own pharmacy data"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if current_user.role == 'superadmin':
            return f(*args, **kwargs)
        
        # Store current user's pharmacy ID in g for use in views
        g.pharmacy_id = current_user.pharmacy_id
        return f(*args, **kwargs)
    return decorated_function
