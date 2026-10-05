const formatStatus = (status) => {
    if (!status) return '<span class="badge">Unknown</span>';
    switch (status.toLowerCase()) {
        case 'requested to the authority':
            return '<span class="badge badge-pending">Requested to Authority</span>';
        case 'assigned personnel':
            return '<span class="badge badge-active" style="background-color:rgba(139,92,246,.12);color:#a78bfa;border-color:rgba(139,92,246,.35);">Assigned Personnel</span>';
        case 'work on going':
            return '<span class="badge badge-active">Work On Going</span>';
        case 'work done':
            return '<span class="badge badge-resolved">Work Done</span>';
        default:
            return `<span class="badge">${status}</span>`;
    }
};

const formatDate = (ds) => {
    if (!ds) return '';
    const opts = { year: 'numeric', month: 'short', day: 'numeric' };
    return new Date(ds).toLocaleDateString(undefined, opts);
};

const showError = (elId, msg) => {
    const el = document.getElementById(elId);
    if (el) { el.textContent = msg; el.style.display = 'block'; }
};

const hideError = (elId) => {
    const el = document.getElementById(elId);
    if (el) el.style.display = 'none';
};


const api = async (endpoint, method = 'GET', body = null) => {
    const opts = {
        method,
        credentials: 'include',
    };

    if (body) {
        if (body instanceof FormData) {
            opts.body = body;
        } else {
            opts.headers = { 'Content-Type': 'application/json' };
            opts.body = JSON.stringify(body);
        }
    }

    const res = await fetch(endpoint, opts);
    const data = await res.json();
    if (!res.ok) throw data;
    return data;
};


const getCurrentUser = () => {
    try { return JSON.parse(localStorage.getItem('cityserve_user')); }
    catch { return null; }
};

const requireAuth = async (allowedRoles = ['user', 'authority']) => {
    try {
        const { user } = await api('/api/auth/me');
        if (!user) throw new Error('not logged in');
        localStorage.setItem('cityserve_user', JSON.stringify(user));
        if (!allowedRoles.includes(user.role)) {
            window.location.href = user.role === 'authority'
                ? '/authority_dashboard.html' : '/home.html';
            return null;
        }
        return user;
    } catch {
        localStorage.removeItem('cityserve_user');
        window.location.href = '/';
        return null;
    }
};

const updateNavbarAuth = () => {
    const nav = document.querySelector('.nav-links');
    if (!nav) return;

    nav.querySelectorAll('.nav-auth-injected').forEach(el => el.remove());

    const user = getCurrentUser();
    if (user) {
        const dashHref = user.role === 'authority' ? '/authority_dashboard.html' : '/dashboard.html';
        const initials = (user.name || 'U').substring(0, 2).toUpperCase();
        const label = user.role === 'authority' ? user.department : 'Citizen';

        const block = document.createElement('div');
        block.className = 'nav-auth-injected';
        block.style.cssText = 'display:flex;align-items:center;gap:.5rem;margin-left:1rem;padding-left:1.5rem;border-left:1px solid var(--border-color);';
        block.innerHTML = `
            <a href="${dashHref}" style="text-decoration:none;">
                <div style="width:32px;height:32px;border-radius:50%;background:linear-gradient(135deg,var(--primary-color),var(--success));color:#fff;display:flex;align-items:center;justify-content:center;font-weight:700;font-size:.8rem;">${initials}</div>
            </a>
            <div style="display:flex;flex-direction:column;line-height:1.2;">
                <span style="font-size:.875rem;font-weight:600;">${user.name}</span>
                <span style="font-size:.65rem;color:var(--text-secondary);">${label}</span>
            </div>
            <a href="#" id="logoutBtn" class="nav-auth-injected" style="font-size:.875rem;margin-left:.75rem;color:var(--text-secondary);">Logout</a>
        `;
        nav.appendChild(block);

        document.getElementById('logoutBtn')?.addEventListener('click', async (e) => {
            e.preventDefault();
            await api('/api/auth/logout', 'POST').catch(() => { });
            localStorage.removeItem('cityserve_user');
            window.location.href = '/';
        });
    } else {
        const loginLink = document.createElement('a');
        loginLink.href = '/';
        loginLink.className = 'btn btn-outline nav-auth-injected';
        loginLink.style.cssText = 'padding:.25rem .75rem;margin-left:1rem;';
        loginLink.textContent = 'Login';

        const regLink = document.createElement('a');
        regLink.href = '/register.html';
        regLink.className = 'btn btn-primary nav-auth-injected';
        regLink.style.cssText = 'padding:.25rem .75rem;margin-left:.5rem;';
        regLink.textContent = 'Register';

        nav.appendChild(loginLink);
        nav.appendChild(regLink);
    }
};



document.addEventListener('DOMContentLoaded', async () => {


    if (!document.querySelector('link[href*="fonts.googleapis"]')) {
        const fl = document.createElement('link');
        fl.rel = 'stylesheet';
        fl.href = 'https://fonts.googleapis.com/css2?family=Lora:wght@400;600;700&family=Source+Sans+3:wght@400;500;600&display=swap';
        document.head.appendChild(fl);
    }

    updateNavbarAuth();

    const path = window.location.pathname;

    const loginForm = document.getElementById('unifiedLoginForm');
    if (loginForm) {
        loginForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            hideError('loginError');
            const email = document.getElementById('username').value.trim();
            const password = document.getElementById('password').value;
            const role = document.getElementById('loginRole').value;

            try {
                const { user } = await api('/api/auth/login', 'POST', { email, password, role });
                localStorage.setItem('cityserve_user', JSON.stringify(user));
                window.location.href = user.role === 'authority'
                    ? '/authority_dashboard.html' : '/home.html';
            } catch (err) {
                showError('loginError', err.error || 'Login failed. Please check your credentials.');
            }
        });
    }


    const registerForm = document.getElementById('registerForm');
    if (registerForm) {
        registerForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            hideError('registerError');
            const name = document.getElementById('fullname').value.trim();
            const email = document.getElementById('regEmail').value.trim();
            const password = document.getElementById('password').value;
            const phone = document.getElementById('phone')?.value.trim() || '';

            try {
                const { user } = await api('/api/auth/register', 'POST', { name, email, password, phone });
                localStorage.setItem('cityserve_user', JSON.stringify(user));
                window.location.href = '/home.html';
            } catch (err) {
                showError('registerError', err.error || 'Registration failed.');
            }
        });
    }

    if (path.includes('home.html')) {
        const user = await requireAuth(['user']);
        if (user) updateNavbarAuth();
    }

    const requestForm = document.getElementById('requestForm');
    if (requestForm) {
        const user = await requireAuth(['user']);
        if (!user) return;
        updateNavbarAuth();

        requestForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            hideError('requestError');

            const category = document.getElementById('type').value;
            const description = document.getElementById('description').value.trim();
            const location = document.getElementById('location').value.trim();
            const lat = parseFloat(document.getElementById('lat')?.value) || null;
            const lng = parseFloat(document.getElementById('lng')?.value) || null;

            const formData = new FormData();
            formData.append('category', category);
            formData.append('description', description);
            formData.append('location', location);
            if (lat !== null) formData.append('lat', lat);
            if (lng !== null) formData.append('lng', lng);

            const imageFile = document.getElementById('imageFile')?.files[0];
            if (imageFile) {
                formData.append('image', imageFile);
            }

            if (!location) {
                showError('requestError', 'Please select a location on the map.');
                return;
            }

            try {
                const { issue } = await api('/api/issues', 'POST', formData);
                document.querySelector('.card').innerHTML = `
                    <div class="text-center animate-fade-in" style="padding:2rem;">
                        <svg style="width:64px;height:64px;color:var(--success);margin:0 auto 1rem;" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"/></svg>
                        <h2>Request Submitted!</h2>
                        <p>Your request <strong>${issue.issue_number}</strong> has been lodged.<br>Track it from your dashboard.</p>
                        <a href="/dashboard.html" class="btn btn-primary mt-3">Go to Dashboard</a>
                    </div>`;
            } catch (err) {
                showError('requestError', err.error || 'Failed to submit request.');
            }
        });
    }


    const rateForm = document.getElementById('rateForm');
    if (rateForm) {
        const user = await requireAuth(['user']);
        if (!user) return;
        updateNavbarAuth();

        const params = new URLSearchParams(window.location.search);
        const issueParam = params.get('issue');
        if (issueParam) {
            const refInput = document.getElementById('rateRequestId');
            if (refInput) refInput.value = issueParam;
        }

        const stars = document.querySelectorAll('.star-rating svg');
        let selectedRating = 0;

        const highlightStars = (n) => {
            stars.forEach(s => {
                const fill = +s.getAttribute('data-value') <= +n ? '#c9a227' : 'none';
                s.style.fill = fill;
                s.style.color = fill === 'none' ? 'currentColor' : fill;
            });
        };

        stars.forEach(star => {
            star.addEventListener('mouseover', () => highlightStars(star.getAttribute('data-value')));
            star.addEventListener('mouseout', () => highlightStars(selectedRating));
            star.addEventListener('click', () => {
                selectedRating = star.getAttribute('data-value');
                document.getElementById('ratingValue').value = selectedRating;
                highlightStars(selectedRating);
            });
        });

        rateForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            hideError('rateError');
            if (!selectedRating || selectedRating === 0) {
                showError('rateError', 'Please select a star rating.');
                return;
            }

            const issueRef = document.getElementById('rateRequestId')?.value.trim();
            const comments = document.getElementById('feedback')?.value.trim() || '';

            try {
                let issueId = issueRef;
                if (isNaN(issueRef)) {
                    const { issue } = await api(`/api/issues/${issueRef}`);
                    issueId = issue.id;
                }
                await api('/api/feedback', 'POST', { issue_id: issueId, rating: selectedRating, comments });

                document.querySelector('.card').innerHTML = `
                    <div class="text-center animate-fade-in" style="padding:2rem;">
                        <svg style="width:64px;height:64px;color:var(--warning);margin:0 auto 1rem;" fill="currentColor" viewBox="0 0 20 20"><path d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.07 3.292a1 1 0 00.95.69h3.462c.969 0 1.371 1.24.588 1.81l-2.8 2.034a1 1 0 00-.364 1.118l1.07 3.292c.3.921-.755 1.688-1.54 1.118l-2.8-2.034a1 1 0 00-1.175 0l-2.8 2.034c-.784.57-1.838-.197-1.539-1.118l1.07-3.292a1 1 0 00-.364-1.118L2.98 8.72c-.783-.57-.38-1.81.588-1.81h3.461a1 1 0 00.951-.69l1.07-3.292z"/></svg>
                        <h2>Thank You!</h2>
                        <p>Your feedback helps us improve municipal services.</p>
                        <a href="/home.html" class="btn btn-primary mt-3">Back to Home</a>
                    </div>`;
            } catch (err) {
                showError('rateError', err.error || 'Failed to submit feedback.');
            }
        });
    }
});
