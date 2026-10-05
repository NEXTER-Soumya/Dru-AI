function showSection(sectionId) {
    ['identify-section', 'loading-section', 'result-section'].forEach(id => {
        const section = document.getElementById(id);
        if (section) {
            const active = id === sectionId;
            section.style.display = active ? 'block' : 'none';
            section.classList.toggle('active-section', active);
        }
    });
}

let activeScan = null;
const breedInfoRequests = new Map();
const characteristics = document.getElementById('breedCharacteristics');
const careGuide = document.getElementById('breedCareGuide');
const similarBreeds = document.getElementById('breedSimilarBreeds');
const breedInfoStatus = document.getElementById('breedInfoStatus');
const breedOverview = document.getElementById('breedOverview');
const overviewFacts = document.getElementById('overviewFacts');
const overviewNote = document.getElementById('overviewNote');

async function processImageSubmission(file) {
    showSection('loading-section');

    try {
        const formData = new FormData();
        formData.append('image', file);
        const response = await fetch('/api/identify', {
            method: 'POST',
            body: formData,
        });
        const responseText = await response.text();
        let data;
        try {
            data = JSON.parse(responseText);
        } catch {
            data = null;
        }

        if (!response.ok) {
            throw new Error(
                data?.error ||
                `Image identification failed (HTTP ${response.status}). The server returned an unexpected response.`
            );
        }
        if (!data || typeof data !== 'object') {
            throw new Error('The server returned an invalid response. Please try again.');
        }
        openResultView(data);
    } catch (error) {
        showSection('identify-section');
        console.error('Image identification error:', error);
        alert(error.message || 'Image identification failed. Please try again.');
    }
}

function openResultView(scan) {
    activeScan = scan;
    showSection('result-section');
    document.getElementById('resultImagePreview').src = scan.image_url;
    document.getElementById('resultBreedName').textContent = scan.breed;
    document.getElementById('resultConfidence').textContent =
        `${Number(scan.confidence).toFixed(2)}% confidence`;
    document.querySelectorAll('.result-tab').forEach(tab => {
        const selected = tab.dataset.tab === 'overview';
        tab.classList.toggle('active', selected);
        tab.setAttribute('aria-selected', String(selected));
    });
    document.querySelectorAll('.tab-pane').forEach(panel => {
        panel.classList.toggle('active-pane', panel.id === 'tab-overview');
    });
    characteristics.replaceChildren();
    careGuide.replaceChildren();
    similarBreeds.replaceChildren();
    breedInfoStatus.textContent = 'Loading breed information from the dataset…';
    loadBreedInfo(scan);
}

function renderBreedInfo(info) {
    characteristics.replaceChildren();
    careGuide.replaceChildren();
    similarBreeds.replaceChildren();
    breedOverview.textContent = '';
    overviewFacts.replaceChildren();
    overviewNote.textContent = '';

    if (!info) {
        breedInfoStatus.textContent =
            'No information for this breed is in the local dataset yet.';
        return;
    }

    breedOverview.textContent = info.overview;
    info.overview_facts.forEach(item => {
        overviewFacts.appendChild(
            createOverviewFact(item.name, item.details, overviewFactIcons[item.name])
        );
    });
    overviewNote.textContent = info.overview_note;
    info.characteristics.forEach(item => {
        characteristics.appendChild(createInfoCard(item.name, item.details));
    });
    info.care_guide.forEach(item => {
        const listItem = document.createElement('li');
        const heading = document.createElement('strong');
        heading.textContent = `${item.name}: `;
        listItem.append(heading, document.createTextNode(item.details));
        careGuide.appendChild(listItem);
    });
    info.similar_breeds.forEach(breed => {
        similarBreeds.appendChild(createInfoCard(breed, ''));
    });
    breedInfoStatus.textContent =
        'Breed information loaded from the local dataset.';
}

const overviewFactIcons = {
    'Scientific name': 'reader-outline',
    'Adult weight': 'scale-outline',
    'Typical lifespan': 'heart-outline',
    'Milk production': 'water-outline',
    'Daily food intake': 'nutrition-outline',
    'Primary use · Draft': 'construct-outline',
    'Primary use · Dairy': 'water-outline',
    'Primary use · Dual Purpose': 'git-compare-outline',
    'Primary use · Dual purpose': 'git-compare-outline',
    'Primary use · Mixed': 'git-compare-outline',
    'Identification features': 'eye-outline',
};

function createOverviewFact(title, details, iconName = 'information-circle-outline') {
    const card = document.createElement('article');
    card.className = 'overview-fact-card';
    const icon = document.createElement('ion-icon');
    icon.setAttribute('name', iconName);
    icon.setAttribute('aria-hidden', 'true');
    const content = document.createElement('div');
    content.className = 'overview-fact-content';
    const heading = document.createElement('h4');
    heading.textContent = title;
    const description = document.createElement('p');
    description.textContent = details;
    content.append(heading, description);
    card.append(icon, content);
    return card;
}

function createInfoCard(title, details) {
    const card = document.createElement('article');
    card.className = 'breed-info-item';
    const heading = document.createElement('h4');
    heading.textContent = title;
    card.appendChild(heading);
    if (details) {
        const description = document.createElement('p');
        description.textContent = details;
        card.appendChild(description);
    }
    return card;
}

async function loadBreedInfo(scan) {
    const requestKey = scan.breed.trim().toLocaleLowerCase();
    if (!breedInfoRequests.has(requestKey)) {
        const promise = (async () => {
            const response = await fetch(
                `/api/breed-info?breed=${encodeURIComponent(scan.breed)}`
            );
            const data = await response.json();
            if (!response.ok) {
                throw new Error(data.error || 'Could not load the breed dataset.');
            }
            return data.breed_info;
        })();
        breedInfoRequests.set(requestKey, promise);
    }

    breedInfoStatus.textContent = 'Loading breed information from the dataset…';
    try {
        const info = await breedInfoRequests.get(requestKey);
        if (activeScan && activeScan.id === scan.id) {
            renderBreedInfo(info);
        }
    } catch (error) {
        breedInfoRequests.delete(requestKey);
        console.error('Local breed dataset error:', error);
        if (activeScan && activeScan.id === scan.id) {
            breedInfoStatus.textContent =
                error.message || 'Could not load the local breed dataset.';
        }
    }
}

async function renderLibraryHistory() {
    const grid = document.getElementById('libraryGrid');
    const emptyMsg = document.getElementById('emptyLibraryMsg');
    if (!grid || !emptyMsg) return;

    grid.replaceChildren();
    emptyMsg.style.display = 'none';

    try {
        const response = await fetch('/api/history');
        const data = await response.json();
        if (!response.ok) {
            throw new Error(data.error || 'Could not load identification history.');
        }

        if (data.scans.length === 0) {
            emptyMsg.style.display = 'block';
            return;
        }

        data.scans.forEach(scan => {
            const card = document.createElement('article');
            card.className = 'library-history-card';
            card.tabIndex = 0;

            const imageContainer = document.createElement('div');
            imageContainer.className = 'lib-card-img';
            const image = document.createElement('img');
            image.src = scan.image_url;
            image.alt = `Image classified as ${scan.breed}`;
            imageContainer.appendChild(image);

            const deleteButton = document.createElement('button');
            deleteButton.className = 'lib-delete-btn';
            deleteButton.type = 'button';
            deleteButton.title = 'Delete from history';
            deleteButton.setAttribute('aria-label', `Delete ${scan.breed} result`);
            deleteButton.innerHTML = '<ion-icon name="trash-outline"></ion-icon>';
            deleteButton.addEventListener('click', async event => {
                event.stopPropagation();
                await deleteScanHistoryItem(scan.id);
            });
            imageContainer.appendChild(deleteButton);

            const info = document.createElement('div');
            info.className = 'lib-card-info';
            const title = document.createElement('h4');
            title.textContent = scan.breed;
            const details = document.createElement('p');
            details.textContent =
                `${Number(scan.confidence).toFixed(2)}% confidence · ` +
                new Date(scan.created_at).toLocaleString();
            info.append(title, details);
            card.append(imageContainer, info);

            const openResult = () => openResultView(scan);
            card.addEventListener('click', openResult);
            card.addEventListener('keydown', event => {
                if (event.key === 'Enter' || event.key === ' ') {
                    event.preventDefault();
                    openResult();
                }
            });
            grid.appendChild(card);
        });
    } catch (error) {
        console.error('History loading error:', error);
        alert(error.message || 'Could not load identification history.');
    }
}

document.querySelectorAll('.result-tab').forEach(tab => {
    tab.addEventListener('click', () => {
        const selectedTab = tab.dataset.tab;
        document.querySelectorAll('.result-tab').forEach(item => {
            const selected = item === tab;
            item.classList.toggle('active', selected);
            item.setAttribute('aria-selected', String(selected));
        });
        document.querySelectorAll('.tab-pane').forEach(panel => {
            panel.classList.toggle('active-pane', panel.id === `tab-${selectedTab}`);
        });
    });
});

async function deleteScanHistoryItem(scanId) {
    try {
        const response = await fetch(`/api/history/${encodeURIComponent(scanId)}`, {
            method: 'DELETE',
        });
        const data = await response.json();
        if (!response.ok) {
            throw new Error(data.error || 'Could not delete this identification.');
        }
        await renderLibraryHistory();
    } catch (error) {
        console.error('History deletion error:', error);
        alert(error.message || 'Could not delete this identification.');
    }
}

renderLibraryHistory();

// --- BACK TO IDENTIFY BUTTON HANDLER ---
const backToIdentifyBtn = document.getElementById('backToIdentifyBtn');
if (backToIdentifyBtn) {
    backToIdentifyBtn.addEventListener('click', () => {
        showSection('identify-section');
        const navItems = document.querySelectorAll('.left li[data-target]');
        navItems.forEach(nav => {
            if (nav.getAttribute('data-target') === 'identify-section') {
                nav.classList.add('active');
            } else {
                nav.classList.remove('active');
            }
        });
    });
}