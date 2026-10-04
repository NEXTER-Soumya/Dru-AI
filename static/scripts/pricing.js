// Dynamic Pricing Period Toggle Handler
document.querySelectorAll('.toggle-btn').forEach(button => {
    button.addEventListener('click', function() {
        // Switch active states on buttons
        document.querySelectorAll('.toggle-btn').forEach(btn => btn.classList.remove('active'));
        this.classList.add('active');

        const period = this.getAttribute('data-period');
        const priceElement = document.querySelector('.price-val');

        if (priceElement) {
            if (period === 'yearly') {
                priceElement.textContent = priceElement.getAttribute('data-yearly');
            } else {
                priceElement.textContent = priceElement.getAttribute('data-monthly');
            }
        }
    });
});