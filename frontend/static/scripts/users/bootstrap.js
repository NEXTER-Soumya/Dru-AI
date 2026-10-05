async function loadClassicScript(source) {
    await new Promise((resolve, reject) => {
        const script = document.createElement('script');
        script.src = source;
        script.onload = resolve;
        script.onerror = () => reject(new Error(`Could not load ${source}.`));
        document.body.appendChild(script);
    });
}

function setDashboardProfile(profile) {
    const name = profile.name || '';
    const initial = name ? name[0].toLocaleUpperCase() : '?';

    document.querySelectorAll('.user-profile p:first-child').forEach(element => {
        element.textContent = name;
    });
    document.querySelectorAll('.user-avatar').forEach(element => {
        element.dataset.avatar = profile.avatar;
        element.dataset.initial = initial;
        element.textContent = initial;
    });

    const settingsNameInput = document.getElementById('settingsNameInput');
    if (settingsNameInput) settingsNameInput.value = name;

    const requiredNameInput = document.getElementById('requiredNameInput');
    const requiredNameModal = document.getElementById('requiredNameModal');
    if (requiredNameInput) requiredNameInput.value = name;
    if (requiredNameModal) requiredNameModal.hidden = !profile.requires_name;
}

async function initializeDashboard() {
    const response = await fetch('/api/session-status', { cache: 'no-store' });
    if (!response.ok) {
        throw new Error(`Session check failed with status ${response.status}.`);
    }
    const profile = await response.json();
    if (!profile.authenticated) {
        window.location.replace('/');
        return;
    }

    setDashboardProfile(profile);
    const dashboard = document.getElementById('dashboardApp');
    if (dashboard) {
        dashboard.inert = profile.requires_name;
        dashboard.style.visibility = 'visible';
    }
    await loadClassicScript('/static/vendor/onnxruntime-web/ort.wasm.min.js');
    window.ort.env.wasm.numThreads = 1;
    window.ort.env.wasm.wasmPaths = '/static/vendor/onnxruntime-web/';
    await loadClassicScript('/static/scripts/users/breed-inference.js');
    await loadClassicScript('/static/scripts/users/dashboard.js');
    await loadClassicScript('/static/scripts/users/informations.js');
}

initializeDashboard().catch(error => {
    console.error('Could not initialize the dashboard:', error);
    window.alert('The dashboard could not connect to the backend. Please try again.');
    window.location.replace('/');
});
