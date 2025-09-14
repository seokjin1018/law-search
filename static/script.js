document.addEventListener("DOMContentLoaded", () => {
    fetch("/laws")
        .then(res => res.json())
        .then(laws => {
            const container = document.getElementById("lawList");
            const allLabel = document.createElement("label");
            const allCheckbox = document.createElement("input");
            allCheckbox.type = "checkbox";
            allCheckbox.value = "전체";
            allCheckbox.id = "checkAll";
            allCheckbox.checked = true;
            allLabel.appendChild(allCheckbox);
            allLabel.appendChild(document.createTextNode(" 전체"));
            container.appendChild(allLabel);
            container.appendChild(document.createElement("br"));
            laws.forEach(law => {
                const label = document.createElement("label");
                const checkbox = document.createElement("input");
                checkbox.type = "checkbox";
                checkbox.value = law;
                checkbox.checked = true;
                label.appendChild(checkbox);
                label.appendChild(document.createTextNode(" " + law));
                container.appendChild(label);
                container.appendChild(document.createElement("br"));
            });
            allCheckbox.addEventListener("change", () => {
                const checkboxes = container.querySelectorAll("input[type=checkbox]");
                checkboxes.forEach(cb => {
                    if (cb !== allCheckbox) cb.checked = allCheckbox.checked;
                });
            });
        });

    document.getElementById("mode").addEventListener("change", () => {
        const mode = document.getElementById("mode").value;
        const help = document.getElementById("modeHelp");
        if (mode === "AND_OR") {
            help.innerHTML = `AND_OR 모드: 첫 번째 키워드는 반드시 포함, 두 번째 또는 세 번째 키워드 중 하나라도 포함된 결과를 보여줍니다.<br>예) "민법, 계약, 해지"`;
        } else if (mode === "AND") {
            help.textContent = "AND 모드: 쉼표로 구분된 모든 키워드가 포함된 결과를 보여줍니다.";
        } else if (mode === "OR") {
            help.textContent = "OR 모드: 키워드 중 하나라도 포함된 결과를 보여줍니다.";
        } else if (mode === "SINGLE") {
            help.textContent = "SINGLE 모드: 첫 번째 키워드가 포함된 결과를 보여줍니다.";
        }
    });

    document.getElementById("keywords").addEventListener("keydown", (e) => {
        if (e.key === "Enter") {
            e.preventDefault();
            document.getElementById("exclude").focus();
        }
    });

    document.getElementById("exclude").addEventListener("keydown", (e) => {
        if (e.key === "Enter") {
            e.preventDefault();
            search();
        }
    });

    document.getElementById("searchBtn").addEventListener("click", search);
});

function search() {
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
    .then(data => {
        renderTable(data);
    });
}

function formatIssueText(text) {
    return text
        .replace(/\[([2-9]|\d{2,})\]/g, '\n[$1]')
        .replace(/([②-⑳])/g, '\n$1')
        .replace(/(\d+\.)/g, '\n$1');
}

function renderTable(data) {
    if (!data.length) {
        document.getElementById("result").innerHTML = "<p>검색 결과가 없습니다.</p>";
        return;
    }
    const columnOrder = ["판례 정보", "제목", "쟁점", "선정이유"];
    let table = "<table><thead><tr>";
    columnOrder.forEach(col => {
        table += `<th class="${col === '판례 정보' ? 'caseinfo' : col === '제목' ? 'title' : col === '쟁점' ? 'issue' : 'reason'}">${col}</th>`;
    });
    table += "</tr></thead><tbody>";
    const regex = /\b\d{2,4}[가-힣]{1,3}\d+\b/;
    data.forEach(row => {
        table += "<tr>";
        columnOrder.forEach(col => {
            let val = row[col];
            if (typeof val === "object") val = JSON.stringify(val);
            if (col === "쟁점" && typeof val === "string") val = formatIssueText(val);
            if (col === "판례 정보" && typeof val === "string") {
                const match = val.match(regex);
                if (match) {
                    const caseNo = match[0];
                    const link = `https://casenote.kr/대법원/${encodeURIComponent(caseNo)}`;
                    table += `<td class="caseinfo"><a href="${link}" target="_blank">${val}</a></td>`;
                    return;
                }
            }
            // 하이라이트 HTML이 포함될 수 있으므로 innerHTML로 넣기
            table += `<td class="${col === '판례 정보' ? 'caseinfo' : col === '제목' ? 'title' : col === '쟁점' ? 'issue' : 'reason'}">${val || ''}</td>`;
        });
        table += "</tr>";
    });
    table += "</tbody></table>";
    document.getElementById("result").innerHTML = table;
}