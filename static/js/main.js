// Persistance Onglets
document.addEventListener('DOMContentLoaded', () => {
    let active = localStorage.getItem('activeTab');
    if(active) bootstrap.Tab.getOrCreateInstance(document.querySelector(`button[data-bs-target="${active}"]`)).show();
});
document.querySelectorAll('button[data-bs-toggle="pill"]').forEach(t => t.addEventListener('shown.bs.tab', e => localStorage.setItem('activeTab', e.target.dataset.bsTarget)));

// Configurations Chart.js
Chart.defaults.font.family = 'system-ui, -apple-system, sans-serif';
Chart.defaults.color = '#78716c';
Chart.defaults.scale.grid.color = '#e7e5df';

// On récupère les variables injectées par Flask dans l'objet global window
const labels = window.chartLabels;
const dataReel = window.chartDataReel;
const dataPrevu = window.chartDataPrevu;
const chartColors = ['#9b1c1c', '#2c3e50', '#b8860b', '#4b5320', '#6e4b3a', '#4a4a4a', '#5f9ea0', '#8b0000'];

// 1. Pie Chart
new Chart(document.getElementById('pieChart'), {
    type: 'pie',
    data: { labels: labels, datasets: [{ data: dataReel, backgroundColor: chartColors, borderWidth: 2, borderColor: '#fdfcfb' }] },
    options: { maintainAspectRatio: false, plugins: { legend: { position: 'bottom', labels: { usePointStyle: true, boxWidth: 10 } } } }
});

// 2. Bar Chart
new Chart(document.getElementById('barChart'), {
    type: 'bar',
    data: {
        labels: labels,
        datasets: [
            { label: 'Réel', data: dataReel, backgroundColor: '#9b1c1c', borderRadius: 4 },
            { label: 'Prévu', data: dataPrevu, backgroundColor: '#d6d3ce', borderRadius: 4 }
        ]
    },
    options: { maintainAspectRatio: false, indexAxis: 'y', plugins: { legend: { display: true, position: 'top', labels: { usePointStyle: true } }, tooltip: { mode: 'index', intersect: false } }, scales: { x: { border: {display: false} }, y: { border: {display: false}, ticks: { autoSkip: false } } } }
});

// 3. Line Chart
new Chart(document.getElementById('lineChart'), {
    type: 'line',
    data: {
        labels: ['Jan', 'Fév', 'Mar', 'Avr', 'Mai', 'Juin', 'Juil', 'Aoû', 'Sep', 'Oct', 'Nov', 'Déc'],
        datasets: [{ label: 'Dépenses mensuelles', data: [1200, 1100, 1400, 900, 1000, 1100, 1500, 1300, 1200, 1100, 1250, 1600], borderColor: '#2c3e50', backgroundColor: 'rgba(44, 62, 80, 0.05)', borderWidth: 2, fill: true, tension: 0.4, pointBackgroundColor: '#fdfcfb', pointBorderColor: '#2c3e50', pointBorderWidth: 2, pointRadius: 4 }]
    },
    options: { maintainAspectRatio: false, plugins: { legend: { display: false } }, scales: { x: { border: {display: false} }, y: { border: {display: false} } } }
});

// 4. Radar Chart
new Chart(document.getElementById('radarChart'), {
    type: 'radar',
    data: {
        labels: labels,
        datasets: [
            { label: 'Réel', data: dataReel, backgroundColor: 'rgba(155, 28, 28, 0.2)', borderColor: '#9b1c1c', pointBackgroundColor: '#9b1c1c' },
            { label: 'Prévu', data: dataPrevu, backgroundColor: 'rgba(214, 211, 206, 0.4)', borderColor: '#d6d3ce', pointBackgroundColor: '#d6d3ce' }
        ]
    },
    options: { maintainAspectRatio: false, plugins: { legend: { position: 'bottom', labels: { usePointStyle: true } } }, scales: { r: { angleLines: { color: '#e7e5df' }, grid: { color: '#e7e5df' }, pointLabels: { color: '#292524', font: { size: 10 } }, ticks: { display: false } } } }
});

// DRAG & DROP
function dragStart(e) { e.dataTransfer.setData("id", e.target.dataset.id); e.target.style.opacity = '0.5'; }
document.addEventListener('dragend', (e) => { if(e.target.classList.contains('transaction-card')) e.target.style.opacity = '1'; });
function allowDrop(e) { e.preventDefault(); e.currentTarget.classList.add('dragover'); }
function dragLeave(e) { e.currentTarget.classList.remove('dragover'); }
function drop(e) {
    e.preventDefault();
    const dropzone = e.currentTarget;
    dropzone.classList.remove('dragover');
    dropzone.innerHTML = `<div class="spinner-border spinner-border-sm text-primary" role="status"></div>`;
    
    fetch('/update_category', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({transaction_id: e.dataTransfer.getData("id"), new_category: dropzone.dataset.category})
    }).then(() => location.reload());
}