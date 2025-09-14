document.addEventListener("DOMContentLoaded", () => {
    // 법령 목록 불러오기
    fetch("/laws")
        .then(res => res.json())
        .then(laws => {
            const lawListDiv = document.getElementById("lawList");
            lawListDiv.innerHTML = `<label><input type="checkbox" value="전체" checked> 전체</label><br>`;
            laws.forEach(law => {
                lawListDiv.innerHTML += `<label><input type="checkbox" value="${law}"> ${law}</label><br>`;
            });
        });

    // 검색 버튼 클릭 이벤트
    document.getElementById("searchBtn").addEventListener("click", () => {
        const mode = document.getElementById("mode").value;
        const keywords = document.getElementById("keywords").value.split(",").map(k => k.trim()).filter(k => k);
        const exclude = document.getElementById("exclude").value.split(",").map(k => k.trim()).filter(k => k);
        const selectedLaws = Array.from(document.querySelectorAll("#lawList input[type=checkbox]:checked")).map(cb => cb.value);

        fetch("/search", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ mode, keywords, exclude, laws: selectedLaws })
        })
        .then(res => res.json())
        .then(data => renderTable(data));
    });
});

function renderTable(data) {
    const tbody = document.querySelector("#resultTable tbody");
    tbody.innerHTML = "";
    data.forEach(item => {
        const tr = document.createElement("tr");
        tr.innerHTML = `
            <td>${item.법령명 || ""}</td>
            <td>${item.사건명 || ""}</td>
            <td>${item.판례내용 || ""}</td>
        `;
        tbody.appendChild(tr);
    });
}