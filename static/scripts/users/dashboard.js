// --- SECTION SWITCHER LOGIC ---
const requiredNameModal = document.getElementById('requiredNameModal');
const requiredNameForm = document.getElementById('requiredNameForm');

if (requiredNameModal && requiredNameForm && !requiredNameModal.hidden) {
    const nameInput = document.getElementById('requiredNameInput');
    const nameError = document.getElementById('requiredNameError');
    const saveButton = document.getElementById('requiredNameSubmit');
    const dashboardApp = document.getElementById('dashboardApp');

    requiredNameModal.addEventListener('click', event => {
        if (event.target === requiredNameModal) {
            event.preventDefault();
            nameInput.focus();
        }
    });
    document.addEventListener('keydown', event => {
        if (event.key === 'Escape') {
            event.preventDefault();
            nameInput.focus();
        } else if (event.key === 'Tab') {
            const focusable = [nameInput, saveButton];
            const currentIndex = focusable.indexOf(document.activeElement);
            if (event.shiftKey && currentIndex <= 0) {
                event.preventDefault();
                saveButton.focus();
            } else if (!event.shiftKey && currentIndex === focusable.length - 1) {
                event.preventDefault();
                nameInput.focus();
            }
        }
    });
    nameInput.focus();

    requiredNameForm.addEventListener('submit', async event => {
        event.preventDefault();
        nameError.hidden = true;
        saveButton.disabled = true;
        saveButton.textContent = 'Saving...';

        try {
            const response = await fetch('/api/profile/name', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ name: nameInput.value })
            });
            const data = await response.json();
            if (!response.ok) {
                throw new Error(data.error || 'Your name could not be saved.');
            }

            document.querySelectorAll('.user-profile p:first-child').forEach(element => {
                element.textContent = data.name;
            });
            document.querySelectorAll('.user-avatar').forEach(element => {
                renderProfileAvatar(element, element.dataset.avatar, data.initial);
            });
            const settingsNameInput = document.getElementById('settingsNameInput');
            if (settingsNameInput) settingsNameInput.value = data.name;
            requiredNameModal.hidden = true;
            dashboardApp.inert = false;
        } catch (error) {
            nameError.textContent = error.message || 'A network error occurred. Please try again.';
            nameError.hidden = false;
        } finally {
            saveButton.disabled = false;
            saveButton.textContent = 'Save name';
        }
    });
}

const navItems = document.querySelectorAll('.left li[data-target]');
const sections = document.querySelectorAll('.dashboard-section');
const dashboardScrollArea = document.querySelector('.right-content-scrollable');

navItems.forEach(item => {
    item.addEventListener('click', (e) => {
        e.preventDefault();
        const targetId = item.getAttribute('data-target');
        dashboardScrollArea?.classList.toggle('help-section-view', targetId === 'help-section');

        navItems.forEach(nav => nav.classList.remove('active'));
        item.classList.add('active');

        const loadingSection = document.getElementById('loading-section');
        const resultSection = document.getElementById('result-section');
        if (loadingSection) {
            loadingSection.style.display = 'none';
            loadingSection.classList.remove('active-section');
        }
        if (resultSection) {
            resultSection.style.display = 'none';
            resultSection.classList.remove('active-section');
        }

        sections.forEach(sec => {
            sec.classList.remove('active-section');
            if (sec.id === targetId) {
                sec.classList.add('active-section');
                sec.style.display = 'block';
                
                if (targetId === 'library-section' && typeof renderLibraryHistory === 'function') {
                    renderLibraryHistory();
                }
            } else if (sec.id !== 'loading-section' && sec.id !== 'result-section') {
                sec.style.display = 'none';
            }
        });
    });
});

// --- SIDEBAR FULL HIDE / SHOW TOGGLE ---
const sidebarToggle = document.getElementById('sidebarToggle');
const expandSidebarBtn = document.getElementById('expandSidebarBtn');
const leftSidebar = document.querySelector('.left');

if (sidebarToggle && leftSidebar && expandSidebarBtn) {
    sidebarToggle.addEventListener('click', () => {
        leftSidebar.classList.add('hidden');
        expandSidebarBtn.style.display = 'flex';
    });

    expandSidebarBtn.addEventListener('click', () => {
        leftSidebar.classList.remove('hidden');
        expandSidebarBtn.style.display = 'none';
    });
}

// --- THEME TOGGLE LOGIC ---
const themeToggleBtn = document.getElementById('themeToggleBtn');
const themeLabelText = document.getElementById('themeLabelText');
const themeIcon = document.getElementById('themeIcon');

// --- PROFILE AVATAR ---
const profileAvatarIcons = {
    person: 'person',
    paw: 'paw',
    leaf: 'leaf',
    flower: 'flower',
    heart: 'heart',
    star: 'star'
};

function renderProfileAvatar(element, avatar, initial) {
    element.replaceChildren();
    element.dataset.avatar = avatar;
    element.dataset.initial = initial;
    if (profileAvatarIcons[avatar]) {
        const icon = document.createElement('ion-icon');
        icon.setAttribute('name', profileAvatarIcons[avatar]);
        element.appendChild(icon);
    } else {
        element.textContent = initial;
    }
}

const profileAvatarElements = document.querySelectorAll('.user-avatar');
profileAvatarElements.forEach(element => {
    renderProfileAvatar(element, element.dataset.avatar, element.dataset.initial);
});

const profileIconChoices = document.querySelectorAll('[data-avatar-choice]');
const currentAvatar = profileAvatarElements[0]?.dataset.avatar || 'initial';
profileIconChoices.forEach(button => {
    button.setAttribute('aria-pressed', String(button.dataset.avatarChoice === currentAvatar));
});

profileIconChoices.forEach(button => {
    button.addEventListener('click', async () => {
        const feedback = document.getElementById('profileIconFeedback');
        feedback.hidden = true;
        profileIconChoices.forEach(choice => { choice.disabled = true; });

        try {
            const response = await fetch('/api/profile/avatar', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ avatar: button.dataset.avatarChoice })
            });
            const data = await response.json();
            if (!response.ok) throw new Error(data.error || 'Your profile icon could not be saved.');

            profileAvatarElements.forEach(element => {
                renderProfileAvatar(element, data.avatar, element.dataset.initial);
            });
            profileIconChoices.forEach(choice => {
                choice.setAttribute('aria-pressed', String(choice === button));
            });
            feedback.textContent = 'Your profile icon has been updated.';
            feedback.classList.remove('settings-error');
            feedback.hidden = false;
        } catch (error) {
            feedback.textContent = error.message || 'A network error occurred. Please try again.';
            feedback.classList.add('settings-error');
            feedback.hidden = false;
        } finally {
            profileIconChoices.forEach(choice => { choice.disabled = false; });
        }
    });
});

const paletteNames = ['default', 'blueviolet', 'lightblue', 'purple', 'orange'];
let currentPalette = localStorage.getItem('druai_palette');
if (!paletteNames.includes(currentPalette)) currentPalette = 'default';
document.body.dataset.palette = currentPalette;
let currentTheme = localStorage.getItem('druai_theme');
if (currentTheme !== 'dark') currentTheme = 'light';

function updateThemeUI(theme) {
    document.body.classList.remove('light-mode', 'dark-mode');
    if (theme === 'dark') {
        document.body.classList.add('dark-mode');
        themeLabelText.textContent = 'Dark Mode';
        themeIcon.setAttribute('name', 'moon-sharp');
    } else {
        document.body.classList.add('light-mode');
        themeLabelText.textContent = 'Light Mode';
        themeIcon.setAttribute('name', 'sunny-sharp');
    }
    document.querySelectorAll('[data-color-mode]').forEach(button => {
        button.setAttribute('aria-pressed', String(button.dataset.colorMode === theme));
    });
}
updateThemeUI(currentTheme);

document.querySelectorAll('.theme-choice').forEach(button => {
    button.setAttribute('aria-pressed', String(button.dataset.palette === currentPalette));
    button.addEventListener('click', () => {
        currentPalette = button.dataset.palette;
        document.body.dataset.palette = currentPalette;
        localStorage.setItem('druai_palette', currentPalette);
        document.querySelectorAll('.theme-choice').forEach(choice => {
            choice.setAttribute('aria-pressed', String(choice === button));
        });
    });
});

document.querySelectorAll('[data-color-mode]').forEach(button => {
    button.addEventListener('click', () => {
        currentTheme = button.dataset.colorMode;
        localStorage.setItem('druai_theme', currentTheme);
        updateThemeUI(currentTheme);
    });
});

if (themeToggleBtn) {
    themeToggleBtn.addEventListener('click', () => {
        currentTheme = (currentTheme === 'light') ? 'dark' : 'light';
        localStorage.setItem('druai_theme', currentTheme);
        updateThemeUI(currentTheme);
    });
}

// --- PROFILE SETTINGS ---
const profileSettingsForm = document.getElementById('profileSettingsForm');
if (profileSettingsForm) {
    const settingsNameInput = document.getElementById('settingsNameInput');
    const profileFeedback = document.getElementById('profileSettingsFeedback');

    profileSettingsForm.addEventListener('submit', async event => {
        event.preventDefault();
        profileFeedback.hidden = true;
        const submitButton = profileSettingsForm.querySelector('button[type="submit"]');
        submitButton.disabled = true;

        try {
            const response = await fetch('/api/profile/name', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ name: settingsNameInput.value })
            });
            const data = await response.json();
            if (!response.ok) throw new Error(data.error || 'Your name could not be saved.');

            document.querySelectorAll('.user-profile p:first-child').forEach(element => {
                element.textContent = data.name;
            });
            document.querySelectorAll('.user-avatar').forEach(element => {
                renderProfileAvatar(element, element.dataset.avatar, data.initial);
            });
            settingsNameInput.value = data.name;
            profileFeedback.textContent = 'Your name has been updated.';
            profileFeedback.classList.remove('settings-error');
            profileFeedback.hidden = false;
        } catch (error) {
            profileFeedback.textContent = error.message || 'A network error occurred. Please try again.';
            profileFeedback.classList.add('settings-error');
            profileFeedback.hidden = false;
        } finally {
            submitButton.disabled = false;
        }
    });
}

// --- ACCOUNT DELETION ---
const deleteAccountButton = document.getElementById('deleteAccountButton');
if (deleteAccountButton) {
    const deleteModal = document.getElementById('accountDeleteModal');
    const cancelDeleteButton = document.getElementById('cancelAccountDelete');
    const confirmDeleteButton = document.getElementById('confirmAccountDelete');
    const deleteError = document.getElementById('accountDeleteError');
    const confirmDeleteLabel = confirmDeleteButton.querySelector('span');

    function closeDeleteModal() {
        if (confirmDeleteButton.disabled) return;
        deleteModal.hidden = true;
        deleteAccountButton.focus();
    }

    deleteAccountButton.addEventListener('click', () => {
        deleteError.hidden = true;
        deleteModal.hidden = false;
        cancelDeleteButton.focus();
    });

    cancelDeleteButton.addEventListener('click', closeDeleteModal);
    deleteModal.addEventListener('click', event => {
        if (event.target === deleteModal) closeDeleteModal();
    });
    deleteModal.addEventListener('keydown', event => {
        if (event.key === 'Escape') {
            event.preventDefault();
            closeDeleteModal();
        } else if (event.key === 'Tab') {
            const focusable = [cancelDeleteButton, confirmDeleteButton]
                .filter(button => !button.disabled);
            const first = focusable[0];
            const last = focusable[focusable.length - 1];
            if (event.shiftKey && document.activeElement === first) {
                event.preventDefault();
                last.focus();
            } else if (!event.shiftKey && document.activeElement === last) {
                event.preventDefault();
                first.focus();
            }
        }
    });

    confirmDeleteButton.addEventListener('click', async () => {
        deleteError.hidden = true;
        confirmDeleteButton.disabled = true;
        cancelDeleteButton.disabled = true;
        confirmDeleteLabel.textContent = 'Deleting...';

        try {
            const response = await fetch('/api/account/delete', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ confirm: true })
            });
            const data = await response.json();
            if (!response.ok) throw new Error(data.error || 'Your account could not be deleted.');
            window.location.replace(data.redirect || '/');
        } catch (error) {
            deleteError.textContent = error.message || 'A network error occurred. Please try again.';
            deleteError.hidden = false;
            confirmDeleteButton.disabled = false;
            cancelDeleteButton.disabled = false;
            confirmDeleteLabel.textContent = 'Delete permanently';
        }
    });
}

// --- IDENTIFY UPLOAD & DRAG/DROP LOGIC ---
const uploadBtn = document.getElementById('uploadBtn');
const cameraBtn = document.getElementById('cameraBtn');
const fileInput = document.getElementById('fileInput');
const dropzone = document.getElementById('dropzone');
const exampleCards = document.querySelectorAll('.example-card');

if (uploadBtn && fileInput) {
    uploadBtn.addEventListener('click', (e) => { e.stopPropagation(); fileInput.click(); });
}
if (cameraBtn && fileInput) {
    cameraBtn.addEventListener('click', (e) => { e.stopPropagation(); fileInput.click(); });
}

if (dropzone && fileInput) {
    dropzone.addEventListener('click', (e) => {
        if (!e.target.closest('.upload-actions')) fileInput.click();
    });

    ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
        dropzone.addEventListener(eventName, (e) => { e.preventDefault(); e.stopPropagation(); }, false);
    });
    ['dragenter', 'dragover'].forEach(eventName => {
        dropzone.addEventListener(eventName, () => dropzone.classList.add('drag-over'));
    });
    ['dragleave', 'drop'].forEach(eventName => {
        dropzone.addEventListener(eventName, () => dropzone.classList.remove('drag-over'));
    });

    dropzone.addEventListener('drop', (e) => {
        const files = e.dataTransfer.files;
        if (files && files.length > 0) handleUploadedFile(files[0]);
    }, false);
}

if (fileInput) {
    fileInput.addEventListener('change', () => {
        if (fileInput.files.length > 0) {
            handleUploadedFile(fileInput.files[0]);
            fileInput.value = '';
        }
    });
}

exampleCards.forEach(card => {
    card.addEventListener('click', () => {
        const imgElement = card.querySelector('img');
        handleExampleImage(imgElement.src, imgElement.alt);
    });
});

function handleUploadedFile(file) {
    const allowedTypes = ['image/jpeg', 'image/png', 'image/webp'];
    if (file.type && !allowedTypes.includes(file.type)) {
        alert('Please upload a JPEG, PNG, or WebP image.');
        return;
    }
    if (file.size > 10 * 1024 * 1024) {
        alert('Image size must be 10 MB or less.');
        return;
    }
    processImageSubmission(file);
}

async function handleExampleImage(imgSrc, name) {
    try {
        const response = await fetch(imgSrc);
        if (!response.ok) {
            throw new Error('Could not load the example image.');
        }
        const blob = await response.blob();
        const file = new File([blob], `${name.toLowerCase()}.jpg`, { type: blob.type });
        handleUploadedFile(file);
    } catch (error) {
        console.error('Example image error:', error);
        alert('Could not load this example image. Please upload an image from your device.');
    }
}