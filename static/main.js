// Somali Dictionary App JS
const searchInput = document.getElementById('searchInput');
const searchBtn = document.getElementById('searchBtn');
const showAllBtn = document.getElementById('showAllBtn');
const resultsContainer = document.getElementById('resultsContainer');
const resultsCount = document.getElementById('resultsCount');
const loadingSpinner = document.getElementById('loadingSpinner');
const backToTopBtn = document.getElementById('backToTopBtn');
let searchTimeout;
let allResults = [];
let currentQuery = '';
let currentLetter = '';
const letterIndex = document.getElementById('letterIndex');

// --- Autocomplete Dropdown ---
const suggestionBox = document.createElement('div');
suggestionBox.className = 'suggestion-box';
suggestionBox.style.display = 'none';
document.querySelector('.search-container').appendChild(suggestionBox);
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

// Fetch and render letter index on load
async function fetchLetterIndex() {
    try {
        const res = await fetch('/index');
        const data = await res.json();
        renderLetterIndex(data.letters || []);
    } catch (e) {
        letterIndex.innerHTML = '<div class="no-results">Failed to load index</div>';
    }
}

function renderLetterIndex(letters) {
    if (!letters.length) {
        letterIndex.innerHTML = '';
        return;
    }
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

async function fetchWordsByLetter(letter) {
    showLoading(true);
    try {
        const res = await fetch(`/words_by_letter?letter=${encodeURIComponent(letter)}`);
        const data = await res.json();
        allResults = data.results;
        displayResults(allResults, data.count, '');
    } catch (e) {
        showError('Failed to load words for ' + letter);
    } finally {
        showLoading(false);
    }
}

// Fetch all words on load
async function fetchAllWords() {
    showLoading(true);
    try {
        const res = await fetch('/all_words');
        const data = await res.json();
        allResults = data.results; // Use the array of [word, definition] pairs
        console.log('allResults:', allResults);
        displayResults(allResults, data.total_count, '');
    } catch (e) {
        showError('Failed to load dictionary.');
    } finally {
        showLoading(false);
    }
}

async function performSearch(query = '') {
    currentQuery = query;
    showLoading(true);
    if (!query) {
        // Show all from memory
        displayResults(allResults, allResults.length, '');
        showLoading(false);
        return;
    }
    try {
        const res = await fetch(`/search?q=${encodeURIComponent(query)}`);
        const data = await res.json();
        displayResults(data.results, data.count, query);
    } catch (e) {
        showError('Search failed.');
    } finally {
        showLoading(false);
    }
}

function displayResults(results, count, query) {
    resultsContainer.innerHTML = '';
    resultsCount.textContent = count ? `${count} result${count !== 1 ? 's' : ''}` : '';
    if (!count) {
        resultsContainer.innerHTML = `<div class="no-results"><h3>No results found</h3><p>Try a different Somali word or spelling.</p></div>`;
        return;
    }
    results.forEach(([word, def], idx) => {
        // Try to extract part of speech and preview
        let pos = '';
        let preview = def;
        let match = def.match(/^(m\.|f\.|g\.[a-z0-9]+)\s+(.{0,80})/i);
        if (match) {
            pos = match[1];
            preview = match[2].replace(/\s+$/, '') + (def.length > 80 ? '...' : '');
        } else {
            preview = def.slice(0, 80) + (def.length > 80 ? '...' : '');
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
    });
    // Expand/collapse logic for 'Eeg faahfaahin'
    // Modal logic for 'Eeg faahfaahin'
    resultsContainer.querySelectorAll('.result-view-link').forEach(link => {
        link.addEventListener('click', function(e) {
            e.preventDefault();
            const word = this.closest('.result-card')?.querySelector('.result-word')?.textContent || '';
            const def = this.closest('.result-card')?.querySelector('.result-full-def')?.textContent || '';
            const modal = document.getElementById('entryModal');
            const modalWord = document.getElementById('entryModalWord');
            const modalDef = document.getElementById('entryModalDefinition');
            modalWord.textContent = word;
            modalDef.textContent = def;
            modal.style.display = 'flex';
        });
    });
    // Modal close logic
    const modal = document.getElementById('entryModal');
    const modalClose = document.getElementById('entryModalClose');
    modalClose.onclick = () => { modal.style.display = 'none'; };
    modal.onclick = (e) => { if (e.target === modal) modal.style.display = 'none'; };

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
    if (e.target.classList.contains('eeg-link')) {
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
    loadingSpinner.style.display = show ? '' : 'none';
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
showAllBtn.addEventListener('click', () => {
    searchInput.value = '';
    performSearch('');
});
// Back to Top button
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
// Initial load
fetchLetterIndex();
fetchAllWords();

// When Show All is clicked, clear letter selection
showAllBtn.addEventListener('click', () => {
    currentLetter = '';
    renderLetterIndex(Array.from(letterIndex.querySelectorAll('.letter')).map(el => el.textContent));
    fetchAllWords();
});
