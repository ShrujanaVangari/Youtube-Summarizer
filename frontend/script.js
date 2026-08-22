/**
 * YouTube AI Summarizer - Frontend Client Logic
 */

// API Backend Base URL
const API_BASE_URL = 'http://127.0.0.1:5000/api';

// State Management
let savedSummaries = [];
let selectedSummaryLength = 'short';

// Language Names Mapping
const summaryLengthNames = {
    'short': 'Short',
    'medium': 'Medium',
    'detailed': 'Detailed'
};

// DOM Elements
const summarizeForm = document.getElementById('summarizeForm');
const youtubeUrlInput = document.getElementById('youtubeUrlInput');
const clearInputBtn = document.getElementById('clearInputBtn');
const submitBtn = document.getElementById('submitBtn');

const langButtons = document.querySelectorAll('.lang-btn');
const currentLangBadge = document.getElementById('currentLangBadge');

const errorAlert = document.getElementById('errorAlert');
const errorMessage = document.getElementById('errorMessage');

const loadingState = document.getElementById('loadingState');
const step1 = document.getElementById('step1');
const step2 = document.getElementById('step2');
const step3 = document.getElementById('step3');

const resultState = document.getElementById('resultState');
const videoThumbnail = document.getElementById('videoThumbnail');
const videoTitle = document.getElementById('videoTitle');
const videoLink = document.getElementById('videoLink');
const summaryDate = document.getElementById('summaryDate');
const summaryParagraph = document.getElementById('summaryParagraph');
const keyPointsList = document.getElementById('keyPointsList');
const copySummaryBtn = document.getElementById('copySummaryBtn');

const historyList = document.getElementById('historyList');
const historyCountBadge = document.getElementById('historyCountBadge');
const refreshHistoryBtn = document.getElementById('refreshHistoryBtn');
const searchHistoryInput = document.getElementById('searchHistoryInput');

// ==========================================
// Initialization & Event Listeners
// ==========================================
document.addEventListener('DOMContentLoaded', () => {
    // Input listeners
    youtubeUrlInput.addEventListener('input', handleInputChange);
    clearInputBtn.addEventListener('click', clearInput);
    
    // Language Selection Buttons
    langButtons.forEach(btn => {
        btn.addEventListener('click', () => {
            langButtons.forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            selectedSummaryLength = btn.getAttribute('data-length') || 'medium';
        });
    });

    // Form submission
    summarizeForm.addEventListener('submit', handleFormSubmit);
    
    // Copy summary button
    copySummaryBtn.addEventListener('click', copySummaryToClipboard);
    
    // History actions
    refreshHistoryBtn.addEventListener('click', fetchHistory);
    searchHistoryInput.addEventListener('input', filterHistory);

    // Initial fetch of history records
    fetchHistory();
});

// ==========================================
// Helper Functions
// ==========================================
function extractYouTubeVideoId(url) {
    if (!url) return null;
    const regExp = /^.*(youtu.be\/|v\/|u\/\w\/|embed\/|shorts\/|watch\?v=|\&v=)([^#\&\?]*).*/;
    const match = url.match(regExp);
    return (match && match[2].length === 11) ? match[2] : null;
}

function handleInputChange() {
    clearInputBtn.style.display = youtubeUrlInput.value.trim() ? 'block' : 'none';
    hideError();
}

function clearInput() {
    youtubeUrlInput.value = '';
    clearInputBtn.style.display = 'none';
    hideError();
    youtubeUrlInput.focus();
}

function showError(msg) {
    errorMessage.textContent = msg;
    errorAlert.style.display = 'flex';
}

function hideError() {
    errorAlert.style.display = 'none';
}

// ==========================================
// Form Submission & API Request
// ==========================================
async function handleFormSubmit(e) {
    e.preventDefault();
    hideError();

    const rawUrl = youtubeUrlInput.value.trim();
    const videoId = extractYouTubeVideoId(rawUrl);

    if (!videoId) {
        showError('Invalid YouTube URL format. Please paste a valid YouTube video link.');
        return;
    }

    setLoadingState(true);
    updateProgressSteps(1);

    try {
        updateProgressSteps(2);
        
        const response = await fetch(`${API_BASE_URL}/summarize`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ 
                url: rawUrl, 
                video_id: videoId,
                summary_length: selectedSummaryLength
            })
        });

        const data = await response.json();

        if (!response.ok || !data.success) {
            throw new Error(data.error || 'Failed to generate video summary.');
        }

        updateProgressSteps(3);
        
        setTimeout(() => {
            renderSummaryResult(data.data);
            setLoadingState(false);
            fetchHistory();
        }, 500);

    } catch (err) {
        console.error('Summarization Error:', err);
        setLoadingState(false);
        showError(err.message || 'Server error. Make sure backend service is running.');
    }
}

// ==========================================
// UI Rendering Functions
// ==========================================
function setLoadingState(isLoading) {
    if (isLoading) {
        submitBtn.disabled = true;
        submitBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Generating Brief Summary...';
        loadingState.style.display = 'block';
        resultState.style.display = 'none';
    } else {
        submitBtn.disabled = false;
        submitBtn.innerHTML = '<i class="fa-solid fa-wand-magic-sparkles"></i> Summarize';
        loadingState.style.display = 'none';
    }
}

function updateProgressSteps(stepNumber) {
    step1.classList.toggle('active', stepNumber >= 1);
    step2.classList.toggle('active', stepNumber >= 2);
    step3.classList.toggle('active', stepNumber >= 3);
}

function renderSummaryResult(data) {
    const videoId = data.video_id || extractYouTubeVideoId(data.youtube_url);
    
    // Set Metadata
    videoThumbnail.src = `https://img.youtube.com/vi/${videoId}/hqdefault.jpg`;
    videoTitle.textContent = data.title || 'YouTube Video Summary';
    videoLink.href = data.youtube_url;
    
    // Set Language Badge
    const summaryLength = data.summary_length || selectedSummaryLength;
    currentLangBadge.innerHTML = `<i class="fa-solid fa-align-center"></i> ${summaryLengthNames[summaryLength] || 'Medium'}`;

    // Format timestamp
    const dateObj = data.created_at ? new Date(data.created_at) : new Date();
    summaryDate.innerHTML = `<i class="fa-regular fa-calendar"></i> ${dateObj.toLocaleDateString()} ${dateObj.toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'})}`;
    
    // Set Brief Executive Summary Paragraph
    summaryParagraph.textContent = data.summary;

    // Render Key Points
    keyPointsList.innerHTML = '';
    const points = Array.isArray(data.key_points) ? data.key_points : [];
    
    if (points.length === 0) {
        keyPointsList.innerHTML = '<li>No specific key points extracted.</li>';
    } else {
        points.forEach(point => {
            const li = document.createElement('li');
            li.textContent = point;
            keyPointsList.appendChild(li);
        });
    }

    resultState.style.display = 'flex';
    resultState.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

// ==========================================
// Clipboard Operations
// ==========================================
function copySummaryToClipboard() {
    const textToCopy = `${videoTitle.textContent}\n\nEXECUTIVE SUMMARY:\n${summaryParagraph.textContent}\n\nKEY TAKEAWAYS:\n` + 
        Array.from(keyPointsList.children).map(li => `• ${li.textContent}`).join('\n');
    
    navigator.clipboard.writeText(textToCopy).then(() => {
        const originalText = copySummaryBtn.innerHTML;
        copySummaryBtn.innerHTML = '<i class="fa-solid fa-check"></i> Copied!';
        setTimeout(() => {
            copySummaryBtn.innerHTML = originalText;
        }, 2000);
    }).catch(err => console.error('Failed to copy:', err));
}

// ==========================================
// History Sidebar Functions
// ==========================================
async function fetchHistory() {
    try {
        refreshHistoryBtn.classList.add('fa-spin');
        const response = await fetch(`${API_BASE_URL}/history`);
        if (!response.ok) throw new Error('Could not fetch history');
        
        const data = await response.json();
        if (data.success && Array.isArray(data.data)) {
            savedSummaries = data.data;
            renderHistoryList(savedSummaries);
        }
    } catch (err) {
        console.log('History endpoint offline or empty:', err.message);
    } finally {
        setTimeout(() => refreshHistoryBtn.classList.remove('fa-spin'), 500);
    }
}

function renderHistoryList(items) {
    historyCountBadge.textContent = items.length;
    
    if (items.length === 0) {
        historyList.innerHTML = `
            <div class="empty-state">
                <i class="fa-solid fa-box-open"></i>
                <p>No saved summaries yet.</p>
                <span>Summarize a YouTube video to see it here!</span>
            </div>
        `;
        return;
    }

    historyList.innerHTML = '';
    items.forEach(item => {
        const dateStr = item.created_at ? new Date(item.created_at).toLocaleDateString() : 'Recent';
        const card = document.createElement('div');
        card.className = 'history-item';
        card.innerHTML = `
            <div class="history-item-title">${escapeHtml(item.title || 'YouTube Summary')}</div>
            <div class="history-item-date"><i class="fa-regular fa-clock"></i> ${dateStr}</div>
        `;
        card.addEventListener('click', () => {
            youtubeUrlInput.value = item.youtube_url;
            handleInputChange();
            renderSummaryResult(item);
        });
        historyList.appendChild(card);
    });
}

function filterHistory() {
    const query = searchHistoryInput.value.toLowerCase().trim();
    if (!query) {
        renderHistoryList(savedSummaries);
        return;
    }
    const filtered = savedSummaries.filter(item => 
        (item.title && item.title.toLowerCase().includes(query)) ||
        (item.summary && item.summary.toLowerCase().includes(query))
    );
    renderHistoryList(filtered);
}

function escapeHtml(str) {
    return str.replace(/[&<>'"]/g, 
        tag => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;' }[tag] || tag)
    );
}
