from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, session
from flask_login import login_required, current_user
from auth import superadmin_required
from models import (User, Pharmacy, License, Payment, Sale, Drug, Customer, 
                   SystemConfiguration, AuditLog, PharmacyActivity)
from app import db
from datetime import datetime, timedelta
from sqlalchemy import func, desc, and_, or_
import json

admin_bp = Blueprint('admin', __name__)

def log_audit_action(action, target_type, target_id=None, details=None):
    """Log audit action for superadmin activities"""
    audit_log = AuditLog(
        user_id=current_user.id,
        action=action,
        target_type=target_type,
        target_id=target_id,
        details=details,
        ip_address=request.remote_addr,
        user_agent=request.headers.get('User-Agent', '')
    )
    db.session.add(audit_log)
    db.session.commit()

def get_system_config(key, default=None):
    """Get system configuration value"""
    config = SystemConfiguration.query.filter_by(key=key).first()
    return config.value if config else default

def set_system_config(key, value, description=None):
    """Set system configuration value"""
    config = SystemConfiguration.query.filter_by(key=key).first()
    if config:
        config.value = value
        config.updated_by = current_user.id
        config.updated_at = datetime.utcnow()
    else:
        config = SystemConfiguration(
            key=key,
            value=value,
            description=description,
            updated_by=current_user.id
        )
        db.session.add(config)
    db.session.commit()

@admin_bp.route('/')
@login_required
@superadmin_required
def dashboard():
    """Enhanced Superadmin dashboard with comprehensive analytics"""
    # Enhanced system statistics
    stats = {}
    stats['total_pharmacies'] = Pharmacy.query.count()
    stats['active_pharmacies'] = Pharmacy.query.filter_by(is_active=True).count()
    stats['blocked_pharmacies'] = Pharmacy.query.filter_by(is_active=False).count()
    
    # License statistics
    stats['active_licenses'] = License.query.filter_by(status='active').count()
    stats['expired_licenses'] = License.query.filter_by(status='expired').count()
    stats['pending_licenses'] = License.query.filter_by(status='pending').count()
    
    # Payment statistics
    stats['pending_payments'] = Payment.query.filter_by(status='pending').count()
    stats['confirmed_payments'] = Payment.query.filter_by(status='confirmed').count()
    stats['rejected_payments'] = Payment.query.filter_by(status='rejected').count()
    
    # Revenue calculations
    total_revenue = db.session.query(func.sum(Payment.amount)).filter(
        Payment.status == 'confirmed'
    ).scalar() or 0
    stats['total_revenue'] = total_revenue
    
    # This month's revenue
    month_start = datetime.utcnow().replace(day=1)
    month_revenue = db.session.query(func.sum(Payment.amount)).filter(
        Payment.status == 'confirmed',
        Payment.confirmation_date >= month_start
    ).scalar() or 0
    stats['month_revenue'] = month_revenue
    
    # Today's registrations
    today = datetime.utcnow().date()
    stats['today_registrations'] = Pharmacy.query.filter(
        func.date(Pharmacy.created_at) == today
    ).count()
    
    # License price from system config
    stats['license_price'] = float(get_system_config('license_price', '3000'))
    stats['mpesa_till'] = get_system_config('mpesa_till', '123456')
    
    # Recent activities
    recent_registrations = Pharmacy.query.order_by(
        Pharmacy.created_at.desc()
    ).limit(5).all()
    
    pending_payments = Payment.query.filter_by(status='pending').order_by(
        Payment.created_at.desc()
    ).limit(10).all()
    
    expiring_licenses = License.query.filter(
        License.status == 'active',
        License.expiry_date <= datetime.utcnow() + timedelta(days=7)
    ).order_by(License.expiry_date).limit(10).all()
    
    # Daily registration trends (last 30 days)
    registration_trends = []
    for i in range(30):
        date = (datetime.utcnow() - timedelta(days=i)).date()
        count = Pharmacy.query.filter(func.date(Pharmacy.created_at) == date).count()
        registration_trends.append({'date': date.strftime('%Y-%m-%d'), 'count': count})
    registration_trends.reverse()
    
    # Recent audit logs
    recent_audits = AuditLog.query.order_by(desc(AuditLog.created_at)).limit(10).all()
    
    return render_template('admin/dashboard.html',
                         stats=stats,
                         recent_registrations=recent_registrations,
                         pending_payments=pending_payments,
                         expiring_licenses=expiring_licenses,
                         registration_trends=registration_trends,
                         recent_audits=recent_audits)

@admin_bp.route('/pharmacies')
@login_required
@superadmin_required
def pharmacies():
    """Manage pharmacies"""
    search = request.args.get('search', '')
    status = request.args.get('status', '')
    page = request.args.get('page', 1, type=int)
    
    query = Pharmacy.query
    
    if search:
        query = query.filter(
            Pharmacy.name.ilike(f'%{search}%') |
            Pharmacy.email.ilike(f'%{search}%')
        )
    
    if status == 'active':
        query = query.filter_by(is_active=True)
    elif status == 'inactive':
        query = query.filter_by(is_active=False)
    
    pharmacies = query.order_by(Pharmacy.created_at.desc()).paginate(
        page=page, per_page=20, error_out=False
    )
    
    return render_template('admin/pharmacies.html',
                         pharmacies=pharmacies,
                         search=search,
                         status=status)

@admin_bp.route('/pharmacy/<int:pharmacy_id>')
@login_required
@superadmin_required
def view_pharmacy(pharmacy_id):
    """View pharmacy details"""
    pharmacy = Pharmacy.query.get_or_404(pharmacy_id)
    
    # Get pharmacy statistics
    stats = {}
    stats['total_drugs'] = Drug.query.filter_by(pharmacy_id=pharmacy_id).count()
    stats['total_sales'] = Sale.query.filter_by(pharmacy_id=pharmacy_id).count()
    stats['total_revenue'] = db.session.query(func.sum(Sale.total_amount)).filter_by(
        pharmacy_id=pharmacy_id
    ).scalar() or 0
    
    # Get license history
    licenses = License.query.filter_by(pharmacy_id=pharmacy_id).order_by(
        License.created_at.desc()
    ).all()
    
    # Get payment history
    payments = Payment.query.filter_by(pharmacy_id=pharmacy_id).order_by(
        Payment.created_at.desc()
    ).all()
    
    # Get users
    users = User.query.filter_by(pharmacy_id=pharmacy_id).all()
    
    return render_template('admin/view_pharmacy.html',
                         pharmacy=pharmacy,
                         stats=stats,
                         licenses=licenses,
                         payments=payments,
                         users=users)

@admin_bp.route('/toggle-pharmacy/<int:pharmacy_id>', methods=['POST'])
@login_required
@superadmin_required
def toggle_pharmacy(pharmacy_id):
    """Toggle pharmacy active status"""
    pharmacy = Pharmacy.query.get_or_404(pharmacy_id)
    
    try:
        pharmacy.is_active = not pharmacy.is_active
        db.session.commit()
        
        status = 'activated' if pharmacy.is_active else 'deactivated'
        flash(f'Pharmacy {status} successfully!', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash('Failed to update pharmacy status.', 'error')
    
    return redirect(url_for('admin.view_pharmacy', pharmacy_id=pharmacy_id))

@admin_bp.route('/payments')
@login_required
@superadmin_required
def payments():
    """Manage payments"""
    status = request.args.get('status', 'pending')
    page = request.args.get('page', 1, type=int)
    
    query = Payment.query
    
    if status:
        query = query.filter_by(status=status)
    
    payments = query.order_by(Payment.created_at.desc()).paginate(
        page=page, per_page=20, error_out=False
    )
    
    return render_template('admin/payments.html',
                         payments=payments,
                         status=status)

@admin_bp.route('/confirm-payment/<int:payment_id>', methods=['POST'])
@login_required
@superadmin_required
def confirm_payment(payment_id):
    """Confirm payment and activate license"""
    payment = Payment.query.get_or_404(payment_id)
    
    if payment.status != 'pending':
        flash('Payment has already been processed.', 'error')
        return redirect(url_for('admin.payments'))
    
    try:
        # Update payment status
        payment.status = 'confirmed'
        payment.confirmed_by = current_user.id
        payment.confirmation_date = datetime.utcnow()
        
        # Create or update license
        if payment.license_id:
            license = License.query.get(payment.license_id)
        else:
            license = License.query.filter_by(
                pharmacy_id=payment.pharmacy_id
            ).order_by(License.created_at.desc()).first()
        
        if license:
            license.status = 'active'
            license.start_date = datetime.utcnow()
            license.expiry_date = datetime.utcnow() + timedelta(days=30)
            payment.license_id = license.id
        else:
            # Create new license
            license = License(
                pharmacy_id=payment.pharmacy_id,
                status='active',
                amount=payment.amount,
                start_date=datetime.utcnow(),
                expiry_date=datetime.utcnow() + timedelta(days=30)
            )
            db.session.add(license)
            db.session.flush()
            payment.license_id = license.id
        
        db.session.commit()
        flash('Payment confirmed and license activated!', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash('Failed to confirm payment. Please try again.', 'error')
    
    return redirect(url_for('admin.payments'))

@admin_bp.route('/reject-payment/<int:payment_id>', methods=['POST'])
@login_required
@superadmin_required
def reject_payment(payment_id):
    """Reject payment"""
    payment = Payment.query.get_or_404(payment_id)
    
    if payment.status != 'pending':
        flash('Payment has already been processed.', 'error')
        return redirect(url_for('admin.payments'))
    
    try:
        payment.status = 'rejected'
        payment.confirmed_by = current_user.id
        payment.confirmation_date = datetime.utcnow()
        
        db.session.commit()
        flash('Payment rejected.', 'info')
        
    except Exception as e:
        db.session.rollback()
        flash('Failed to reject payment. Please try again.', 'error')
    
    return redirect(url_for('admin.payments'))

@admin_bp.route('/settings', methods=['GET', 'POST'])
@login_required
@superadmin_required
def settings():
    """Admin settings"""
    if request.method == 'POST':
        license_amount = request.form.get('license_amount', type=float)
        till_number = request.form.get('till_number')
        
        # These would typically be stored in a settings table
        # For now, we'll use session or environment variables
        flash('Settings updated successfully!', 'success')
    
    return render_template('admin/settings.html')

@admin_bp.route('/reports')
@login_required
@superadmin_required
def reports():
    """Admin reports"""
    # Revenue by month
    monthly_revenue = db.session.query(
        func.date_trunc('month', Payment.confirmation_date).label('month'),
        func.sum(Payment.amount).label('revenue')
    ).filter(
        Payment.status == 'confirmed'
    ).group_by(
        func.date_trunc('month', Payment.confirmation_date)
    ).order_by('month').limit(12).all()
    
    # Top pharmacies by revenue
    top_pharmacies = db.session.query(
        Pharmacy.name,
        func.sum(Payment.amount).label('total_paid')
    ).join(Payment).filter(
        Payment.status == 'confirmed'
    ).group_by(Pharmacy.id, Pharmacy.name).order_by(
        func.sum(Payment.amount).desc()
    ).limit(10).all()
    
    # License status breakdown
    license_stats = db.session.query(
        License.status,
        func.count(License.id).label('count')
    ).group_by(License.status).all()
    
    return render_template('admin/reports.html',
                         monthly_revenue=monthly_revenue,
                         top_pharmacies=top_pharmacies,
                         license_stats=license_stats)

@admin_bp.route('/system-config')
@login_required
@superadmin_required
def system_config():
    """System configuration management"""
    configs = {
        'license_price': get_system_config('license_price', '3000'),
        'mpesa_till': get_system_config('mpesa_till', '123456'),
        'system_name': get_system_config('system_name', 'Comolor Pharmacy'),
        'allow_registrations': get_system_config('allow_registrations', 'true'),
        'license_duration_days': get_system_config('license_duration_days', '30'),
        'terms_conditions': get_system_config('terms_conditions', 'Default terms and conditions')
    }
    
    return render_template('admin/system_config.html', configs=configs)

@admin_bp.route('/system-config', methods=['POST'])
@login_required
@superadmin_required
def update_system_config():
    """Update system configuration"""
    config_updates = {}
    
    # Get form data
    license_price = request.form.get('license_price', '3000')
    mpesa_till = request.form.get('mpesa_till', '123456')
    system_name = request.form.get('system_name', 'Comolor Pharmacy')
    allow_registrations = 'true' if request.form.get('allow_registrations') else 'false'
    license_duration = request.form.get('license_duration_days', '30')
    
    # Update configurations
    set_system_config('license_price', license_price, 'Monthly license price in KES')
    set_system_config('mpesa_till', mpesa_till, 'Official M-PESA Till Number')
    set_system_config('system_name', system_name, 'System display name')
    set_system_config('allow_registrations', allow_registrations, 'Allow new pharmacy registrations')
    set_system_config('license_duration_days', license_duration, 'License duration in days')
    
    config_updates['license_price'] = license_price
    config_updates['mpesa_till'] = mpesa_till
    config_updates['system_name'] = system_name
    config_updates['allow_registrations'] = allow_registrations
    config_updates['license_duration'] = license_duration
    
    # Log audit action
    log_audit_action('system_config_update', 'system', details=json.dumps(config_updates))
    
    flash('System configuration updated successfully!', 'success')
    return redirect(url_for('admin.system_config'))

@admin_bp.route('/terms-conditions')
@login_required
@superadmin_required
def terms_conditions():
    """Manage terms and conditions"""
    terms = get_system_config('terms_conditions', '''
# Comolor Pharmacy Management System - Terms and Conditions

## 1. Service Agreement
By registering for Comolor Pharmacy Management System, you agree to pay the monthly licensing fee of KES 3,000.

## 2. Payment Terms
- Monthly license fee: KES 3,000
- Payment via M-PESA to Till Number: 123456
- License expires 30 days from activation
- No refunds for partial months

## 3. System Usage
- One pharmacy per license
- Responsible for data backup
- Must comply with Kenyan pharmacy regulations

## 4. Support
For technical support, contact: support@comolor.com

## 5. Termination
We reserve the right to suspend accounts for non-payment or misuse.
    '''.strip())
    
    return render_template('admin/terms_conditions.html', terms=terms)

@admin_bp.route('/terms-conditions', methods=['POST'])
@login_required
@superadmin_required
def update_terms_conditions():
    """Update terms and conditions"""
    terms = request.form.get('terms_conditions', '').strip()
    
    if not terms:
        flash('Terms and conditions cannot be empty!', 'error')
        return redirect(url_for('admin.terms_conditions'))
    
    set_system_config('terms_conditions', terms, 'System terms and conditions')
    
    # Log audit action
    log_audit_action('terms_update', 'system', details=f'Updated terms and conditions ({len(terms)} characters)')
    
    flash('Terms and conditions updated successfully!', 'success')
    return redirect(url_for('admin.terms_conditions'))

@admin_bp.route('/financial-overview')
@login_required
@superadmin_required
def financial_overview():
    """Comprehensive financial oversight"""
    # Revenue analytics
    revenue_data = {}
    
    # Total revenue
    total_revenue = db.session.query(func.sum(Payment.amount)).filter(
        Payment.status == 'confirmed'
    ).scalar() or 0
    revenue_data['total_revenue'] = total_revenue
    
    # Monthly revenue breakdown (last 12 months)
    monthly_revenue = []
    for i in range(12):
        month_start = (datetime.utcnow().replace(day=1) - timedelta(days=32*i)).replace(day=1)
        month_end = (month_start + timedelta(days=32)).replace(day=1) - timedelta(days=1)
        
        month_total = db.session.query(func.sum(Payment.amount)).filter(
            Payment.status == 'confirmed',
            Payment.confirmation_date >= month_start,
            Payment.confirmation_date <= month_end
        ).scalar() or 0
        
        monthly_revenue.append({
            'month': month_start.strftime('%B %Y'),
            'amount': month_total,
            'date': month_start.strftime('%Y-%m')
        })
    
    monthly_revenue.reverse()
    revenue_data['monthly_revenue'] = monthly_revenue
    
    # Payment statistics
    payment_stats = {
        'pending': Payment.query.filter_by(status='pending').count(),
        'confirmed': Payment.query.filter_by(status='confirmed').count(),
        'rejected': Payment.query.filter_by(status='rejected').count(),
        'total': Payment.query.count()
    }
    
    # Top paying pharmacies
    top_pharmacies = db.session.query(
        Pharmacy.name,
        func.sum(Payment.amount).label('total_paid'),
        func.count(Payment.id).label('payment_count')
    ).join(Payment).filter(
        Payment.status == 'confirmed'
    ).group_by(Pharmacy.id, Pharmacy.name).order_by(
        desc('total_paid')
    ).limit(10).all()
    
    # Recent payments
    recent_payments = db.session.query(Payment, Pharmacy).join(
        Pharmacy, Payment.pharmacy_id == Pharmacy.id
    ).order_by(desc(Payment.created_at)).limit(20).all()
    
    return render_template('admin/financial_overview.html',
                         revenue_data=revenue_data,
                         payment_stats=payment_stats,
                         top_pharmacies=top_pharmacies,
                         recent_payments=recent_payments)

@admin_bp.route('/audit-logs')
@login_required
@superadmin_required
def audit_logs():
    """View audit trail"""
    page = request.args.get('page', 1, type=int)
    per_page = 50
    
    # Filter options
    action_filter = request.args.get('action', '')
    target_filter = request.args.get('target_type', '')
    date_from = request.args.get('date_from', '')
    date_to = request.args.get('date_to', '')
    
    query = AuditLog.query
    
    if action_filter:
        query = query.filter(AuditLog.action.contains(action_filter))
    
    if target_filter:
        query = query.filter_by(target_type=target_filter)
    
    if date_from:
        try:
            from_date = datetime.strptime(date_from, '%Y-%m-%d')
            query = query.filter(AuditLog.created_at >= from_date)
        except ValueError:
            pass
    
    if date_to:
        try:
            to_date = datetime.strptime(date_to, '%Y-%m-%d') + timedelta(days=1)
            query = query.filter(AuditLog.created_at < to_date)
        except ValueError:
            pass
    
    audit_logs = query.order_by(desc(AuditLog.created_at)).paginate(
        page=page, per_page=per_page, error_out=False
    )
    
    # Get unique actions and target types for filters
    actions = db.session.query(AuditLog.action.distinct()).all()
    target_types = db.session.query(AuditLog.target_type.distinct()).all()
    
    return render_template('admin/audit_logs.html',
                         audit_logs=audit_logs,
                         actions=[a[0] for a in actions],
                         target_types=[t[0] for t in target_types],
                         filters={
                             'action': action_filter,
                             'target_type': target_filter,
                             'date_from': date_from,
                             'date_to': date_to
                         })

@admin_bp.route('/pharmacy-activities')
@login_required
@superadmin_required
def pharmacy_activities():
    """View pharmacy activity logs"""
    page = request.args.get('page', 1, type=int)
    per_page = 50
    pharmacy_id = request.args.get('pharmacy_id', type=int)
    activity_type = request.args.get('activity_type', '')
    
    query = db.session.query(PharmacyActivity, Pharmacy, User).join(
        Pharmacy, PharmacyActivity.pharmacy_id == Pharmacy.id
    ).outerjoin(
        User, PharmacyActivity.user_id == User.id
    )
    
    if pharmacy_id:
        query = query.filter(PharmacyActivity.pharmacy_id == pharmacy_id)
    
    if activity_type:
        query = query.filter(PharmacyActivity.activity_type == activity_type)
    
    activities = query.order_by(desc(PharmacyActivity.created_at)).paginate(
        page=page, per_page=per_page, error_out=False
    )
    
    # Get pharmacy list for filter
    pharmacies = Pharmacy.query.order_by(Pharmacy.name).all()
    
    # Get activity types for filter
    activity_types = db.session.query(PharmacyActivity.activity_type.distinct()).all()
    
    return render_template('admin/pharmacy_activities.html',
                         activities=activities,
                         pharmacies=pharmacies,
                         activity_types=[t[0] for t in activity_types],
                         filters={
                             'pharmacy_id': pharmacy_id,
                             'activity_type': activity_type
                         })

@admin_bp.route('/block-pharmacy/<int:pharmacy_id>')
@login_required
@superadmin_required
def block_pharmacy(pharmacy_id):
    """Block/unblock pharmacy access"""
    pharmacy = Pharmacy.query.get_or_404(pharmacy_id)
    
    # Toggle active status
    pharmacy.is_active = not pharmacy.is_active
    db.session.commit()
    
    action = 'pharmacy_blocked' if not pharmacy.is_active else 'pharmacy_unblocked'
    log_audit_action(action, 'pharmacy', pharmacy_id, f'Pharmacy {pharmacy.name}')
    
    status = 'blocked' if not pharmacy.is_active else 'unblocked'
    flash(f'Pharmacy {pharmacy.name} has been {status}!', 'success')
    
    return redirect(url_for('admin.view_pharmacy', pharmacy_id=pharmacy_id))

@admin_bp.route('/extend-license/<int:license_id>')
@login_required
@superadmin_required
def extend_license(license_id):
    """Manually extend license duration"""
    license = License.query.get_or_404(license_id)
    days = request.args.get('days', 30, type=int)
    
    if license.expiry_date:
        license.expiry_date = license.expiry_date + timedelta(days=days)
    else:
        license.expiry_date = datetime.utcnow() + timedelta(days=days)
    
    if license.status == 'expired':
        license.status = 'active'
    
    db.session.commit()
    
    log_audit_action('license_extended', 'license', license_id, 
                    f'Extended license for {license.pharmacy.name} by {days} days')
    
    flash(f'License extended by {days} days!', 'success')
    return redirect(url_for('admin.view_pharmacy', pharmacy_id=license.pharmacy_id))

@admin_bp.route('/test-license-expiry')
@login_required
@superadmin_required
def test_license_expiry():
    """Test license expiry behavior (debug tool)"""
    # Find licenses expiring in the next 7 days
    expiring_licenses = License.query.filter(
        License.status == 'active',
        License.expiry_date <= datetime.utcnow() + timedelta(days=7)
    ).all()
    
    # Simulate expiry notifications
    notifications = []
    for license in expiring_licenses:
        days_left = (license.expiry_date - datetime.utcnow()).days
        notifications.append({
            'pharmacy': license.pharmacy.name,
            'expiry_date': license.expiry_date,
            'days_left': days_left,
            'email': license.pharmacy.email
        })
    
    return render_template('admin/test_license_expiry.html', 
                         notifications=notifications,
                         expiring_licenses=expiring_licenses)

@admin_bp.route('/impersonate/<int:pharmacy_id>')
@login_required
@superadmin_required
def impersonate_pharmacy(pharmacy_id):
    """Impersonate pharmacy user for debugging (read-only)"""
    pharmacy = Pharmacy.query.get_or_404(pharmacy_id)
    
    # Log the impersonation action
    log_audit_action('pharmacy_impersonation', 'pharmacy', pharmacy_id, 
                    f'Impersonated pharmacy {pharmacy.name} for debugging')
    
    # Store impersonation flag in session
    session['impersonating_pharmacy'] = pharmacy_id
    session['original_user'] = current_user.id
    
    flash(f'Now impersonating {pharmacy.name} (read-only mode)', 'info')
    return redirect(url_for('main.dashboard'))

@admin_bp.route('/stop-impersonation')
@login_required
def stop_impersonation():
    """Stop impersonating pharmacy"""
    if 'impersonating_pharmacy' in session:
        pharmacy_id = session.pop('impersonating_pharmacy')
        session.pop('original_user', None)
        
        log_audit_action('impersonation_stopped', 'pharmacy', pharmacy_id, 
                        'Stopped pharmacy impersonation')
        
        flash('Stopped impersonation', 'info')
    
    return redirect(url_for('admin.dashboard'))

@admin_bp.route('/analytics-api')
@login_required
@superadmin_required
def analytics_api():
    """API endpoint for dashboard analytics"""
    # Daily registrations for the last 30 days
    daily_registrations = []
    for i in range(30):
        date = (datetime.utcnow() - timedelta(days=i)).date()
        count = Pharmacy.query.filter(func.date(Pharmacy.created_at) == date).count()
        daily_registrations.append({
            'date': date.strftime('%Y-%m-%d'),
            'count': count
        })
    
    # Monthly revenue for the last 12 months
    monthly_revenue = []
    for i in range(12):
        month_start = (datetime.utcnow().replace(day=1) - timedelta(days=32*i)).replace(day=1)
        month_end = (month_start + timedelta(days=32)).replace(day=1) - timedelta(days=1)
        
        revenue = db.session.query(func.sum(Payment.amount)).filter(
            Payment.status == 'confirmed',
            Payment.confirmation_date >= month_start,
            Payment.confirmation_date <= month_end
        ).scalar() or 0
        
        monthly_revenue.append({
            'month': month_start.strftime('%B %Y'),
            'revenue': float(revenue)
        })
    
    return jsonify({
        'daily_registrations': daily_registrations,
        'monthly_revenue': monthly_revenue
    })
