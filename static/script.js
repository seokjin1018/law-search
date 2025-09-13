document.getElementById("mode").addEventListener("change", () => {
    const mode = document.getElementById("mode").value;
    const help = document.getElementById("modeHelp");
    if (mode === "AND_OR") {
        help.innerHTML = `AND_OR 모드: 첫 번째 키워드는 반드시 포함, 두 번째 또는 세 번째 키워드 중 하나라도 포함된 결과를 보여줍니다.<br>예) "민법, 계약, 해지"`;
    } else if (mode === "AND") {
        help.textContent = "AND 모드: 모든 키워드가 포함된 결과를 보여줍니다.";
    } else if (mode === "OR") {
        help.textContent = "OR 모드: 키워드 중 하나라도 포함된 결과를 보여줍니다.";
    } else if (mode === "SINGLE") {
        help.textContent = "SINGLE 모드: 첫 번째 키워드가 포함된 결과를 보여줍니다.";
    } else if (mode === "NOT") {
        help.textContent = "NOT 모드: 첫 번째 키워드는 포함되지만 제외어는 포함되지 않은 결과를 보여줍니다.";
    }
});

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

function formatIssueText(text) {
    return text
        .replace(/(\[\d+\])/g, '$1\n')
        .replace(/(\d+\.)/g, '$1\n')
        .replace(/([①-⑳])/g, '$1\n');
}

function renderTable(data) {
    if (!data.length) {
        document.getElementById("result").innerHTML = "<p>검색 결과가 없습니다.</p>";
        return;
    }

    const columnOrder = ["판례정보", "제목", "쟁점", "선정이유"];

    let table = "<table><thead><tr>";
    columnOrder.forEach(col => {
        table += `<th class="${col === '판례정보' ? 'caseinfo' : col === '제목' ? 'title' : col === '쟁점' ? 'issue' : 'reason'}">${col}</th>`;
    });
    table += "</tr></thead><tbody>";

    const caseTypes = ["다", "도", "두", "헌가", "헌나", "헌다", "헌라", "헌마", "헌바"];
    const regex = new RegExp(`(\\d{4}|\\d{2})(${caseTypes.join("|")})\\d+`);

    data.forEach(row => {
        table += "<tr>";
        columnOrder.forEach(col => {
            let val = row[col];
            if (typeof val === "object") {
                val = JSON.stringify(val);
            }
            if (col === "쟁점" && typeof val === "string") {
                val = formatIssueText(val);
            }
            if (typeof val === "string") {
                const match = val.match(regex);
                if (match) {
                    const caseNo = match[0];
                    const link = `https://casenote.kr/대법원/${encodeURIComponent(caseNo)}`;
                    table += `<td class="${col === '판례정보' ? 'caseinfo' : col === '제목' ? 'title' : col === '쟁점' ? 'issue' : 'reason'}"><a href="${link}" target="_blank">${val}</a></td>`;
                    return;
                }
            }
            table += `<td class="${col === '판례정보' ? 'caseinfo' : col === '제목' ? 'title' : col === '쟁점' ? 'issue' : 'reason'}">${val}</td>`;
        });
        table += "</tr>";
    });

    table += "</tbody></table>";
    document.getElementById("result").innerHTML = table;
}