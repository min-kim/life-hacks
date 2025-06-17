let flashcardsData = [];
let currentCardIndex = 0;
let learningCards = [];
let knownCards = [];
let displayState = 'hanja';
let intervalId;

const LOCAL_STORAGE_KEY_PREFIX = 'hanjaFlashcard_';
let currentLoadedFileName = '';

const cardContentDisplay = document.getElementById('card-content');
const knownBtn = document.getElementById('known-btn');
const unknownBtn = document.getElementById('unknown-btn');
const downloadRemainingBtn = document.getElementById('download-remaining-btn'); // 새로 추가된 버튼
const remainingCountSpan = document.getElementById('remaining-count');
const flashcardArea = document.getElementById('flashcard-area');
const noCardsMessage = document.getElementById('no-cards-message');
const resetBtn = document.getElementById('reset-btn');

const fileSelectionSection = document.querySelector('.file-selection-section');
const presetHanjaSelect = document.getElementById('preset-hanja-select');
const loadPresetBtn = document.getElementById('load-preset-btn');
const hanjaFileInput = document.getElementById('hanja-file-input');
const fileNameDisplay = document.getElementById('file-name-display');
const loadCustomFileBtn = document.getElementById('load-custom-file-btn');
const fileErrorMessage = document.getElementById('file-error-message');

const HANJA_DISPLAY_TIME = 3000;
const MEANING_DISPLAY_TIME = 3000;

// --- 파일 로드 관련 함수 (이전과 동일) ---
presetHanjaSelect.addEventListener('change', () => {
    if (presetHanjaSelect.value) {
        loadPresetBtn.disabled = false;
        fileErrorMessage.style.display = 'none';
    } else {
        loadPresetBtn.disabled = true;
    }
});

loadPresetBtn.addEventListener('click', async () => {
    const filePath = presetHanjaSelect.value;
    if (filePath) {
        currentLoadedFileName = filePath.split('/').pop().split('.')[0];
        await loadAndProcessFile(filePath, 'preset');
    } else {
        showError('세트를 선택해 주세요.');
    }
});

hanjaFileInput.addEventListener('change', (event) => {
    const file = event.target.files[0];
    if (file) {
        fileNameDisplay.textContent = file.name;
        loadCustomFileBtn.disabled = false;
        fileErrorMessage.style.display = 'none';
        currentLoadedFileName = file.name.split('.')[0];
    } else {
        fileNameDisplay.textContent = '내 CSV 파일 업로드';
        loadCustomFileBtn.disabled = true;
    }
});

loadCustomFileBtn.addEventListener('click', async () => {
    const file = hanjaFileInput.files[0];
    if (file) {
        if (!file.name.endsWith('.csv')) {
            showError('CSV 파일만 업로드할 수 있습니다.');
            return;
        }
        await loadAndProcessFile(file, 'custom');
    } else {
        showError('먼저 CSV 파일을 선택해 주세요.');
    }
});

async function loadAndProcessFile(source, type) {
    let csvContent = '';
    fileErrorMessage.style.display = 'none';

    try {
        if (type === 'preset') {
            const response = await fetch(source);
            if (!response.ok) {
                throw new Error(`파일을 불러오는 데 실패했습니다: ${response.statusText}`);
            }
            csvContent = await response.text();
        } else { // type === 'custom'
            csvContent = await new Promise((resolve, reject) => {
                const reader = new FileReader();
                reader.onload = (e) => resolve(e.target.result);
                reader.onerror = (e) => reject(new Error('파일 읽기 오류: ' + reader.error));
                reader.readAsText(source, 'UTF-8');
            });
        }

        flashcardsData = parseCSV(csvContent);
        if (flashcardsData.length === 0) {
            showError('파일에서 유효한 한자 데이터를 찾을 수 없습니다.');
            return;
        }
        
        fileSelectionSection.style.display = 'none';
        initializeCards();

    } catch (error) {
        showError('파일을 처리하는 중 오류가 발생했습니다: ' + error.message);
        console.error('Error loading or processing file:', error);
    }
}

function parseCSV(csvText) {
    const lines = csvText.split('\n');
    const parsedData = [];
    for (const line of lines) {
        const trimmedLine = line.trim();
        if (trimmedLine) {
            const columns = trimmedLine.split(',');
            if (columns.length >= 3) {
                const hanja = columns[0].trim();
                const meaning = columns[1].trim();
                const sound = columns[2].trim();
                parsedData.push({ hanja: hanja, meaning: `${meaning} (${sound})` });
            } else if (columns.length === 2) {
                const hanja = columns[0].trim();
                const meaningSound = columns[1].trim();
                parsedData.push({ hanja: hanja, meaning: meaningSound });
            }
        }
    }
    return parsedData;
}

function showError(message) {
    fileErrorMessage.textContent = message;
    fileErrorMessage.style.display = 'block';
    console.error(message);
}


// --- 플래시카드 학습 로직 (로컬 스토리지 및 다운로드 추가) ---

function initializeCards() {
    if (intervalId) {
        clearInterval(intervalId);
    }

    const savedData = loadLearningState(currentLoadedFileName);

    if (savedData && savedData.learningCards.length > 0) {
        learningCards = savedData.learningCards;
        currentCardIndex = savedData.currentCardIndex;
        console.log(`학습 재개: ${learningCards.length}개의 카드`);
    } else {
        learningCards = [...flashcardsData];
        currentCardIndex = 0;
        shuffleCards();
        console.log(`새로운 학습 시작: ${learningCards.length}개의 카드`);
    }
    
    updateRemainingCount();
    flashcardArea.style.display = 'block';
    noCardsMessage.style.display = 'none';
    
    startCardCycle();
}

function saveLearningState(fileName) {
    const dataToSave = {
        learningCards: learningCards,
        currentCardIndex: currentCardIndex
    };
    try {
        localStorage.setItem(LOCAL_STORAGE_KEY_PREFIX + fileName, JSON.stringify(dataToSave));
        console.log('학습 상태 저장됨.');
    } catch (e) {
        console.error('로컬 스토리지 저장 실패:', e);
    }
}

function loadLearningState(fileName) {
    try {
        const savedData = localStorage.getItem(LOCAL_STORAGE_KEY_PREFIX + fileName);
        if (savedData) {
            return JSON.parse(savedData);
        }
    } catch (e) {
        console.error('로컬 스토리지 불러오기 실패:', e);
        localStorage.removeItem(LOCAL_STORAGE_KEY_PREFIX + fileName);
    }
    return null;
}

function shuffleCards() {
    for (let i = learningCards.length - 1; i > 0; i--) {
        const j = Math.floor(Math.random() * (i + 1));
        [learningCards[i], learningCards[j]] = [learningCards[j], learningCards[i]];
    }
}

function updateCardContent() {
    if (learningCards.length === 0) {
        clearInterval(intervalId);
        flashcardArea.style.display = 'none';
        noCardsMessage.style.display = 'block';
        saveLearningState(currentLoadedFileName);
        return;
    }

    const card = learningCards[currentCardIndex];

    if (displayState === 'hanja') {
        cardContentDisplay.textContent = card.hanja;
        cardContentDisplay.className = 'hanja-text';
        intervalId = setTimeout(() => {
            displayState = 'meaning';
            updateCardContent();
        }, HANJA_DISPLAY_TIME);
    } else {
        cardContentDisplay.textContent = card.meaning;
        cardContentDisplay.className = 'meaning-text';
        intervalId = setTimeout(() => {
            displayState = 'hanja';
            moveToNextCard();
        }, MEANING_DISPLAY_TIME);
    }
}

function moveToNextCard() {
    currentCardIndex++;
    if (currentCardIndex >= learningCards.length) {
        currentCardIndex = 0;
    }
    saveLearningState(currentLoadedFileName);
    updateCardContent();
}

function startCardCycle() {
    displayState = 'hanja';
    updateCardContent();
}

function updateRemainingCount() {
    remainingCountSpan.textContent = learningCards.length;
}

knownBtn.addEventListener('click', () => {
    clearInterval(intervalId);
    learningCards.splice(currentCardIndex, 1);

    if (learningCards.length === 0) {
        updateCardContent();
    } else {
        if (currentCardIndex >= learningCards.length) {
            currentCardIndex = 0;
        }
        startCardCycle();
        updateRemainingCount();
        saveLearningState(currentLoadedFileName);
    }
});

unknownBtn.addEventListener('click', () => {
    clearInterval(intervalId);
    const cardToMove = learningCards.splice(currentCardIndex, 1)[0];
    learningCards.push(cardToMove);
    
    if (currentCardIndex >= learningCards.length) {
         currentCardIndex = 0;
    }
    startCardCycle();
    updateRemainingCount();
    saveLearningState(currentLoadedFileName);
});

resetBtn.addEventListener('click', () => {
    clearInterval(intervalId);
    if (currentLoadedFileName) {
        localStorage.removeItem(LOCAL_STORAGE_KEY_PREFIX + currentLoadedFileName);
        console.log(`저장된 학습 상태 "${currentLoadedFileName}" 초기화됨.`);
    }

    fileSelectionSection.style.display = 'block';
    flashcardArea.style.display = 'none';
    noCardsMessage.style.display = 'none';
    hanjaFileInput.value = '';
    fileNameDisplay.textContent = '내 CSV 파일 업로드';
    loadCustomFileBtn.disabled = true;
    fileErrorMessage.style.display = 'none';
    presetHanjaSelect.value = '';
    loadPresetBtn.disabled = true;
    flashcardsData = [];
    learningCards = [];
    currentCardIndex = 0;
});

// --- 남은 단어 다운로드 기능 추가 ---
downloadRemainingBtn.addEventListener('click', () => {
    if (learningCards.length === 0) {
        alert('현재 학습할 남은 단어가 없습니다.');
        return;
    }
    
    const csvContent = convertToCSV(learningCards);
    const fileName = `남은_한자_(${currentLoadedFileName || 'unknown_set'}_${new Date().toLocaleDateString()}).csv`;
    downloadCSV(csvContent, fileName);
});

// JavaScript 배열을 CSV 문자열로 변환하는 함수
function convertToCSV(dataArray) {
    const csvRows = [];
    // 헤더 추가 (선택 사항)
    // csvRows.push('한자,뜻,음'); // CSV 파일에 헤더가 필요하다면 이 줄을 추가합니다.

    for (const card of dataArray) {
        // '뜻 (음)' 형태에서 '뜻', '음'을 분리
        const meaningMatch = card.meaning.match(/(.+)\s+\((.+)\)/);
        let meaningPart = card.meaning;
        let soundPart = '';

        if (meaningMatch && meaningMatch.length === 3) {
            meaningPart = meaningMatch[1].trim();
            soundPart = meaningMatch[2].trim();
        } else {
            // '(음)' 형식이 아니면 전체를 뜻으로 간주하고 음은 비워둠
            meaningPart = card.meaning.trim();
            soundPart = '';
        }
        
        // CSV 형식에 맞게 따옴표 처리 및 줄바꿈
        // 쉼표가 포함된 필드는 큰따옴표로 묶어야 합니다.
        const hanja = `"${card.hanja.replace(/"/g, '""')}"`;
        const meaning = `"${meaningPart.replace(/"/g, '""')}"`;
        const sound = `"${soundPart.replace(/"/g, '""')}"`;
        
        csvRows.push(`${hanja},${meaning},${sound}`);
    }
    return csvRows.join('\n');
}

// CSV 문자열을 파일로 다운로드하는 함수
function downloadCSV(csvString, fileName) {
    const blob = new Blob([csvString], { type: 'text/csv;charset=utf-8;' });
    const link = document.createElement('a');
    
    if (link.download !== undefined) { // HTML5 download 속성 지원 브라우저
        const url = URL.createObjectURL(blob);
        link.setAttribute('href', url);
        link.setAttribute('download', fileName);
        link.style.visibility = 'hidden';
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
    } else { // 구형 브라우저 대체 (제한적)
        window.open('data:text/csv;charset=utf-8,' + encodeURIComponent(csvString));
    }
}

document.addEventListener('DOMContentLoaded', () => {
    fileSelectionSection.style.display = 'block';
    flashcardArea.style.display = 'none';
    noCardsMessage.style.display = 'none';
    loadCustomFileBtn.disabled = true;
    loadPresetBtn.disabled = true;
});