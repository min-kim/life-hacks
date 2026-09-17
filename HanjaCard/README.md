# HanjaCard: 한자 플래시카드 웹 앱 (Hanja Flashcard Web Application)

한자 학습을 효율적으로 지원하기 위해 JavaScript, HTML5, CSS3 기반으로 구축된 린(Lean) 웹 애플리케이션입니다. 미리 준비된 데이터 세트 선택 및 커스텀 CSV 파일 업로드 기능, 자동 타이머 전환, localStorage 기반의 학습 상태 복원, 그리고 미습득 단어 CSV 추출 기능을 지원합니다. 

*한자에 최적화되어 있으나, 기존 일반 플래시카드로 다루기 까다로웠던 다국어 어휘(일본어 칸지, 성조가 포함된 성어)나 3가지 요소(표기-의미-발음) 결합이 필요한 전문 용어 학습에도 유연하게 활용할 수 있습니다.*

A lightweight, browser-based flashcard application designed for efficient learning of Chinese characters (Hanja). Built with plain JavaScript, HTML5, and CSS3, it offers features such as preset dataset selection, custom CSV file uploads, automatic timer switching, state restoration via localStorage, and exporting unmastered vocabulary. 

*While optimized for Hanja, it can also be seamlessly adapted for complex language vocabulary (such as Japanese Kanji or tonal phrases) and specialized terminology requiring multi-attribute mapping.*

---

## 주요 기능 (Key Features)

* **다양한 입력 경로 (Dual Data Input Options)**
  * 미리 제공되는 프리셋 CSV 데이터 세트 선택 기능
    * Select from pre-loaded preset CSV datasets.
  * 사용자 정의 커스텀 CSV 파일 업로드 기능 (`1열: 한자`, `2열: 뜻`, `3열: 음` 또는 `1열: 한자`, `2열: 뜻(음)` 지원)
    * Upload custom CSV files (supports `Column 1: Character`, `Column 2: Meaning`, `Column 3: Sound` or `Column 1: Character`, `Column 2: Meaning (Sound)`).

* **자동 3초 순환 (Automated Card Cycling)**
  * 한자(3초) -> 뜻/음(3초) 순으로 자동 전환되는 타이머 제어 루틴
    * Automatic timer routine cycling through Hanja (3 sec) -> Meaning/Sound (3 sec).

* **학습 상태 자동 저장 (Progress Persistence via LocalStorage)**
  * 세트별 학습 잔여 카드 및 진행 위치를 localStorage에 자동 보관하여 재방문 시 학습 연속성 유지
    * Automatically saves remaining cards and progress index per set to localStorage, allowing users to resume learning seamlessly upon returning to the browser.

* **알아요/몰라요 분류 (Spaced Repetition Practice)**
  * **알아요 (Known)**: 해당 카드를 잔여 학습 목록에서 완전히 제거
    * Completely removes the card from the remaining review list.
  * **몰라요 (Unknown)**: 해당 카드를 배열의 최후순위로 재배치하여 반복 노출
    * Moves the card to the end of the array for repeated exposure.

* **남은 단어 다운로드 (Export Remaining Vocabularies)**
  * 학습 중 남은 미습득 단어 카드들을 동적으로 CSV 파일 형태로 변환하여 다운로드
    * Dynamically converts and downloads remaining unmastered card data as a CSV file.

---

## 기술 스택 및 구조 (Technical Stack & Architecture)

* **프론트엔드 (Frontend)**: 순수 자바스크립트 (Pure JavaScript - ES6+ Native DOM Engine), HTML5, CSS3
* **데이터 포맷 (Data Format)**: CSV (Comma-Separated Values, UTF-8 Encoding)
* **저장소 엔진 (Storage Engine)**: 브라우저 `window.localStorage` API
* **배포 호환성 (Deployment Compatibility)**: GitHub Pages, Netlify 등 정적 호스팅 서비스 완전 호환 (Fully compatible with static hosting services)

---

## 프로젝트 구조 (File & Directory Layout)

```text
.
├── index.html      # 메인 레이아웃 및 웹 UI (Main layout and UI markup)
├── style.css       # 반응형 UI 및 스타일링 (Responsive styles and component design)
├── script.js       # CSV 파싱, 타이머 제어 및 상태 엔진 (CSV parsing, timer control, state engine)
└── data/       # Preset 한자 CSV 데이터 폴더 (Preset Hanja CSV data directory)
    ├── hanja_set1-5_850char.csv
    ├── hanja_set6-10_938char.csv
    ├── hanja_set11-15_809char.csv
    └── hanja_set16-20_705char.csv

```
---
## CSV 데이터 파일 규격 (CSV File Specification)

CSV 데이터 파일 규격 (CSV File Specification)
자체 제작한 CSV 커스텀 파일을 업로드할 경우 아래 형태 중 하나를 만족해야 합니다.

When uploading custom CSV files, ensure they follow one of the formats below.

* **3열 권장 규격 (Standard Format - 3 Columns Recommended)**
```text
漢,한나라,한
字,글자,자
學,배울,학
```
* **2열 대체 규격 (Alternative Format - 2 Columns)**
```text
漢,한나라 (한)
字,글자 (자)
```
---
## 사용 방법 (Getting Started)

### 1-A. 웹에서 바로 사용하기 (Web Access)
별도의 설치 없이 아래 링크에서 바로 플래시카드를 이용하실 수 있습니다.  
Access and use the application directly in your browser without any installation:

👉 **[한자 플래시카드 앱 바로가기 (Live Demo)](https://hanjacard.netlify.app/)**


### 1-B. 로컬 환경에서 실행하기 (Local Setup)
소스 코드를 내려받아 직접 실행하거나 수정하려는 경우 아래 절차를 따르세요.  
Follow these steps if you wish to run or modify the code locally:


* **해당 앱 폴더를 내려받기 (Sparse-Checkout)**
```bash
git clone --depth 1 --filter=blob:none --sparse https://github.com/min-kim/life-hacks.git
cd life-hacks
git sparse-checkout set hanja_flashcard_generator
cd hanja_flashcard_generator
```

* **실행 (Run)**

index.html 파일을 브라우저에서 실행합니다.

Open index.html in your browser.

### 2. 학습 세트 선택 (Select Set)

* **드롭다운 목록에서 `미리 준비된 세트`를 선택 후 `선택한 세트 불러오기` 버튼을 클릭합니다. 또는 개인 컴퓨터에 저장된 CSV 파일을 선택하고 `내 CSV 파일 업로드` 버튼을 클릭합니다.**
* Choose a `미리 준비된 세트` (Preset Set) from the dropdown menu and click `선택한 세트 불러오기`. Or choose a custom CSV File from your local machine and click `내 CSV 파일 업로드`.

### 3. 학습 진행 (Study)

* **3초간 노출되는 한자를 보고 음과 뜻을 떠올립니다. `알아요` 클릭 시 목록에서 제외되며, `몰라요` 클릭 시 맨 뒤로 이동합니다. 언제든지 `남은 단어 다운로드` 버튼을 눌러 남은 카드만 복습용 CSV 파일로 추출할 수 있습니다.**

* Recall the sound and meaning during the 3-second Hanja display. Click `알아요` (Known) to exclude the card, or `몰라요` (Unknown) to move it to the back of the queue. Click `남은 단어 다운로드` at any time to export remaining cards into a review CSV.

---
## 📜 License
This project is open-source and available under the [MIT License](LICENSE).