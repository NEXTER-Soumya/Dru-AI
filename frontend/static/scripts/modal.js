// --- AUTHENTICATION MODAL LOGIC & API SUBMISSION ---

const authModal = document.getElementById("authModal");
const openAuthBtns = document.querySelectorAll(".open-auth-modal, .log-in, .sign-up");
const closeAuthModal = document.getElementById("closeAuthModal");
const showSignupLink = document.getElementById("showSignup");
const showLoginLink = document.getElementById("showLogin");
const loginFormPanel = document.getElementById("loginForm");
const signupFormPanel = document.getElementById("signupForm");

window.addEventListener("pageshow", async (event) => {
    if (!event.persisted) return;

    try {
        const response = await fetch("/api/session-status", { cache: "no-store" });
        if (!response.ok) {
            throw new Error(`Session check failed with status ${response.status}.`);
        }
        const data = await response.json();
        if (data.authenticated) {
            window.location.replace(data.redirect || "/dashboard");
        }
    } catch (error) {
        console.error("Could not verify the restored page session:", error);
    }
});

// Open Modal Triggers
openAuthBtns.forEach(btn => {
    btn.addEventListener("click", (e) => {
        e.preventDefault();
        if (authModal) {
            const showSignup = btn.classList.contains("sign-up");
            loginFormPanel.classList.toggle("active-panel", !showSignup);
            signupFormPanel.classList.toggle("active-panel", showSignup);
            authModal.classList.add("modal-active");
        }
    });
});

// Close Modal Triggers
if (closeAuthModal) {
    closeAuthModal.addEventListener("click", () => {
        authModal.classList.remove("modal-active");
    });
}

if (authModal) {
    authModal.addEventListener("click", (e) => {
        if (e.target === authModal) {
            authModal.classList.remove("modal-active");
        }
    });
}

// Switch between Login and Signup panels
if (showSignupLink) {
    showSignupLink.addEventListener("click", (e) => {
        e.preventDefault();
        loginFormPanel.classList.remove("active-panel");
        signupFormPanel.classList.add("active-panel");
    });
}

if (showLoginLink) {
    showLoginLink.addEventListener("click", (e) => {
        e.preventDefault();
        signupFormPanel.classList.remove("active-panel");
        loginFormPanel.classList.add("active-panel");
    });
}

// Toggle Password Visibility
const togglePasswordBtns = document.querySelectorAll(".toggle-password");
togglePasswordBtns.forEach(btn => {
    btn.addEventListener("click", () => {
        const targetId = btn.getAttribute("data-target");
        const input = document.getElementById(targetId);
        if (input) {
            if (input.type === "password") {
                input.type = "text";
                btn.innerHTML = '<ion-icon name="eye-off-outline"></ion-icon>';
            } else {
                input.type = "password";
                btn.innerHTML = '<ion-icon name="eye-outline"></ion-icon>';
            }
        }
    });
});

// --- API SUBMISSION HANDLERS ---

// 1. Sign In Form Submission
const loginFormElement = document.querySelector("#loginForm form");
if (loginFormElement) {
    loginFormElement.addEventListener('submit', async (e) => {
        e.preventDefault();
        
        const emailInput = document.querySelector("#loginForm input[type='email']");
        const passwordInput = document.getElementById('loginPassword');

        const email = emailInput ? emailInput.value : '';
        const password = passwordInput ? passwordInput.value : '';

        try {
            const response = await fetch('/api/signin', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ email, password })
            });

            const data = await response.json();
            if (response.ok) {
                window.location.href = data.redirect || '/dashboard';
            } else {
                alert(data.error || "Login failed");
            }
        } catch (err) {
            console.error("Login error:", err);
            alert("An error occurred during login. Please try again.");
        }
    });
}

// 2. Sign Up Form Submission
const signupFormElement = document.querySelector("#signupForm form");
if (signupFormElement) {
    signupFormElement.addEventListener('submit', async (e) => {
        e.preventDefault();

        const nameInput = document.getElementById('signupName');
        const emailInput = document.getElementById('signupEmail');
        const passwordInput = document.getElementById('signupPassword');

        const name = nameInput ? nameInput.value : '';
        const email = emailInput ? emailInput.value : '';
        const password = passwordInput ? passwordInput.value : '';

        try {
            const response = await fetch('/api/signup', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ name, email, password })
            });

            const data = await response.json();
            if (response.ok) {
                window.location.href = data.redirect || '/dashboard';
            } else {
                alert(data.error || "Signup failed");
            }
        } catch (err) {
            console.error("Signup error:", err);
            alert("An error occurred during signup. Please try again.");
        }
    });
}