/**
 * School Management System — Client-side utilities
 */

document.addEventListener('DOMContentLoaded', () => {
    // Auto-dismiss success alerts after 5 seconds
    document.querySelectorAll('[class*="bg-emerald-50"]').forEach(alert => {
        setTimeout(() => {
            alert.style.transition = 'all 0.3s ease';
            alert.style.opacity = '0';
            alert.style.transform = 'translateY(-10px)';
            setTimeout(() => alert.remove(), 300);
        }, 5000);
    });

    // Add loading state to forms on submit
    document.querySelectorAll('form').forEach(form => {
        form.addEventListener('submit', (e) => {
            const btn = form.querySelector('button[type="submit"]');
            if (btn && !btn.disabled) {
                btn.disabled = true;
                const originalText = btn.innerHTML;
                btn.innerHTML = `<span class="flex items-center justify-center gap-2"><span class="spinner"></span> Processing...</span>`;
                // Re-enable after 10 seconds as fallback
                setTimeout(() => {
                    btn.disabled = false;
                    btn.innerHTML = originalText;
                }, 10000);
            }
        });
    });

    // Keyboard shortcut: Escape to go back
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') {
            const backLink = document.querySelector('a[href="/dashboard"]');
            if (backLink) backLink.click();
        }
    });

    // Add active states to bottom nav items
    const currentPath = window.location.pathname;
    document.querySelectorAll('nav a').forEach(link => {
        if (link.getAttribute('href') === currentPath) {
            link.classList.add('font-semibold');
        }
    });

    // Smooth scroll to top on page load
    window.scrollTo({ top: 0, behavior: 'instant' });
});

/**
 * Toggle all checkboxes in a container
 */
function toggleAll(containerId, checked) {
    const container = document.getElementById(containerId);
    if (container) {
        container.querySelectorAll('input[type="checkbox"]').forEach(cb => {
            cb.checked = checked;
            cb.dispatchEvent(new Event('change'));
        });
    }
}

/**
 * Confirm before destructive actions
 */
function confirmAction(message) {
    return confirm(message || 'Are you sure?');
}
