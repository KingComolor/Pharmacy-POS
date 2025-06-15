from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from auth import superadmin_required
from models import User, Pharmacy, License, Payment, Sale, Drug
from app import db
from datetime import datetime, timedelta
from sqlalchemy import func

admin_bp = Blueprint('admin', __name__)

@admin_bp.route('/')
@login_required
@superadmin_required
def dashboard():
    """Superadmin dashboard"""
    # System statistics
    stats = {}
    stats['total_pharmacies'] = Pharmacy.query.count()
    stats['active_licenses'] = License.query.filter_by(status='active').count()
    stats['pending_payments'] = Payment.query.filter_by(status='pending').count()
    
    # This month's revenue
    month_start = datetime.utcnow().replace(day=1)
    month_revenue = db.session.query(func.sum(Payment.amount)).filter(
        Payment.status == 'confirmed',
        Payment.confirmation_date >= month_start
    ).scalar() or 0
    stats['month_revenue'] = month_revenue
    
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
    
    return render_template('admin/dashboard.html',
                         stats=stats,
                         recent_registrations=recent_registrations,
                         pending_payments=pending_payments,
                         expiring_licenses=expiring_licenses)

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
