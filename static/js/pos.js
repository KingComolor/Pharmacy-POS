// Comolor Pharmacy - Point of Sale JavaScript
// Handles drug search, cart management, and checkout functionality

class PharmacyPOS {
    constructor() {
        this.cart = {};
        this.searchTimeout = null;
        this.currentSearchResults = [];
        
        this.initializeEventListeners();
        this.loadExistingCart();
    }
    
    initializeEventListeners() {
        // Drug search functionality
        const drugSearchInput = document.getElementById('drugSearch');
        if (drugSearchInput) {
            drugSearchInput.addEventListener('input', (e) => {
                this.handleDrugSearch(e.target.value);
            });
            
            // Clear search results when input is cleared
            drugSearchInput.addEventListener('keyup', (e) => {
                if (e.target.value === '') {
                    this.clearSearchResults();
                }
            });
        }
        
        // Checkout button
        const checkoutBtn = document.getElementById('checkoutBtn');
        if (checkoutBtn) {
            checkoutBtn.addEventListener('click', () => {
                this.openCheckoutModal();
            });
        }
        
        // Payment method change handler
        const paymentMethodSelect = document.getElementById('payment_method');
        if (paymentMethodSelect) {
            paymentMethodSelect.addEventListener('change', (e) => {
                this.toggleMpesaReference(e.target.value);
            });
        }
        
        // Checkout form submission
        const checkoutForm = document.getElementById('checkoutForm');
        if (checkoutForm) {
            checkoutForm.addEventListener('submit', (e) => {
                if (!this.validateCheckoutForm()) {
                    e.preventDefault();
                }
            });
        }
        
        // Initialize cart display
        this.updateCartDisplay();
    }
    
    handleDrugSearch(query) {
        // Clear previous timeout
        if (this.searchTimeout) {
            clearTimeout(this.searchTimeout);
        }
        
        // If query is too short, clear results
        if (query.length < 2) {
            this.clearSearchResults();
            return;
        }
        
        // Debounce search requests
        this.searchTimeout = setTimeout(() => {
            this.searchDrugs(query);
        }, 300);
    }
    
    async searchDrugs(query) {
        try {
            const response = await fetch(`/inventory/search?q=${encodeURIComponent(query)}`);
            const drugs = await response.json();
            this.displaySearchResults(drugs);
        } catch (error) {
            console.error('Search error:', error);
            this.showSearchError();
        }
    }
    
    displaySearchResults(drugs) {
        const resultsContainer = document.getElementById('searchResults');
        if (!resultsContainer) return;
        
        if (drugs.length === 0) {
            resultsContainer.innerHTML = `
                <div class="text-center py-3 text-muted">
                    <i class="fas fa-search"></i>
                    <p class="mb-0">No drugs found</p>
                </div>
            `;
            return;
        }
        
        let resultsHtml = '';
        drugs.forEach(drug => {
            resultsHtml += `
                <div class="search-result-item" onclick="pos.addToCart(${drug.id}, '${drug.name}', ${drug.price}, ${drug.quantity})">
                    <div class="d-flex justify-content-between align-items-start">
                        <div class="flex-grow-1">
                            <h6 class="mb-1">${drug.name}</h6>
                            ${drug.barcode ? `<small class="text-muted">Barcode: ${drug.barcode}</small>` : ''}
                        </div>
                        <div class="text-end">
                            <div class="fw-bold text-primary">KES ${drug.price.toFixed(2)}</div>
                            <small class="text-muted">${drug.quantity} in stock</small>
                        </div>
                    </div>
                </div>
            `;
        });
        
        resultsContainer.innerHTML = resultsHtml;
        this.currentSearchResults = drugs;
    }
    
    clearSearchResults() {
        const resultsContainer = document.getElementById('searchResults');
        if (resultsContainer) {
            resultsContainer.innerHTML = `
                <p class="text-muted text-center">Start typing to search for drugs...</p>
            `;
        }
        this.currentSearchResults = [];
    }
    
    showSearchError() {
        const resultsContainer = document.getElementById('searchResults');
        if (resultsContainer) {
            resultsContainer.innerHTML = `
                <div class="text-center py-3 text-danger">
                    <i class="fas fa-exclamation-triangle"></i>
                    <p class="mb-0">Search failed. Please try again.</p>
                </div>
            `;
        }
    }
    
    async addToCart(drugId, drugName, price, availableQuantity, quantity = 1) {
        try {
            const response = await fetch('/sales/add-to-cart', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    drug_id: drugId,
                    quantity: quantity
                })
            });
            
            const result = await response.json();
            
            if (result.success) {
                this.cart = result.cart;
                this.updateCartDisplay();
                this.showToast('Item added to cart', 'success');
                
                // Clear search input and results
                const searchInput = document.getElementById('drugSearch');
                if (searchInput) {
                    searchInput.value = '';
                }
                this.clearSearchResults();
            } else {
                this.showToast(result.message || 'Failed to add item to cart', 'error');
            }
        } catch (error) {
            console.error('Add to cart error:', error);
            this.showToast('Failed to add item to cart', 'error');
        }
    }
    
    async removeFromCart(drugId) {
        try {
            const response = await fetch('/sales/remove-from-cart', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    drug_id: drugId
                })
            });
            
            const result = await response.json();
            
            if (result.success) {
                this.cart = result.cart;
                this.updateCartDisplay();
                this.showToast('Item removed from cart', 'success');
            } else {
                this.showToast(result.message || 'Failed to remove item', 'error');
            }
        } catch (error) {
            console.error('Remove from cart error:', error);
            this.showToast('Failed to remove item', 'error');
        }
    }
    
    async updateCartQuantity(drugId, newQuantity) {
        if (newQuantity <= 0) {
            return this.removeFromCart(drugId);
        }
        
        try {
            const response = await fetch('/sales/update-cart', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    drug_id: drugId,
                    quantity: newQuantity
                })
            });
            
            const result = await response.json();
            
            if (result.success) {
                this.cart = result.cart;
                this.updateCartDisplay();
            } else {
                this.showToast(result.message || 'Failed to update quantity', 'error');
            }
        } catch (error) {
            console.error('Update cart error:', error);
            this.showToast('Failed to update quantity', 'error');
        }
    }
    
    updateCartDisplay() {
        const cartItemsContainer = document.getElementById('cartItems');
        const cartCountElement = document.getElementById('cartCount');
        const cartTotalElement = document.getElementById('cartTotal');
        const checkoutBtn = document.getElementById('checkoutBtn');
        
        const cartItems = Object.values(this.cart);
        const cartCount = cartItems.reduce((sum, item) => sum + item.quantity, 0);
        const cartTotal = cartItems.reduce((sum, item) => sum + item.total, 0);
        
        // Update cart count
        if (cartCountElement) {
            cartCountElement.textContent = cartCount;
        }
        
        // Update cart total
        if (cartTotalElement) {
            cartTotalElement.textContent = `KES ${cartTotal.toFixed(2)}`;
        }
        
        // Enable/disable checkout button
        if (checkoutBtn) {
            checkoutBtn.disabled = cartCount === 0;
        }
        
        // Update cart items display
        if (cartItemsContainer) {
            if (cartItems.length === 0) {
                cartItemsContainer.innerHTML = '<p class="text-muted text-center">Cart is empty</p>';
            } else {
                let cartHtml = '';
                Object.entries(this.cart).forEach(([drugId, item]) => {
                    cartHtml += `
                        <div class="cart-item">
                            <div class="d-flex justify-content-between align-items-start mb-2">
                                <div class="flex-grow-1">
                                    <h6 class="mb-1">${item.name}</h6>
                                    <small class="text-muted">KES ${item.price.toFixed(2)} each</small>
                                </div>
                                <button type="button" class="btn btn-sm btn-outline-danger" 
                                        onclick="pos.removeFromCart(${drugId})" title="Remove item">
                                    <i class="fas fa-trash"></i>
                                </button>
                            </div>
                            <div class="d-flex justify-content-between align-items-center">
                                <div class="quantity-controls">
                                    <button type="button" class="quantity-btn" 
                                            onclick="pos.updateCartQuantity(${drugId}, ${item.quantity - 1})">
                                        <i class="fas fa-minus"></i>
                                    </button>
                                    <span class="mx-2 fw-bold">${item.quantity}</span>
                                    <button type="button" class="quantity-btn" 
                                            onclick="pos.updateCartQuantity(${drugId}, ${item.quantity + 1})">
                                        <i class="fas fa-plus"></i>
                                    </button>
                                </div>
                                <div class="fw-bold text-primary">KES ${item.total.toFixed(2)}</div>
                            </div>
                        </div>
                    `;
                });
                cartItemsContainer.innerHTML = cartHtml;
            }
        }
    }
    
    async loadExistingCart() {
        try {
            const response = await fetch('/sales/get-cart');
            const result = await response.json();
            
            if (result.cart) {
                this.cart = result.cart;
                this.updateCartDisplay();
            }
        } catch (error) {
            console.error('Load cart error:', error);
        }
    }
    
    openCheckoutModal() {
        if (Object.keys(this.cart).length === 0) {
            this.showToast('Cart is empty', 'error');
            return;
        }
        
        this.updateCheckoutSummary();
        const checkoutModal = new bootstrap.Modal(document.getElementById('checkoutModal'));
        checkoutModal.show();
    }
    
    updateCheckoutSummary() {
        const summaryContainer = document.getElementById('checkoutSummary');
        const totalContainer = document.getElementById('checkoutTotal');
        
        if (!summaryContainer || !totalContainer) return;
        
        const cartItems = Object.values(this.cart);
        const cartTotal = cartItems.reduce((sum, item) => sum + item.total, 0);
        
        let summaryHtml = '';
        cartItems.forEach(item => {
            summaryHtml += `
                <div class="d-flex justify-content-between">
                    <span>${item.name} × ${item.quantity}</span>
                    <span>KES ${item.total.toFixed(2)}</span>
                </div>
            `;
        });
        
        summaryContainer.innerHTML = summaryHtml;
        totalContainer.textContent = `KES ${cartTotal.toFixed(2)}`;
    }
    
    toggleMpesaReference(paymentMethod) {
        const mpesaReferenceDiv = document.getElementById('mpesaReferenceDiv');
        const mpesaReferenceInput = document.getElementById('mpesa_reference');
        
        if (mpesaReferenceDiv && mpesaReferenceInput) {
            if (paymentMethod === 'mpesa') {
                mpesaReferenceDiv.style.display = 'block';
                mpesaReferenceInput.required = true;
            } else {
                mpesaReferenceDiv.style.display = 'none';
                mpesaReferenceInput.required = false;
                mpesaReferenceInput.value = '';
            }
        }
    }
    
    validateCheckoutForm() {
        const paymentMethod = document.getElementById('payment_method').value;
        const mpesaReference = document.getElementById('mpesa_reference').value;
        
        if (!paymentMethod) {
            this.showToast('Please select a payment method', 'error');
            return false;
        }
        
        if (paymentMethod === 'mpesa' && !mpesaReference.trim()) {
            this.showToast('M-PESA reference is required for M-PESA payments', 'error');
            return false;
        }
        
        if (Object.keys(this.cart).length === 0) {
            this.showToast('Cart is empty', 'error');
            return false;
        }
        
        return true;
    }
    
    showToast(message, type = 'info') {
        // Create toast element
        const toastHtml = `
            <div class="toast align-items-center text-white bg-${type === 'error' ? 'danger' : type === 'success' ? 'success' : 'primary'} border-0" role="alert" aria-live="assertive" aria-atomic="true">
                <div class="d-flex">
                    <div class="toast-body">
                        <i class="fas fa-${type === 'error' ? 'exclamation-triangle' : type === 'success' ? 'check-circle' : 'info-circle'} me-2"></i>
                        ${message}
                    </div>
                    <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast" aria-label="Close"></button>
                </div>
            </div>
        `;
        
        // Create or get toast container
        let toastContainer = document.getElementById('toast-container');
        if (!toastContainer) {
            toastContainer = document.createElement('div');
            toastContainer.id = 'toast-container';
            toastContainer.className = 'toast-container position-fixed top-0 end-0 p-3';
            toastContainer.style.zIndex = '1055';
            document.body.appendChild(toastContainer);
        }
        
        // Add toast to container
        const toastElement = document.createElement('div');
        toastElement.innerHTML = toastHtml;
        const toast = toastElement.firstElementChild;
        toastContainer.appendChild(toast);
        
        // Initialize and show toast
        const bsToast = new bootstrap.Toast(toast, {
            autohide: true,
            delay: type === 'error' ? 5000 : 3000
        });
        bsToast.show();
        
        // Remove toast element after it's hidden
        toast.addEventListener('hidden.bs.toast', () => {
            toast.remove();
        });
    }
    
    // Keyboard shortcuts
    handleKeyboardShortcuts(event) {
        // Ctrl/Cmd + F to focus search
        if ((event.ctrlKey || event.metaKey) && event.key === 'f') {
            event.preventDefault();
            const searchInput = document.getElementById('drugSearch');
            if (searchInput) {
                searchInput.focus();
            }
        }
        
        // ESC to clear search
        if (event.key === 'Escape') {
            const searchInput = document.getElementById('drugSearch');
            if (searchInput && document.activeElement === searchInput) {
                searchInput.value = '';
                this.clearSearchResults();
                searchInput.blur();
            }
        }
        
        // Enter to add first search result to cart
        if (event.key === 'Enter') {
            const searchInput = document.getElementById('drugSearch');
            if (searchInput && document.activeElement === searchInput && this.currentSearchResults.length > 0) {
                event.preventDefault();
                const firstResult = this.currentSearchResults[0];
                this.addToCart(firstResult.id, firstResult.name, firstResult.price, firstResult.quantity);
            }
        }
    }
}

// Initialize POS system when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    // Create global POS instance
    window.pos = new PharmacyPOS();
    
    // Add keyboard shortcuts
    document.addEventListener('keydown', (event) => {
        window.pos.handleKeyboardShortcuts(event);
    });
    
    // Auto-focus search input
    const searchInput = document.getElementById('drugSearch');
    if (searchInput) {
        searchInput.focus();
    }
    
    // Initialize tooltips
    const tooltipTriggerList = [].slice.call(document.querySelectorAll('[title]'));
    tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });
});

// Utility functions for number formatting
function formatCurrency(amount) {
    return `KES ${parseFloat(amount).toFixed(2)}`;
}

function formatNumber(number) {
    return parseFloat(number).toLocaleString();
}

// Export for potential module use
if (typeof module !== 'undefined' && module.exports) {
    module.exports = PharmacyPOS;
}
