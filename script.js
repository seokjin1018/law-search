// ===== 전역 변수 =====
let isLogin = false;
let bookmarkSet = new Set();
let currentSearchType = null;
let currentSearchKeywords = [];
let currentPage = { legacy: 1, criminal: 1 };
let currentBookmarkPages = { legacy: 1, criminal: 1 };

// ===== 초기화 및 내비게이션 =====
document.addEventListener("DOMContentLoaded", async () => {
  window.addEventListener("hashchange", handleNavigation);
  await checkLoginStatus();
  handleNavigation();
  initLegacyLawCheckboxes();
  criminalInitLawAndArticleDropdowns();
});

function handleNavigation() {
  const hash = window.location.hash;
  const searchPage = document.getElementById("search-page");
  const bookmarksPage = document.getElementById("bookmarks-page");
  const resultsWrapper = document.getElementById("results-wrapper");
  if (hash === "#bookmarks" && isLogin) {
    searchPage.classList.add("hidden");
    resultsWrapper.classList.add("hidden");
    bookmarksPage.classList.remove("hidden");
    showBookmarks("all");
  } else {
    searchPage.classList.remove("hidden");
    resultsWrapper.classList.remove("hidden");
    bookmarksPage.classList.add("hidden");
    if (hash !== "#search") {
      window.location.hash = "search";
    }
  }
}

function navigateTo(page) {
  window.location.hash = page;
}

// ===== 인증 =====
async function checkLoginStatus() {
  return fetch("/whoami")
    .then((res) => res.json())
    .then((data) => {
      const whoamiBar = document.getElementById("whoamiBar");
      const authBar = document.getElementById("authBar");
      if (data.nickname) {
        isLogin = true;
        whoamiBar.classList.remove("hidden");
        authBar.classList.add("hidden");
        whoamiBar.querySelector(".whoami").textContent = data.nickname;
        bookmarkSet = new Set(
          (data.bookmarks || []).map((bm) => `${bm.type}__${bm.제목}`)
        );
      } else {
        isLogin = false;
        whoamiBar.classList.add("hidden");
        authBar.classList.remove("hidden");
        bookmarkSet.clear();
      }
    })
    .catch((error) => {
      console.error("Auth check failed:", error);
      isLogin = false;
      document.getElementById("authBar").classList.remove("hidden");
      document.getElementById("whoamiBar").classList.add("hidden");
    });
}

async function signup() {
  const nickname = document.getElementById("nickname").value;
  const password = document.getElementById("password").value;
  const response = await fetch("/signup", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ nickname, password }),
  });
  const data = await response.json();
  alert(data.message || data.error);
  if (response.ok) {
    document.getElementById("nickname").value = "";
    document.getElementById("password").value = "";
  }
}
async function login() {
  const nickname = document.getElementById("nickname").value;
  const password = document.getElementById("password").value;
  const response = await fetch("/login", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ nickname, password }),
  });
  const data = await response.json();
  if (response.ok) {
    alert("로그인 성공!");
    await checkLoginStatus();
    handleNavigation();
  } else {
    alert(data.error);
  }
}
async function logout() {
  await fetch("/logout", { method: "POST" });
  alert("로그아웃 되었습니다.");
  isLogin = false;
  await checkLoginStatus();
  handleNavigation();
}

// ===== 법령 체크박스 =====
async function initLegacyLawCheckboxes() {
  const container = document.getElementById("legacy-laws-container");
  try {
    const laws = await fetch("/laws").then((res) => res.json());
    let checkboxesHTML = `<label><input type="checkbox" id="legacy-law-all" onchange="toggleAllLegacyLaws(this.checked)"> <strong>전체</strong></label>`;
    checkboxesHTML += laws
      .map(
        (law) =>
          `<label><input type="checkbox" name="legacy-law" value="${law}" onchange="updateAllCheckboxState()"> ${law}</label>`
      )
      .join("");
    container.innerHTML = checkboxesHTML;
  } catch (e) {
    container.innerHTML = "법령 목록 로딩 실패";
  }
}

function toggleAllLegacyLaws(isChecked) {
  document
    .getElementsByName("legacy-law")
    .forEach((cb) => (cb.checked = isChecked));
}

function updateAllCheckboxState() {
  const allCheckbox = document.getElementById("legacy-law-all");
  const lawCheckboxes = [...document.getElementsByName("legacy-law")];
  allCheckbox.checked = lawCheckboxes.every((cb) => cb.checked);
  allCheckbox.indeterminate =
    !allCheckbox.checked && lawCheckboxes.some((cb) => cb.checked);
}

// ===== 검색 =====
async function performSearch(type, page = 1) {
  document
    .getElementById("results-wrapper")
    .scrollIntoView({ behavior: "smooth", block: "start" });
  currentSearchType = type;
  currentPage[type] = page;

  const keywordsInput = document.getElementById(`${type}-keywords`);
  const searchBtn = document.getElementById(`${type}-search-btn`);
  const loader = document.getElementById("loader");

  currentSearchKeywords = keywordsInput.value
    .split(",")
    .map((k) => k.trim())
    .filter(Boolean);
  let payload = {
    keywords: currentSearchKeywords,
    exclude: document
      .getElementById(`${type}-exclude`)
      .value.split(",")
      .map((k) => k.trim())
      .filter(Boolean),
    mode: document.getElementById(`${type}-mode`).value,
    sortBy: document.getElementById(`${type}-sort`).value,
    page,
    pageSize: 20,
  };

  if (type === "legacy") {
    const checkedLaws = [...document.getElementsByName("legacy-law")]
      .filter((cb) => cb.checked)
      .map((cb) => cb.value);
    payload.laws = document.getElementById("legacy-law-all").checked
      ? []
      : checkedLaws;
  } else {
    payload.selectedLaw = document.getElementById("criminalLawSelect").value;
    payload.selectedArticle = document.getElementById(
      "criminalArticleSelect"
    ).value;
  }

  loader.style.display = "block";
  if (searchBtn) searchBtn.disabled = true;
  document.getElementById("results").innerHTML = "";
  document.getElementById("pagination").innerHTML = "";
  const resultsCountEl = document.getElementById("results-count");
  if (resultsCountEl) resultsCountEl.textContent = "";

  try {
    const response = await fetch(
      type === "legacy" ? "/search" : "/criminal/search",
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      }
    );
    const data = await response.json();

    displayResults(data.results, type, "search");
    if (resultsCountEl && data.total > 0)
      resultsCountEl.textContent = `(총 ${data.total}개)`;
    createPagination("search", type, data.total, page, 20);
  } catch (error) {
    document.getElementById("results").innerHTML =
      "<p>검색 중 오류가 발생했습니다.</p>";
  } finally {
    loader.style.display = "none";
    if (searchBtn) searchBtn.disabled = false;
  }
}

// ===== 북마크 =====
async function showBookmarks(type, page, bookmarkType) {
  if (bookmarkType) {
    currentBookmarkPages[bookmarkType] = page;
  } else {
    currentBookmarkPages = { legacy: 1, criminal: 1 };
  }

  const loader = document.getElementById("loader");
  loader.style.display = "block";

  try {
    const response = await fetch(
      `/bookmarks?type=${type}&legacy_page=${currentBookmarkPages.legacy}&criminal_page=${currentBookmarkPages.criminal}`
    );
    const data = await response.json();

    const legacySection = document.getElementById("legacy-bookmark-section");
    const criminalSection = document.getElementById(
      "criminal-bookmark-section"
    );
    legacySection.style.display =
      type === "all" || type === "legacy" ? "block" : "none";
    criminalSection.style.display =
      type === "all" || type === "criminal" ? "block" : "none";

    document.getElementById("legacy-bookmark-results").innerHTML = "";
    document.getElementById("criminal-bookmark-results").innerHTML = "";

    if (data.legacy) {
      document.getElementById(
        "legacy-bookmark-count"
      ).textContent = `(총 ${data.legacy.total}개)`;
      displayResults(data.legacy.results, "legacy", "bookmark");
      createPagination(
        "bookmark",
        "legacy",
        data.legacy.total,
        data.legacy.page,
        10
      );
      if (bookmarkType === "legacy")
        legacySection.scrollIntoView({ behavior: "smooth", block: "start" });
    }
    if (data.criminal) {
      document.getElementById(
        "criminal-bookmark-count"
      ).textContent = `(총 ${data.criminal.total}개)`;
      displayResults(data.criminal.results, "criminal", "bookmark");
      createPagination(
        "bookmark",
        "criminal",
        data.criminal.total,
        data.criminal.page,
        10
      );
      if (bookmarkType === "criminal")
        criminalSection.scrollIntoView({ behavior: "smooth", block: "start" });
    }
  } catch (e) {
    console.error("Error fetching bookmarks:", e);
  } finally {
    loader.style.display = "none";
  }
}

// ===== 결과 렌더링 =====
function displayResults(results, type, context) {
  let resultsDiv;
  if (context === "search") resultsDiv = document.getElementById("results");
  else if (type === "legacy")
    resultsDiv = document.getElementById("legacy-bookmark-results");
  else resultsDiv = document.getElementById("criminal-bookmark-results");

  if (context !== "search") resultsDiv.innerHTML = "";
  if (!results || results.length === 0) {
    resultsDiv.innerHTML = `<p>${
      context.includes("bookmark") ? "북마크가" : "검색 결과가"
    } 없습니다.</p>`;
    return;
  }

  results.forEach((item) => {
    const itemType = item.type || type;
    const key = `${itemType}__${item.제목}`;
    const isBookmarked = bookmarkSet.has(key);
    const itemDiv = document.createElement("div");
    itemDiv.className = "result-item";

    let headerContent = `<h3>${highlightText(item["제목"] || "")}</h3>`;

    let bodyContent = "";
    if (itemType === "legacy") {
      let caseInfoText = item["판례 정보"] || "";
      let highlightedCaseInfo = highlightText(caseInfoText);
      const match = caseInfoText.match(/\b\d{2,4}[가-힣]{1,3}\d+\b/);
      if (match) {
        const link = `https://casenote.kr/대법원/${encodeURIComponent(
          match[0]
        )}`;
        highlightedCaseInfo = `<a href="${link}" target="_blank">${highlightedCaseInfo}</a>`;
      }
      bodyContent += `<p><strong>판례 정보:</strong> ${highlightedCaseInfo}</p>`;
      bodyContent += `<p><strong>법령명:</strong> ${highlightText(
        item["법령명"] || ""
      )}</p>`;
      bodyContent += `<p><strong>쟁점:</strong> ${highlightText(
        item["쟁점"] || ""
      )}</p>`;
      bodyContent += `<p><strong>선정이유:</strong> ${highlightText(
        item["선정이유"] || ""
      )}</p>`;
    } else {
      let caseNoText = item["사건번호"] || "";
      let highlightedCaseNo = highlightText(caseNoText);
      if (caseNoText) {
        const link = `https://casenote.kr/대법원/${encodeURIComponent(
          caseNoText
        )}`;
        highlightedCaseNo = `<a href="${link}" target="_blank">${highlightedCaseNo}</a>`;
      }
      bodyContent += `<p><strong>사건번호:</strong> ${highlightedCaseNo}</p>`;
      bodyContent += `<p><strong>선고일자:</strong> ${highlightText(
        item["선고일자"] || item["선고일"] || ""
      )}</p>`;
      bodyContent += `<p><strong>판시사항:</strong> ${highlightText(
        item["판시사항"] || ""
      )}</p>`;
      bodyContent += `<p><strong>참조조문:</strong> ${highlightText(
        item["참조조문"] || ""
      )}</p>`;
    }

    let bookmarkButton = "";
    if (isLogin) {
      bookmarkButton = `<button class="bookmark-btn" style="color: ${
        isBookmarked ? "gold" : "black"
      }" onclick="toggleBookmark(this, '${itemType}', \`${item.제목}\`)">${
        isBookmarked ? "★" : "☆"
      }</button>`;
    }

    itemDiv.innerHTML = `<div class="result-item-header">${headerContent}${bookmarkButton}</div>${bodyContent}`;
    resultsDiv.appendChild(itemDiv);
  });
}

// ===== 유틸리티 =====
function highlightText(text) {
  if (!currentSearchKeywords.length || !text) return String(text);
  const textStr = String(text);
  const regex = new RegExp(
    currentSearchKeywords
      .map(
        (k) =>
          k
            .replace(/[.*+?^${}()|[\]\\]/g, "\\$&") // 특수문자 이스케이프
            .split("") // 한 글자씩 분리
            .join("\\s*") // 글자 사이에 \s* 허용
      )
      .join("|"),
    "gi"
  );

  return textStr.replace(
    regex,
    (match) => `<mark class="highlight">${match}</mark>`
  );
}

function createPagination(context, type, total, page, pageSize) {
  let paginationDiv;
  if (context === "search")
    paginationDiv = document.getElementById("pagination");
  else if (context === "bookmark" && type === "legacy")
    paginationDiv = document.getElementById("legacy-bookmark-pagination");
  else paginationDiv = document.getElementById("criminal-bookmark-pagination");

  paginationDiv.innerHTML = "";
  const totalPages = Math.ceil(total / pageSize);
  if (totalPages <= 1) return;

  const createButton = (text, pageNum, isDisabled = false) => {
    const button = document.createElement("button");
    button.innerHTML = text;
    button.disabled = isDisabled;
    button.onclick = () => {
      if (context === "search") performSearch(type, pageNum);
      else showBookmarks(type, pageNum, type);
    };
    return button;
  };

  paginationDiv.appendChild(createButton("<<", 1, page === 1));
  paginationDiv.appendChild(createButton("<", page - 1, page === 1));

  let startPage = Math.max(1, page - 2),
    endPage = Math.min(totalPages, page + 2);
  if (page <= 3) endPage = Math.min(totalPages, 5);
  if (page >= totalPages - 2) startPage = Math.max(1, totalPages - 4);

  for (let i = startPage; i <= endPage; i++) {
    const button = createButton(i, i);
    if (i === page) button.className = "active";
    paginationDiv.appendChild(button);
  }

  paginationDiv.appendChild(createButton(">", page + 1, page === totalPages));
  paginationDiv.appendChild(
    createButton(">>", totalPages, page === totalPages)
  );
}

function showHelpModal() {
  document.getElementById("help-modal").style.display = "flex";
}
function closeHelpModal() {
  document.getElementById("help-modal").style.display = "none";
}

async function criminalInitLawAndArticleDropdowns() {
  const lawSelect = document.getElementById("criminalLawSelect");
  const articleSelect = document.getElementById("criminalArticleSelect");
  const laws = await fetch("/criminal/laws")
    .then((res) => res.json())
    .catch(() => []);
  lawSelect.innerHTML +=
    '<option value="">법령 선택 (전체)</option>' +
    laws.map((l) => `<option value="${l}">${l}</option>`).join("");
  lawSelect.addEventListener("change", async () => {
    const law = lawSelect.value;
    articleSelect.innerHTML = `<option value="">조문 선택 (전체)</option>`;
    if (!law) return;
    const items = await fetch(
      `/criminal/articles?law=${encodeURIComponent(law)}`
    )
      .then((res) => res.json())
      .catch(() => []);
    articleSelect.innerHTML += items
      .map((item) => `<option value="${item}">${item}</option>`)
      .join("");
  });
}
async function toggleBookmark(button, type, title) {
  if (!isLogin) {
    alert("로그인이 필요합니다.");
    return;
  }
  const key = `${type}__${title}`;
  const isBookmarked = bookmarkSet.has(key);
  const url = isBookmarked ? "/bookmarks/remove" : "/bookmarks/add";
  const response = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ 제목: title, type: type }),
  });
  if (response.ok) {
    const data = await response.json();
    bookmarkSet = new Set(data.bookmarks.map((bm) => `${bm.type}__${bm.제목}`));
    if (window.location.hash === "#bookmarks") {
      const currentView =
        document.getElementById("legacy-bookmark-section").style.display !==
          "none" &&
        document.getElementById("criminal-bookmark-section").style.display !==
          "none"
          ? "all"
          : document.getElementById("legacy-bookmark-section").style.display !==
            "none"
          ? "legacy"
          : "criminal";
      showBookmarks(currentView);
    } else {
      button.textContent = isBookmarked ? "☆" : "★";
      button.style.color = isBookmarked ? "black" : "gold";
    }
  } else {
    alert("요청에 실패했습니다.");
  }
}
