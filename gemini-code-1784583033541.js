// إضافة متغير لتحديد نوع الصرفية المطلوبة
let currentModeIsSegel = false;

function loadSalaryData() {
    const selectedMonth = document.querySelector('#monthSelect').value;
    const selectedYear = document.querySelector('#yearSelect').value;

    fetch('/get_salary', {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body: `month=${selectedMonth}&year=${selectedYear}&segel_agoor=${currentModeIsSegel}`
    })
    .then(response => response.json())
    .then(data => {
        // كود تحديث الجداول والجداول والإجماليات هنا (نفس الكود السابق)
        // ...
    });
}

// عند الضغط على زرار شريط المرتب
document.querySelector('#salarySlipBtn').addEventListener('click', function() {
    currentModeIsSegel = false;
    loadSalaryData();
});

// عند الضغط على زرار سجل الأجور الجديد
document.querySelector('#segelAgoorBtn').addEventListener('click', function() {
    currentModeIsSegel = true;
    loadSalaryData();
});