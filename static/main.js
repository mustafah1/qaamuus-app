// Somali Dictionary App JS
const DEBUG = false;
const searchInput = document.getElementById('searchInput');
const searchBtn = document.getElementById('searchBtn');
const showAllBtn = document.getElementById('showAllBtn');
const resultsContainer = document.getElementById('resultsContainer');
const resultsCount = document.getElementById('resultsCount');
const loadingSpinner = document.getElementById('loadingSpinner') || (resultsContainer?.querySelector('#loadingSpinner'));
const scrollLoader = document.getElementById('scrollLoader');
const backToTopBtn = document.getElementById('backToTopBtn');
// Mobile nav elements
const navToggle = document.getElementById('navToggle');
const primaryNav = document.getElementById('primaryNav');
let navLastFocused = null;
let searchTimeout;
let currentQuery = '';
let currentLetter = '';
const letterIndex = document.getElementById('letterIndex');
// Server-side pagination state + mode
const pagination = {
    mode: 'all', // 'all' | 'search' | 'letter'
    offset: 0,
    limit: 40,
    total: 0,
    loading: false,
    query: '',
    letter: ''
};
const loadMoreBtn = document.getElementById('loadMoreBtn'); // kept as fallback but unused with infinite scroll

// --- Autocomplete Dropdown ---
const existingSuggest = document.getElementById('suggestionBox');
const suggestionBox = existingSuggest || document.createElement('div');
if (!existingSuggest) {
    suggestionBox.className = 'suggestion-box';
    suggestionBox.style.display = 'none';
    const sc = document.querySelector('.search-container');
    if (sc) sc.appendChild(suggestionBox);
}
let suggestions = [];
let selectedSuggestion = -1;

function renderSuggestions(list, query) {
    if (!list.length || !query) {
        suggestionBox.style.display = 'none';
        suggestionBox.innerHTML = '';
        return;
    }
    suggestionBox.innerHTML = list.map((word, i) =>
        `<div class="suggestion-item${i === selectedSuggestion ? ' selected' : ''}" data-index="${i}">${highlightSuggestion(word, query)}</div>`
    ).join('');
    suggestionBox.style.display = '';
}

function highlightSuggestion(word, query) {
    if (!query) return word;
    const regex = new RegExp(`(${escapeRegExp(query)})`, 'gi');
    return word.replace(regex, '<mark>$1</mark>');
}

async function fetchSuggestions(query) {
    if (!query) {
        renderSuggestions([], '');
        return;
    }
    try {
        const res = await fetch(`/suggest?q=${encodeURIComponent(query)}`);
        const data = await res.json();
        suggestions = data.suggestions || [];
        selectedSuggestion = -1;
        renderSuggestions(suggestions, query);
    } catch {
        renderSuggestions([], '');
    }
}

searchInput.addEventListener('input', e => {
    const val = searchInput.value.trim();
    if (val) fetchSuggestions(val);
    else renderSuggestions([], '');
});

searchInput.addEventListener('keydown', e => {
    if (suggestionBox.style.display === 'none') return;
    if (e.key === 'ArrowDown') {
        selectedSuggestion = (selectedSuggestion + 1) % suggestions.length;
        renderSuggestions(suggestions, searchInput.value.trim());
        e.preventDefault();
    } else if (e.key === 'ArrowUp') {
        selectedSuggestion = (selectedSuggestion - 1 + suggestions.length) % suggestions.length;
        renderSuggestions(suggestions, searchInput.value.trim());
        e.preventDefault();
    } else if (e.key === 'Enter') {
        if (selectedSuggestion >= 0 && suggestions[selectedSuggestion]) {
            searchInput.value = suggestions[selectedSuggestion];
            renderSuggestions([], '');
            performSearch(searchInput.value.trim());
            e.preventDefault();
        }
    } else if (e.key === 'Escape') {
        renderSuggestions([], '');
    }
});

suggestionBox.addEventListener('mousedown', e => {
    if (e.target.classList.contains('suggestion-item')) {
        const idx = +e.target.dataset.index;
        if (suggestions[idx]) {
            searchInput.value = suggestions[idx];
            renderSuggestions([], '');
            performSearch(searchInput.value.trim());
        }
    }
});

document.addEventListener('click', e => {
    if (!suggestionBox.contains(e.target) && e.target !== searchInput) {
        renderSuggestions([], '');
    }
});

// --- Mobile Nav Toggle with A11y ---
function getFocusable(root) {
    return root ? Array.from(root.querySelectorAll('a[href], button, [tabindex]:not([tabindex="-1"])')) : [];
}
function openNav() {
    if (!primaryNav) return;
    navLastFocused = document.activeElement;
    primaryNav.classList.add('open');
    navToggle?.setAttribute('aria-expanded', 'true');
    const items = getFocusable(primaryNav);
    (items[0] || primaryNav).focus();
    document.addEventListener('keydown', onNavKeyDown);
    document.addEventListener('click', onNavOutsideClick, true);
}
function closeNav() {
    if (!primaryNav) return;
    primaryNav.classList.remove('open');
    navToggle?.setAttribute('aria-expanded', 'false');
    document.removeEventListener('keydown', onNavKeyDown);
    document.removeEventListener('click', onNavOutsideClick, true);
    if (navLastFocused && typeof navLastFocused.focus === 'function') {
        navLastFocused.focus();
    } else if (navToggle) {
        navToggle.focus();
    }
}
function onNavKeyDown(e) {
    if (e.key === 'Escape') {
        e.preventDefault();
        closeNav();
    } else if (e.key === 'Tab' && primaryNav && primaryNav.classList.contains('open')) {
        const items = getFocusable(primaryNav);
        if (!items.length) return;
        const idx = items.indexOf(document.activeElement);
        if (e.shiftKey && (idx <= 0)) {
            e.preventDefault();
            items[items.length - 1].focus();
        } else if (!e.shiftKey && (idx === items.length - 1)) {
            e.preventDefault();
            items[0].focus();
        }
    }
}
function onNavOutsideClick(e) {
    if (!primaryNav || !primaryNav.classList.contains('open')) return;
    if (e.target === navToggle) return;
    if (!primaryNav.contains(e.target)) closeNav();
}
if (navToggle && primaryNav) {
    navToggle.addEventListener('click', () => {
        const expanded = navToggle.getAttribute('aria-expanded') === 'true';
        if (expanded) closeNav(); else openNav();
    });
    // Close when a nav link is clicked
    primaryNav.addEventListener('click', (e) => {
        const target = e.target;
        if (target && target.closest('a')) {
            closeNav();
        }
    });
}

// Close nav when resizing to desktop
window.addEventListener('resize', () => {
    if (window.innerWidth > 700 && primaryNav && primaryNav.classList.contains('open')) {
        closeNav();
    }
});

// Fetch and render letter index on load
async function fetchLetterIndex() {
    if (!letterIndex) return; // not available on dictionary page
    try {
        const res = await fetch('/index');
        const data = await res.json();
        renderLetterIndex(data.letters || []);
    } catch (e) {
        if (letterIndex) letterIndex.innerHTML = '<div class="no-results">Failed to load index</div>';
    }
}

function renderLetterIndex(letters) {
    if (!letterIndex) return;
    if (!letters.length) { letterIndex.innerHTML = ''; return; }
    letterIndex.innerHTML = letters.map(letter => `<span class="letter${letter === currentLetter ? ' active' : ''}" data-letter="${letter}">${letter}</span>`).join(' ');
    // Add event listeners
    Array.from(letterIndex.querySelectorAll('.letter')).forEach(el => {
        el.onclick = () => {
            currentLetter = el.dataset.letter;
            currentQuery = '';
            searchInput.value = '';
            fetchWordsByLetter(currentLetter);
            renderLetterIndex(letters);
        };
    });
}

async function fetchWordsByLetter(letter, reset = true) {
    if (reset) {
        pagination.mode = 'letter';
        pagination.offset = 0;
        pagination.total = 0;
        pagination.letter = letter;
        currentQuery = '';
        resultsContainer.innerHTML = '';
    }
    if (pagination.loading) return;
    pagination.loading = true;
    showLoading(true);
    try {
        const url = `/words_by_letter?letter=${encodeURIComponent(pagination.letter)}&limit=${pagination.limit}&offset=${pagination.offset}`;
        const res = await fetch(url);
        const data = await res.json();
        if (reset) pagination.total = data.total_count || data.count || 0;
        appendItems(data.results || [], '');
        pagination.offset += (data.count || (data.results ? data.results.length : 0));
        updateCountLabel();
    } catch (e) {
        showError('Failed to load words for ' + letter);
    } finally {
        pagination.loading = false;
        showLoading(false);
    }
}

// Fetch all words on load
async function fetchAllWords(reset = true) {
    if (reset) {
        pagination.mode = 'all';
        pagination.offset = 0;
        pagination.total = 0;
        resultsContainer.innerHTML = '';
        currentQuery = '';
        currentLetter = '';
    }
    if (pagination.loading) return;
    pagination.loading = true;
    showLoading(true);
    try {
        const url = `/all_words?limit=${pagination.limit}&offset=${pagination.offset}`;
        const res = await fetch(url);
        const data = await res.json();
        if (reset) pagination.total = data.total_count || data.count || 0;
        appendItems(data.results || [], '');
        pagination.offset += (data.count || (data.results ? data.results.length : 0));
        updateCountLabel();
    } catch (e) {
        showError('Failed to load dictionary.');
    } finally {
        pagination.loading = false;
        showLoading(false);
    }
}

async function performSearch(query = '', reset = true) {
    currentQuery = query;
    if (!query) { fetchAllWords(true); return; }
    if (reset) {
        pagination.mode = 'search';
        pagination.offset = 0;
        pagination.total = 0;
        pagination.query = query;
        resultsContainer.innerHTML = '';
    }
    if (pagination.loading) return;
    pagination.loading = true;
    showLoading(true);
    try {
        const url = `/search?q=${encodeURIComponent(pagination.query)}&limit=${pagination.limit}&offset=${pagination.offset}`;
        const res = await fetch(url);
        const data = await res.json();
        if (reset) pagination.total = data.total_count || data.count || 0;
        appendItems(data.results || [], query);
        pagination.offset += (data.count || (data.results ? data.results.length : 0));
        updateCountLabel();
    } catch (e) {
        showError('Search failed.');
    } finally {
        pagination.loading = false;
        showLoading(false);
    }
}

function appendItems(items, query) {
    const list = Array.isArray(items) ? items : [];
    if (!list.length && resultsContainer.children.length === 0) {
        resultsContainer.innerHTML = `<div class="no-results"><h3>No results found</h3><p>Isku day eray Soomaali oo kale ama higgaad kale.</p></div>`;
        if (loadMoreBtn) loadMoreBtn.style.display = 'none';
        return;
    }
    let appended = 0;
    list.forEach((item, idxLocal) => {
        const idx = resultsContainer.children.length + idxLocal;
        try {
            let word = Array.isArray(item) ? item[0] : (item?.word ?? item?.[0]);
            let def = Array.isArray(item) ? item[1] : (item?.definition ?? item?.[1]);
            if (word == null && def == null) return; // skip malformed
            if (typeof word !== 'string') word = String(word ?? '');
            if (typeof def !== 'string') def = String(def ?? '');

            // Try to extract part of speech and preview
            let pos = '';
            let preview = def;
            let match = def ? def.match(/^(m\.|f\.|g\.[a-z0-9]+)\s+(.{0,80})/i) : null;
            if (match) {
                pos = match[1];
                preview = (match[2] || '').replace(/\s+$/, '') + (def.length > 80 ? '...' : '');
            } else {
                preview = (def || '').slice(0, 80) + ((def || '').length > 80 ? '...' : '');
            }
            const card = document.createElement('div');
            card.className = 'result-card';
            card.innerHTML = `
                <div class="result-meta">
                    <div class="meta-label">Somali</div>
                </div>
                <div class="result-main">
                    <div class="result-head">
                        <span class="result-word">${highlightText(word, query)}</span>
                        ${pos ? `<span class="result-pos">${pos}</span>` : ''}
                    </div>
                    <div class="result-preview">${highlightText(preview, query)}</div>
                    <a href="#" class="result-view-link" data-idx="${idx}">Eeg faahfaahin</a>
                    <div class="result-full-def" style="display:none;">${highlightText(def, query)}</div>
                </div>
            `;
            resultsContainer.appendChild(card);
            appended++;
        } catch (err) {
            console.error('Failed to render result item', item, err);
        }
    });
    updateCountLabel();
    if (DEBUG) console.log('displayResults appended cards:', appended);
    // Expand/collapse logic for 'Eeg faahfaahin'
    // Modal logic for 'Eeg faahfaahin' (optional on some pages)
    const modal = document.getElementById('entryModal');
    const modalClose = document.getElementById('entryModalClose');
    const modalWord = document.getElementById('entryModalWord');
    const modalDef = document.getElementById('entryModalDefinition');

    let lastFocusedElement = null;
    function getFocusableElements(root) {
        return root.querySelectorAll('a[href], button, textarea, input, select, [tabindex]:not([tabindex="-1"])');
    }
    function openModal(word, def) {
        if (!modal || !modalClose || !modalWord || !modalDef) return; // no modal on this page
        lastFocusedElement = document.activeElement;
        modalWord.textContent = word;
        modalDef.textContent = def;
        modal.style.display = 'flex';
        // focus first focusable
        const focusables = getFocusableElements(modal);
        (focusables[0] || modalClose).focus();
        document.addEventListener('keydown', onModalKeyDown);
    }
    function closeModal() {
        if (!modal) return;
        modal.style.display = 'none';
        document.removeEventListener('keydown', onModalKeyDown);
        if (lastFocusedElement && typeof lastFocusedElement.focus === 'function') {
            lastFocusedElement.focus();
        }
    }
    function onModalKeyDown(e) {
        if (e.key === 'Escape') {
            e.preventDefault();
            closeModal();
        } else if (e.key === 'Tab') {
            // simple focus trap
            const focusables = Array.from(getFocusableElements(modal));
            if (!focusables.length) return;
            const idx = focusables.indexOf(document.activeElement);
            if (e.shiftKey) {
                if (idx <= 0) {
                    e.preventDefault();
                    focusables[focusables.length - 1].focus();
                }
            } else {
                if (idx === focusables.length - 1) {
                    e.preventDefault();
                    focusables[0].focus();
                }
            }
        }
    }

    resultsContainer.querySelectorAll('.result-view-link').forEach(link => {
        link.addEventListener('click', function(e) {
            e.preventDefault();
            const word = this.closest('.result-card')?.querySelector('.result-word')?.textContent || '';
            const def = this.closest('.result-card')?.querySelector('.result-full-def')?.textContent || '';
            openModal(word, def);
        });
    });
    // Modal close and backdrop click (only if modal exists)
    if (modal && modalClose) {
        modalClose.onclick = () => { closeModal(); };
        modal.onclick = (e) => { if (e.target === modal) closeModal(); };
    }

}

function highlightText(text, query) {
    // First, make 'eeg WORD' clickable (WORD = Somali word, not punctuation)
    text = text.replace(/eeg ([a-zA-Z’ʼʻ0-9()¹²³'′]+)/g, function(match, word) {
        return `eeg <a href="#" class="eeg-link" data-eeg="${word}">${word}</a>`;
    });
    // Then highlight query (but not inside links)
    if (query) {
        // Only highlight outside of <a> tags
        text = text.replace(/>([^<]+)</g, function(m, inner) {
            const regex = new RegExp(`(${escapeRegExp(query)})`, 'gi');
            return '>' + inner.replace(regex, '<mark>$1</mark>') + '<';
        });
    }
    return text;
}

// Delegate click on eeg-link
resultsContainer.addEventListener('click', function(e) {
    if (e.target.classList && e.target.classList.contains('eeg-link')) {
        e.preventDefault();
        const word = e.target.dataset.eeg;
        searchInput.value = word;
        performSearch(word);
        window.scrollTo({ top: 0, behavior: 'smooth' });
    }
});
function escapeRegExp(string) {
    return string.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}
function showLoading(show) {
    if (loadingSpinner) loadingSpinner.style.display = show ? '' : 'none';
    // Show a smaller loader at the bottom only for subsequent pages
    if (scrollLoader) {
        const useBottom = show && pagination && pagination.offset > 0;
        scrollLoader.style.display = useBottom ? '' : 'none';
    }
}
function showError(message) {
    resultsContainer.innerHTML = `<div class='no-results'><h3>${message}</h3></div>`;
}
// Event listeners
searchBtn.addEventListener('click', () => {
    const query = searchInput.value.trim();
    performSearch(query);
});
searchInput.addEventListener('keydown', e => {
    if (e.key === 'Enter') {
        performSearch(searchInput.value.trim());
    }
});
// Note: Show All handler is defined later to also reset letter filters and refetch
// Back to Top button
if (backToTopBtn) {
    window.addEventListener('scroll', () => {
        if (window.scrollY > 300) {
            backToTopBtn.style.display = 'flex';
        } else {
            backToTopBtn.style.display = 'none';
        }
    });
    backToTopBtn.addEventListener('click', () => {
        window.scrollTo({ top: 0, behavior: 'smooth' });
    });
}
// Initial load
fetchLetterIndex();
fetchAllWords(true);

// Show All: single handler, also clears letter selection if present
showAllBtn.addEventListener('click', () => {
    searchInput.value = '';
    currentQuery = '';
    if (letterIndex) {
        currentLetter = '';
        renderLetterIndex(Array.from(letterIndex.querySelectorAll('.letter')).map(el => el.textContent));
    }
    fetchAllWords(true);
});

// Infinite scroll: fetch next page near bottom
window.addEventListener('scroll', () => {
    const nearBottom = (window.innerHeight + window.scrollY) >= (document.body.offsetHeight - 600);
    if (!nearBottom) return;
    if (pagination.loading) return;
    // If fully loaded, stop
    if (pagination.offset >= pagination.total) return;
    if (pagination.mode === 'all') return fetchAllWords(false);
    if (pagination.mode === 'search') return performSearch(pagination.query, false);
    if (pagination.mode === 'letter') return fetchWordsByLetter(pagination.letter, false);
});

function updateCountLabel() {
    if (!resultsCount) return;
    const shown = Math.min(pagination.offset, pagination.total);
    const total = pagination.total;
    if (!total) { resultsCount.textContent = ''; return; }
    // Somali label
    resultsCount.textContent = `${shown} ka mid ah ${total} natiijo`;
}
