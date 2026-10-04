const themeBtn = document.getElementById('theme');
const icon = themeBtn.querySelector('ion-icon');
const navLinks = document.querySelectorAll('.nav-menu ul li a');
const pages = document.querySelectorAll('.page');


// 1. Check for saved theme preference when the page first loads
const savedTheme = localStorage.getItem('theme');
if (savedTheme === 'dark') {
    document.body.classList.add('dark-mode');
    icon.setAttribute('name', 'sunny'); // Set icon to sun if dark mode is active
} else {
    icon.setAttribute('name', 'moon-outline'); // Default to moon
}

// 2. Handle click to toggle theme and save preference
themeBtn.addEventListener('click', () => {
    document.body.classList.toggle('dark-mode');
    icon.classList.add('rotate');

    setTimeout(() => {
        if (document.body.classList.contains('dark-mode')) {
            localStorage.setItem('theme', 'dark'); // Save dark choice
            icon.setAttribute('name', 'sunny');
        } else {
            localStorage.setItem('theme', 'light'); // Save light choice
            icon.setAttribute('name', 'moon');
        }
    }, 200); // 200ms matches halfway through the animation

    setTimeout(() => {
        icon.classList.remove('rotate');
    }, 400);
});

navLinks.forEach(link => {
    link.addEventListener('click', (e) => {
        e.preventDefault();

        // Extract target section ID (e.g. '#feature' -> 'feature')
        const targetId = link.getAttribute('href').substring(1);
        const targetPage = document.getElementById(targetId);

        if (!targetPage || targetPage.classList.contains('active')) return;

        // Hide all pages
        pages.forEach(page => {
            page.classList.remove('active');
        });

        // Activate the target page, triggering the right-to-left slide animation
        targetPage.classList.add('active');
    });
});
// Target all internal hash links (nav menu, buttons, and footer links)
document.querySelectorAll('a[href^="#"]').forEach(link => {
    link.addEventListener('click', function(e) {
        e.preventDefault();

        const targetId = this.getAttribute('href'); // e.g. "#docs"
        const targetSection = document.querySelector(targetId);

        if (targetSection) {
            // Remove active class from all pages
            document.querySelectorAll('.page').forEach(page => {
                page.classList.remove('active');
            });

            // Activate target page
            targetSection.classList.add('active');

            // Optional: If you want corresponding navbar items to highlight if clicked
            document.querySelectorAll('.nav-menu a').forEach(navLink => {
                navLink.classList.remove('active-nav');
                if (navLink.getAttribute('href') === targetId) {
                    navLink.classList.add('active-nav');
                }
            });
        }
    });
});
