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

const originalLabels = window.chartLabels ? [...window.chartLabels] : [];
const originalDataReel = window.chartDataReel ? [...window.chartDataReel] : [];
const originalDataPrevu = window.chartDataPrevu ? [...window.chartDataPrevu] : [];
const chartColors = ['#9b1c1c', '#2c3e50', '#b8860b', '#4b5320', '#6e4b3a', '#4a4a4a', '#5f9ea0', '#8b0000', '#d35400', '#388e3c', '#0277bd', '#1565c0'];

let hiddenCategories = JSON.parse(localStorage.getItem('hiddenCategories')) || [];
let initialVisibleIndices = [];
originalLabels.forEach((label, index) => {
    if (!hiddenCategories.includes(label)) initialVisibleIndices.push(index);
});

// ========================================================
// RECALCUL DES KPIS (Cashflow complet)
// ========================================================
function updateKPIs(visibleIndices) {
    let depensesReel = 0;
    let depensesPrevu = 0;
    visibleIndices.forEach(i => {
        depensesReel += (originalDataReel[i] || 0);
        depensesPrevu += (originalDataPrevu[i] || 0);
    });
    
    const revenusReel = (window.chartDataReelRevenus || []).reduce((a, b) => a + b, 0);
    const revenusPrevu = (window.chartDataPrevuRevenus || []).reduce((a, b) => a + b, 0);

    let resteReel = revenusReel - depensesReel;
    let restePrevu = revenusPrevu - depensesPrevu;
    let perf = resteReel - restePrevu;

    const elDepReel = document.getElementById('kpi-depenses-reel');
    const elDepPrevu = document.getElementById('kpi-depenses-prevu');
    if(elDepReel) elDepReel.textContent = `${Math.round(depensesReel * 100) / 100} €`;
    if(elDepPrevu) elDepPrevu.textContent = `Prévu : ${Math.round(depensesPrevu * 100) / 100} €`;

    const elRevReel = document.getElementById('kpi-revenus-reel');
    const elRevPrevu = document.getElementById('kpi-revenus-prevu');
    if(elRevReel) elRevReel.textContent = `${Math.round(revenusReel * 100) / 100} €`;
    if(elRevPrevu) elRevPrevu.textContent = `Prévu : ${Math.round(revenusPrevu * 100) / 100} €`;

    const elResteReel = document.getElementById('kpi-reste-reel');
    const elRestePrevu = document.getElementById('kpi-reste-prevu');
    if(elResteReel) elResteReel.textContent = `${Math.round(resteReel * 100) / 100} €`;
    if(elRestePrevu) elRestePrevu.textContent = `Prévu : ${Math.round(restePrevu * 100) / 100} €`;

    const elBilan = document.getElementById('kpi-bilan');
    const elBilanText = document.getElementById('kpi-bilan-text');
    const cardBilan = document.getElementById('kpi-card-bilan');
    
    if(elBilan) {
        let color, text;
        if(perf > 0) { color = 'var(--success)'; text = 'Super ! Vous avez économisé plus que prévu.'; }
        else if (perf < 0) { color = 'var(--danger)'; text = 'Attention, vous avez moins de reste à vivre que prévu.'; }
        else { color = 'var(--text-muted)'; text = 'Vous êtes exactement sur votre prévisionnel.'; }
        
        elBilan.textContent = `${perf > 0 ? '+' : ''}${Math.round(perf * 100) / 100} €`;
        elBilan.style.color = color;
        if(elBilanText) elBilanText.textContent = text;
        if(cardBilan) cardBilan.style.borderLeft = `5px solid ${color}`;
    }
}

// 1. Initialisation du Bar Chart (Dépenses)
const barCanvas = document.getElementById('barChart');
let barChart = null;
if (barCanvas) {
    barChart = new Chart(barCanvas, {
        type: 'bar',
        data: {
            labels: initialVisibleIndices.map(i => originalLabels[i]),
            datasets: [
                { label: 'Réel', data: initialVisibleIndices.map(i => originalDataReel[i]), backgroundColor: '#9b1c1c', borderRadius: 4 },
                { label: 'Prévu', data: initialVisibleIndices.map(i => originalDataPrevu[i]), backgroundColor: '#d6d3ce', borderRadius: 4 }
            ]
        },
        options: { maintainAspectRatio: false, indexAxis: 'y', plugins: { legend: { display: true, position: 'top', labels: { usePointStyle: true } }, tooltip: { mode: 'index', intersect: false } }, scales: { x: { border: {display: false} }, y: { border: {display: false}, ticks: { autoSkip: false } } } }
    });
}

// 2. Initialisation du Bar Chart (Revenus)
const barRevenusCanvas = document.getElementById('barChartRevenus');
let barChartRevenus = null;
if (barRevenusCanvas && window.chartLabelsRevenus) {
    barChartRevenus = new Chart(barRevenusCanvas, {
        type: 'bar',
        data: {
            labels: window.chartLabelsRevenus,
            datasets: [
                { label: 'Réel', data: window.chartDataReelRevenus, backgroundColor: '#2e7d32', borderRadius: 4 },
                { label: 'Prévu', data: window.chartDataPrevuRevenus, backgroundColor: '#d6d3ce', borderRadius: 4 }
            ]
        },
        options: { maintainAspectRatio: false, indexAxis: 'y', plugins: { legend: { display: true, position: 'top', labels: { usePointStyle: true } }, tooltip: { mode: 'index', intersect: false } }, scales: { x: { border: {display: false} }, y: { border: {display: false}, ticks: { autoSkip: false } } } }
    });
}

// 3. Pie Chart (Master Switch pour les dépenses)
const pieCanvas = document.getElementById('pieChart');
let pieChart = null;
if (pieCanvas) {
    pieChart = new Chart(pieCanvas, {
        type: 'pie',
        data: { 
            labels: [...originalLabels], 
            datasets: [{ data: [...originalDataReel], backgroundColor: chartColors, borderWidth: 2, borderColor: '#fdfcfb' }] 
        },
        options: { 
            maintainAspectRatio: false, 
            plugins: { 
                legend: { 
                    position: 'bottom', 
                    labels: { usePointStyle: true, boxWidth: 10 },
                    onClick: function(e, legendItem, legend) {
                        const chart = legend.chart;
                        const index = legendItem.index;
                        const label = chart.data.labels[index];

                        chart.toggleDataVisibility(index);
                        chart.update();
                        
                        let hiddenCat = JSON.parse(localStorage.getItem('hiddenCategories')) || [];
                        if (chart.getDataVisibility(index)) {
                            hiddenCat = hiddenCat.filter(item => item !== label);
                        } else {
                            if (!hiddenCat.includes(label)) hiddenCat.push(label);
                        }
                        localStorage.setItem('hiddenCategories', JSON.stringify(hiddenCat));
                        
                        let visibleIndices = [];
                        originalLabels.forEach((lbl, i) => {
                            if (chart.getDataVisibility(i)) visibleIndices.push(i);
                        });
                        
                        if (barChart) {
                            barChart.data.labels = visibleIndices.map(i => originalLabels[i]);
                            barChart.data.datasets[0].data = visibleIndices.map(i => originalDataReel[i]);
                            barChart.data.datasets[1].data = visibleIndices.map(i => originalDataPrevu[i]);
                            barChart.update();
                        }
                        
                        updateKPIs(visibleIndices);
                    }
                } 
            } 
        }
    });

    originalLabels.forEach((label, index) => {
        if (hiddenCategories.includes(label)) pieChart.toggleDataVisibility(index);
    });
    pieChart.update();
}

// Synchronisation initiale des KPIs
document.addEventListener('DOMContentLoaded', () => {
    updateKPIs(initialVisibleIndices);
});

// 4. Line Chart (Évolution Annuelle)
const lineCanvas = document.getElementById('lineChart');
if (lineCanvas && window.dataEvolution) {
    new Chart(lineCanvas, {
        type: 'line',
        data: {
            labels: ['Jan', 'Fév', 'Mar', 'Avr', 'Mai', 'Juin', 'Juil', 'Aoû', 'Sep', 'Oct', 'Nov', 'Déc'],
            datasets: [
                 { 
                    label: 'Revenus', 
                    data: window.dataRevenusEvolution || [], 
                    borderColor: '#2e7d32', 
                    backgroundColor: 'rgba(46, 125, 50, 0.05)', 
                    borderWidth: 2, 
                    fill: true, 
                    tension: 0.4 
                },
                { 
                    label: 'Dépenses', 
                    data: window.dataEvolution || [], 
                    borderColor: '#c62828', 
                    backgroundColor: 'rgba(198, 40, 40, 0.05)', 
                    borderWidth: 2, 
                    fill: true, 
                    tension: 0.4 
                }
            ]
        },
        options: { maintainAspectRatio: false, plugins: { legend: { display: true } }, scales: { x: { border: {display: false} }, y: { border: {display: false} } } }
    });
}

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

// SYSTÈME DE TRI DES TABLEAUX
document.querySelectorAll('th.sortable').forEach((th, idx) => {
    th.style.cursor = 'pointer';
    
    const span = document.createElement('span');
    span.innerHTML = ' ↕';
    span.style.opacity = '0.3';
    th.appendChild(span);

    th.addEventListener('click', function() {
        const table = th.closest('table');
        const tbody = table.querySelector('tbody');
        
        let isAsc = this.classList.contains('asc');
        let direction = isAsc ? -1 : 1;
        
        Array.from(th.parentNode.children).forEach(s => {
            s.classList.remove('asc', 'desc');
            if(s.querySelector('span')) {
                s.querySelector('span').innerHTML = ' ↕';
                s.querySelector('span').style.opacity = '0.3';
            }
        });
        
        if (direction === 1) {
            this.classList.add('asc');
            span.innerHTML = ' ↑';
        } else {
            this.classList.add('desc');
            span.innerHTML = ' ↓';
        }
        span.style.opacity = '1';
        
        localStorage.setItem('tableSortIdx', idx);
        localStorage.setItem('tableSortDir', direction === 1 ? 'asc' : 'desc');

        const getVal = (tr, i) => tr.children[i].getAttribute('data-sort') || tr.children[i].innerText.trim();

        const parseDate = (dateStr) => {
            let yearMatch = dateStr.match(/\d{4}/);
            let year = yearMatch ? yearMatch[0] : "0000";
            let month = "00", day = "00";
            const months = { 'janv':'01', 'janvier':'01', 'févr':'02', 'fevr':'02', 'février':'02', 'mars':'03', 'avr':'04', 'avril':'04', 'mai':'05', 'juin':'06', 'juil':'07', 'juillet':'07', 'août':'08', 'aout':'08', 'sept':'09', 'septembre':'09', 'oct':'10', 'octobre':'10', 'nov':'11', 'novembre':'11', 'déc':'12', 'dec':'12', 'décembre':'12' };
            
            let slashMatch = dateStr.match(/(\d{1,2})\/(\d{1,2})/);
            if (slashMatch) {
                day = slashMatch[1].padStart(2, '0');
                month = slashMatch[2].padStart(2, '0');
            } else {
                let textMatch = dateStr.toLowerCase().match(/(\d{1,2})?[\s\-]*(janv|févr|fevr|mars|avr|mai|juin|juil|août|aout|sept|oct|nov|déc|dec|janvier|février|avril|juillet|septembre|octobre|novembre|décembre)/);
                if (textMatch) {
                    if (textMatch[1]) day = textMatch[1].padStart(2, '0');
                    month = months[textMatch[2]] || "00";
                }
            }
            return parseInt(`${year}${month}${day}`, 10);
        };
        
        Array.from(tbody.querySelectorAll('tr'))
            .sort((a, b) => {
                let v1 = getVal(a, idx);
                let v2 = getVal(b, idx);
                let cmp = 0;

                if (idx === 0) {
                    cmp = parseDate(v1) - parseDate(v2);
                } else if (v1 !== '' && v2 !== '' && !isNaN(v1) && !isNaN(v2)) {
                    cmp = parseFloat(v1) - parseFloat(v2);
                } else {
                    cmp = v1.toString().toLowerCase().localeCompare(v2.toString().toLowerCase());
                }
                
                return cmp * direction;
            })
            .forEach(tr => tbody.appendChild(tr));
    });
});

window.addEventListener('DOMContentLoaded', () => {
    const savedSortIdx = localStorage.getItem('tableSortIdx');
    const savedSortDir = localStorage.getItem('tableSortDir');
    
    if (savedSortIdx !== null) {
        const ths = document.querySelectorAll('th.sortable');
        if (ths[savedSortIdx]) {
            if (savedSortDir === 'asc') ths[savedSortIdx].classList.add('desc');
            else ths[savedSortIdx].classList.add('asc');
            ths[savedSortIdx].click();
        }
    }
});

// Flatpickr (Calendrier)
if (document.getElementById("datePicker")) {
    flatpickr("#datePicker", { locale: "fr", dateFormat: "Y-m-d", allowInput: true });
}