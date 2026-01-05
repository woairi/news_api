// Constants
const CATEGORY_TITLES = {
    'ai_news': 'AI 뉴스 요약',
    'datacenterdynamics': 'DatacenterDynamics 요약'
};

const TAB_BASE_MESSAGES = {
    'ai_news': '최근 48시간 인기 AI 기사 요약을 확인하세요.',
    'datacenterdynamics': '전일 기사 기준으로 제공되는 요약입니다.'
};

// State
let state = {
    currentCategory: 'ai_news',
    currentDate: null,
    availableDates: [],
    statusData: {},
    theme: localStorage.getItem('theme') || 'system',
    design: localStorage.getItem('design') || 'material'
};

// DOM Elements
const elements = {
    tabs: document.querySelectorAll('.tab'),
    summaryContent: document.getElementById('summaryContent'),
    recentButtons: document.getElementById('recentButtons'),
    tabInfo: document.getElementById('tabInfo'),
    statusAiRun: document.getElementById('status-ai-run'),
    statusDcRun: document.getElementById('status-dc-run'),
    datePicker: document.getElementById('datePicker'),
    searchDateBtn: document.getElementById('searchDateBtn'),
    themeToggle: document.getElementById('themeToggle'),
    designSelect: document.getElementById('designSelect')
};

// Initialization
document.addEventListener('DOMContentLoaded', () => {
    initTheme();
    initDesign();
    loadStatus();
    switchCategory('ai_news');

    // Event Listeners
    elements.tabs.forEach(tab => {
        tab.addEventListener('click', (e) => {
            const category = e.target.dataset.category;
            switchCategory(category);
        });
    });

    elements.searchDateBtn.addEventListener('click', searchByDate);
    elements.themeToggle.addEventListener('click', toggleTheme);
    elements.designSelect.addEventListener('change', changeDesign);
});

// Theme Management
function initTheme() {
    const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
    if (state.theme === 'system') {
        document.documentElement.setAttribute('data-theme', prefersDark ? 'dark' : 'light');
    } else {
        document.documentElement.setAttribute('data-theme', state.theme);
    }
}

function toggleTheme() {
    const currentTheme = document.documentElement.getAttribute('data-theme');
    const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
    document.documentElement.setAttribute('data-theme', newTheme);
    localStorage.setItem('theme', newTheme);
    state.theme = newTheme;
}

// Design System Management
function initDesign() {
    document.documentElement.setAttribute('data-design', state.design);
    elements.designSelect.value = state.design;
}

function changeDesign() {
    const newDesign = elements.designSelect.value;
    document.documentElement.setAttribute('data-design', newDesign);
    localStorage.setItem('design', newDesign);
    state.design = newDesign;
}

// Data Fetching & UI Logic
async function loadStatus() {
    try {
        const response = await fetch('/api/status');
        const data = await response.json();
        state.statusData = data;

        // Update Status UI
        const cats = data.categories || {};
        if (cats['ai_news']) {
            elements.statusAiRun.textContent = cats['ai_news'].latest_created_at_kst || '-';
        }
        if (cats['datacenterdynamics']) {
            elements.statusDcRun.textContent = cats['datacenterdynamics'].latest_created_at_kst || '-';
        }

        // Set DatePicker max date
        try {
            const todayRes = await fetch('/api/today');
            const todayData = await todayRes.json();
            elements.datePicker.max = todayData.today;
        } catch (e) {
            console.error(e);
        }
    } catch (error) {
        console.error('Status load failed:', error);
    }
}

async function switchCategory(category) {
    state.currentCategory = category;

    // Update Tabs UI
    elements.tabs.forEach(tab => {
        if (tab.dataset.category === category) {
            tab.classList.add('active');
        } else {
            tab.classList.remove('active');
        }
    });

    // Reset Content
    elements.summaryContent.innerHTML = '<div class="text-center" style="padding:40px">📡 데이터 로딩 중...</div>';

    // Load Dates
    await loadDates();
}

async function loadDates() {
    try {
        const response = await fetch(`/api/dates?category=${state.currentCategory}`);
        const dates = await response.json();
        state.availableDates = dates;

        renderDateChips(dates);

        if (dates.length > 0) {
            loadSummary(dates[0]);
        } else {
            elements.summaryContent.innerHTML = '<div class="text-center" style="padding:40px">저장된 요약이 없습니다.</div>';
        }
    } catch (error) {
        console.error('Dates load failed:', error);
        elements.summaryContent.innerHTML = '<div class="text-center" style="padding:40px">❌ 날짜 목록을 불러오지 못했습니다.</div>';
    }
}

function renderDateChips(dates) {
    const recent = dates.slice(0, 14); // Show up to 14 recent dates

    elements.recentButtons.innerHTML = recent.map(date =>
        `<button class="chip ${date === state.currentDate ? 'active' : ''}" onclick="loadSummary('${date}')">${date}</button>`
    ).join('');
}

async function loadSummary(date) {
    state.currentDate = date;

    // Update Chips UI
    document.querySelectorAll('.chip').forEach(chip => {
        if (chip.textContent === date) chip.classList.add('active');
        else chip.classList.remove('active');
    });

    elements.summaryContent.innerHTML = '<div class="text-center" style="padding:40px">📡 요약 로딩 중...</div>';

    updateTabInfo(date);

    try {
        const response = await fetch(`/api/summary/${date}?category=${state.currentCategory}`);
        if (!response.ok) throw new Error('Summary not found');

        const data = await response.json();
        renderSummary(data);
    } catch (error) {
        console.error(error);
        elements.summaryContent.innerHTML = '<div class="text-center" style="padding:40px">❌ 요약을 불러올 수 없습니다.</div>';
    }
}

function renderSummary(data) {
    const articles = parseSummaryText(data.summary);
    const aiProvider = data.ai_provider || 'gemini';

    if (articles.length === 0) {
        elements.summaryContent.innerHTML = `<div class="card"><div class="text-center">${data.summary.replace(/\n/g, '<br>')}</div></div>`;
        return;
    }

    const html = articles.map((article, idx) => `
        <article class="article-item">
            <div class="article-header">
                <span class="article-index">${idx + 1}</span>
                <div style="flex:1">
                    <h3 class="article-title">${article.title}</h3>
                    ${article.source ? `<span class="article-source">${article.source}</span>` : ''}
                </div>
            </div>
            <div class="article-summary">${article.summary}</div>
            ${article.link ? `<a href="${article.link}" target="_blank" class="btn btn-primary">🔗 원문 보기</a>` : ''}
        </article>
    `).join('');

    elements.summaryContent.innerHTML = `
        <div style="margin-bottom:16px; text-align:right; font-size:0.8rem; color:var(--md-sys-color-secondary);">
            Powered by ${aiProvider === 'perplexity' ? 'Perplexity Sonar' : 'Google Gemini'}
        </div>
        ${html}
    `;
}

// Helper: Parse the specific text format from the backend
function parseSummaryText(text) {
    const lines = text.split('\n');
    const articles = [];
    let currentArticle = null;
    const headerPattern = /^(\d+)\.\s*(.+?)(?:\s*\(([^)]+)\))?$/;

    for (const line of lines) {
        const trimmed = line.trim();
        if (!trimmed) continue;

        if (trimmed.startsWith('📰')) {
            if (currentArticle) articles.push(currentArticle);

            const headerText = trimmed.replace('📰', '').trim();
            let title = headerText;
            let source = '';

            const match = headerText.match(headerPattern);
            if (match) {
                title = match[2].trim();
                source = match[3] ? match[3].trim() : '';
            }

            currentArticle = { title, source, summary: '', link: '' };
        } else if (trimmed.startsWith('📝')) {
            if (currentArticle) currentArticle.summary = trimmed.replace('📝', '').trim();
        } else if (trimmed.startsWith('🔗')) {
            if (currentArticle) currentArticle.link = trimmed.replace('🔗', '').trim();
        }
    }
    if (currentArticle) articles.push(currentArticle);

    return articles;
}

function updateTabInfo(date) {
    const msg = TAB_BASE_MESSAGES[state.currentCategory];
    elements.tabInfo.innerHTML = `${msg} <strong style="color:var(--md-sys-color-primary)">(선택된 날짜: ${date})</strong>`;
}

async function searchByDate() {
    const date = elements.datePicker.value;
    if (!date) return alert('날짜를 선택해주세요.');
    await loadSummary(date);
}
