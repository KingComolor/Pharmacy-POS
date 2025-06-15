from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import check_password_hash, generate_password_hash
from models import User, Pharmacy, License, Payment
from app import db
from datetime import datetime, timedelta

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    """User login"""
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))
    
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        
        user = User.query.filter_by(email=email).first()
        
        if user and check_password_hash(user.password_hash, password):
            if not user.is_active:
                flash('Your account has been deactivated.', 'error')
                return render_template('auth/login.html')
            
            login_user(user)
            
            # Check license for non-superadmin users
            if user.role != 'superadmin' and user.pharmacy_id:
                license = License.query.filter_by(
                    pharmacy_id=user.pharmacy_id,
                    status='active'
                ).first()
                
                if not license or license.is_expired():
                    flash('Your license has expired. Please renew to continue.', 'warning')
                    return redirect(url_for('auth.pay_license'))
            
            next_page = request.args.get('next')
            return redirect(next_page) if next_page else redirect(url_for('main.dashboard'))
        else:
            flash('Invalid email or password.', 'error')
    
    return render_template('auth/login.html')

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    """Pharmacy registration"""
    if request.method == 'POST':
        # Pharmacy details
        pharmacy_name = request.form.get('pharmacy_name')
        pharmacy_email = request.form.get('pharmacy_email')
        pharmacy_phone = request.form.get('pharmacy_phone')
        address = request.form.get('address')
        
        # Admin user details
        first_name = request.form.get('first_name')
        last_name = request.form.get('last_name')
        email = request.form.get('email')
        phone = request.form.get('phone')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        terms_accepted = request.form.get('terms_accepted')
        
        # Validation
        errors = []
        
        if not all([pharmacy_name, pharmacy_email, pharmacy_phone, first_name, 
                   last_name, email, password, confirm_password]):
            errors.append('All fields are required.')
        
        if password != confirm_password:
            errors.append('Passwords do not match.')
        
        if len(password) < 6:
            errors.append('Password must be at least 6 characters long.')
        
        if not terms_accepted:
            errors.append('You must accept the terms and conditions.')
        
        if User.query.filter_by(email=email).first():
            errors.append('Email already registered.')
        
        if Pharmacy.query.filter_by(email=pharmacy_email).first():
            errors.append('Pharmacy email already registered.')
        
        if errors:
            for error in errors:
                flash(error, 'error')
            return render_template('auth/register.html')
        
        try:
            # Create pharmacy
            pharmacy = Pharmacy(
                name=pharmacy_name,
                email=pharmacy_email,
                phone=pharmacy_phone,
                address=address,
                terms_accepted=True
            )
            db.session.add(pharmacy)
            db.session.flush()  # Get pharmacy ID
            
            # Create admin user
            user = User(
                email=email,
                password_hash=generate_password_hash(password),
                role='admin',
                first_name=first_name,
                last_name=last_name,
                phone=phone,
                pharmacy_id=pharmacy.id
            )
            db.session.add(user)
            
            # Create initial license record
            license = License(
                pharmacy_id=pharmacy.id,
                status='pending',
                amount=3000.0
            )
            db.session.add(license)
            
            db.session.commit()
            
            flash('Registration successful! Please proceed to license payment.', 'success')
            login_user(user)
            return redirect(url_for('auth.pay_license'))
            
        except Exception as e:
            db.session.rollback()
            flash('Registration failed. Please try again.', 'error')
            return render_template('auth/register.html')
    
    return render_template('auth/register.html')

@auth_bp.route('/terms')
def terms():
    """Terms and conditions"""
    return render_template('auth/terms.html')

@auth_bp.route('/pay-license', methods=['GET', 'POST'])
@login_required
def pay_license():
    """License payment page"""
    if current_user.role == 'superadmin':
        return redirect(url_for('admin.dashboard'))
    
    license = License.query.filter_by(
        pharmacy_id=current_user.pharmacy_id
    ).order_by(License.created_at.desc()).first()
    
    if request.method == 'POST':
        mpesa_code = request.form.get('mpesa_code')
        phone_number = request.form.get('phone_number')
        
        if not mpesa_code or not phone_number:
            flash('M-PESA code and phone number are required.', 'error')
            return render_template('auth/pay_license.html', license=license)
        
        # Check if payment already exists
        existing_payment = Payment.query.filter_by(
            mpesa_code=mpesa_code,
            pharmacy_id=current_user.pharmacy_id
        ).first()
        
        if existing_payment:
            flash('This M-PESA code has already been submitted.', 'error')
            return render_template('auth/pay_license.html', license=license)
        
        # Create payment record
        payment = Payment(
            pharmacy_id=current_user.pharmacy_id,
            license_id=license.id if license else None,
            mpesa_code=mpesa_code,
            phone_number=phone_number,
            amount=3000.0,
            status='pending'
        )
        db.session.add(payment)
        db.session.commit()
        
        flash('Payment submitted successfully! Awaiting confirmation from admin.', 'success')
        return redirect(url_for('main.dashboard'))
    
    return render_template('auth/pay_license.html', license=license)

@auth_bp.route('/logout')
@login_required
def logout():
    """User logout"""
    logout_user()
    flash('You have been logged out successfully.', 'info')
    return redirect(url_for('main.index'))
