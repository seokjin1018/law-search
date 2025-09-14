document.addEventListener("DOMContentLoaded", () => {
    fetch("/laws")
        .then(res => res.json())
        .then(laws => {
            const select = document.getElementById("lawSelect");

            // "전체" 옵션 추가
            const allOption = document.createElement("option");
            allOption.value = "전체";
            allOption.textContent = "전체";
            select.appendChild(allOption);

            // 법령 옵션 추가
            laws.forEach(law => {
                const opt = document.createElement("option");
                opt.value = law;
                opt.textContent = law;
                select.appendChild(opt);
            });

            // ✅ 전체 선택 자동화
            select.addEventListener("change", () => {
                const selected = Array.from(select.selectedOptions).map(o => o.value);
                if (selected.includes("전체")) {
                    // 전체 선택 시 모든 옵션 선택
                    for (let i = 0; i < select.options.length; i++) {
                        select.options[i].selected = true;
                    }
                }
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

    const lawSelect = document.getElementById("lawSelect");
    const selectedLaws = Array.from(lawSelect.selectedOptions).map(opt => opt.value);

    console.log("선택된 법령:", selectedLaws);

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
        table += `<th class="${col === '판례 정보' ? 'caseinfo' 
                        : col === '제목' ? 'title' 
                        : col === '쟁점' ? 'issue'