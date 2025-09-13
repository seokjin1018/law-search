document.getElementById("searchBtn").addEventListener("click", () => {
    const mode = document.getElementById("mode").value;
    const keywords = document.getElementById("keywords").value.split(",").map(k => k.trim()).filter(k => k);
    const exclude = document.getElementById("exclude").value.split(",").map(k => k.trim()).filter(k => k);

    fetch("/search", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ mode, keywords, exclude })
    })
    .then(res => res.json())
    .then(data => {
        renderTable(data);
    });
});

function renderTable(data) {
    if (!data.length) {
        document.getElementById("result").innerHTML = "<p>검색 결과가 없습니다.</p>";
        return;
    }

    let table = "<table><thead><tr>";
    Object.keys(data[0]).forEach(key => {
        table += `<th>${key}</th>`;
    });
    table += "</tr></thead><tbody>";

    const caseTypes = ["다", "도", "두", "헌가", "헌나", "헌다", "헌라", "헌마", "헌바"];
    const regex = new RegExp(`(\\d{4}|\\d{2})(${caseTypes.join("|")})\\d+`);

    data.forEach(row => {
        table += "<tr>";
        Object.entries(row).forEach(([key, val]) => {
            if (typeof val === "object") {
                val = JSON.stringify(val);
            }
            if (typeof val === "string") {
                const match = val.match(regex);
                if (match) {
                    const caseNo = match[0];
                    const link = `https://casenote.kr/대법원/${encodeURIComponent(caseNo)}`;
                    table += `<td><a href="${link}" target="_blank">${val}</a></td>`;
                    return;
                }
            }
            table += `<td>${val}</td>`;
        });
        table += "</tr>";
    });

    table += "</tbody></table>";
    document.getElementById("result").innerHTML = table;
}