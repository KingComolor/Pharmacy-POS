from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from auth import license_required, same_pharmacy_required, role_required
from models import Pharmacy, License, User
from app import db
from werkzeug.security import check_password_hash, generate_password_hash

settings_bp = Blueprint('settings', __name__)

@settings_bp.route('/')
@login_required
@license_required
@same_pharmacy_required
@role_required('admin', 'pharmacist')
def index():
    """Settings dashboard"""
    pharmacy = Pharmacy.query.get(current_user.pharmacy_id)
    
    # Get license info
    license = License.query.filter_by(
        pharmacy_id=current_user.pharmacy_id,
        status='active'
    ).first()
    
    return render_template('settings/index.html', pharmacy=pharmacy, license=license)

@settings_bp.route('/pharmacy', methods=['GET', 'POST'])
@login_required
@license_required
@same_pharmacy_required
@role_required('admin')
def pharmacy_settings():
    """Pharmacy settings"""
    pharmacy = Pharmacy.query.get(current_user.pharmacy_id)
    
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        phone = request.form.get('phone')
        address = request.form.get('address')
        mpesa_till = request.form.get('mpesa_till')
        receipt_footer = request.form.get('receipt_footer')
        
        # Validation
        if not name:
            flash('Pharmacy name is required.', 'error')
            return render_template('settings/pharmacy_settings.html', pharmacy=pharmacy)
        
        if not email:
            flash('Email is required.', 'error')
            return render_template('settings/pharmacy_settings.html', pharmacy=pharmacy)
        
        # Check for duplicate email (excluding current pharmacy)
        existing = Pharmacy.query.filter_by(email=email).filter(
            Pharmacy.id != pharmacy.id
        ).first()
        if existing:
            flash('Email already in use by another pharmacy.', 'error')
            return render_template('settings/pharmacy_settings.html', pharmacy=pharmacy)
        
        try:
            pharmacy.name = name
            pharmacy.email = email
            pharmacy.phone = phone
            pharmacy.address = address
            pharmacy.mpesa_till = mpesa_till or '123456'
            pharmacy.receipt_footer = receipt_footer or 'Thank you for your business!'
            
            db.session.commit()
            flash('Pharmacy settings updated successfully!', 'success')
            
        except Exception as e:
            db.session.rollback()
            flash('Failed to update settings. Please try again.', 'error')
    
    return render_template('settings/pharmacy_settings.html', pharmacy=pharmacy)

@settings_bp.route('/users')
@login_required
@license_required
@same_pharmacy_required
@role_required('admin')
def users():
    """Manage pharmacy users"""
    users = User.query.filter_by(pharmacy_id=current_user.pharmacy_id).all()
    return render_template('settings/users.html', users=users)

@settings_bp.route('/add-user', methods=['GET', 'POST'])
@login_required
@license_required
@same_pharmacy_required
@role_required('admin')
def add_user():
    """Add new user"""
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        first_name = request.form.get('first_name')
        last_name = request.form.get('last_name')
        phone = request.form.get('phone')
        role = request.form.get('role')
        
        # Validation
        errors = []
        if not all([email, password, first_name, last_name, role]):
            errors.append('All required fields must be filled.')
        
        if password != confirm_password:
            errors.append('Passwords do not match.')
        
        if len(password) < 6:
            errors.append('Password must be at least 6 characters long.')
        
        if role not in ['pharmacist', 'cashier']:
            errors.append('Invalid role selected.')
        
        if User.query.filter_by(email=email).first():
            errors.append('Email already registered.')
        
        if errors:
            for error in errors:
                flash(error, 'error')
            return render_template('settings/add_user.html')
        
        try:
            user = User(
                email=email,
                password_hash=generate_password_hash(password),
                role=role,
                first_name=first_name,
                last_name=last_name,
                phone=phone,
                pharmacy_id=current_user.pharmacy_id
            )
            db.session.add(user)
            db.session.commit()
            
            flash('User added successfully!', 'success')
            return redirect(url_for('settings.users'))
            
        except Exception as e:
            db.session.rollback()
            flash('Failed to add user. Please try again.', 'error')
    
    return render_template('settings/add_user.html')

@settings_bp.route('/edit-user/<int:user_id>', methods=['GET', 'POST'])
@login_required
@license_required
@same_pharmacy_required
@role_required('admin')
def edit_user(user_id):
    """Edit user"""
    user = User.query.filter_by(
        id=user_id,
        pharmacy_id=current_user.pharmacy_id
    ).first_or_404()
    
    # Cannot edit admin users or yourself
    if user.role == 'admin' or user.id == current_user.id:
        flash('Cannot edit this user.', 'error')
        return redirect(url_for('settings.users'))
    
    if request.method == 'POST':
        first_name = request.form.get('first_name')
        last_name = request.form.get('last_name')
        phone = request.form.get('phone')
        role = request.form.get('role')
        is_active = request.form.get('is_active') == 'on'
        
        # Validation
        if not all([first_name, last_name, role]):
            flash('All required fields must be filled.', 'error')
            return render_template('settings/edit_user.html', user=user)
        
        if role not in ['pharmacist', 'cashier']:
            flash('Invalid role selected.', 'error')
            return render_template('settings/edit_user.html', user=user)
        
        try:
            user.first_name = first_name
            user.last_name = last_name
            user.phone = phone
            user.role = role
            user.is_active = is_active
            
            db.session.commit()
            flash('User updated successfully!', 'success')
            return redirect(url_for('settings.users'))
            
        except Exception as e:
            db.session.rollback()
            flash('Failed to update user. Please try again.', 'error')
    
    return render_template('settings/edit_user.html', user=user)

@settings_bp.route('/change-password', methods=['GET', 'POST'])
@login_required
@license_required
@same_pharmacy_required
def change_password():
    """Change user password"""
    if request.method == 'POST':
        current_password = request.form.get('current_password')
        new_password = request.form.get('new_password')
        confirm_password = request.form.get('confirm_password')
        
        # Validation
        if not check_password_hash(current_user.password_hash, current_password):
            flash('Current password is incorrect.', 'error')
            return render_template('settings/change_password.html')
        
        if new_password != confirm_password:
            flash('New passwords do not match.', 'error')
            return render_template('settings/change_password.html')
        
        if len(new_password) < 6:
            flash('Password must be at least 6 characters long.', 'error')
            return render_template('settings/change_password.html')
        
        try:
            current_user.password_hash = generate_password_hash(new_password)
            db.session.commit()
            flash('Password changed successfully!', 'success')
            return redirect(url_for('settings.index'))
            
        except Exception as e:
            db.session.rollback()
            flash('Failed to change password. Please try again.', 'error')
    
    return render_template('settings/change_password.html')
