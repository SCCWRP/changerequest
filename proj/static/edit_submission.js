import { addTips } from './tooltip.js';

export const root = `/${$SCRIPT_ROOT}`.replace(/\/$/, '');
export const context = JSON.parse(document.getElementById('submission-context').textContent);
export let report = null;
let selectedTable = null;
let dirty = false;
const selector = document.getElementById('report-table-selector');
const status = document.getElementById('request-status');

function captureTable() {
    if (report && selectedTable) {
        report.tables[selectedTable].tbl = document.getElementById('changed-records-display-inner-container').innerHTML;
    }
}

export function invalidateReport() {
    dirty = true;
    document.querySelectorAll('.clean-data-post-change-option').forEach(button => button.classList.add('hidden'));
}

export function browserEdits() {
    captureTable();
    const tables = {};
    Object.entries(report.tables).forEach(([table, data]) => {
        const container = document.createElement('div');
        container.innerHTML = data.tbl;
        tables[table] = Array.from(container.querySelectorAll('tbody tr')).map((row, position) => {
            const values = {};
            row.querySelectorAll('td').forEach(cell => {
                const columnClass = Array.from(cell.classList).find(name => name.startsWith('colname-'));
                values[columnClass.slice('colname-'.length)] = cell.textContent;
            });
            return {row: data.edit_rows[position], values};
        });
    });
    return {tables, revision: report.revision};
}

function showTable() {
    const data = report.tables[selectedTable];
    document.getElementById('changed-records-display-inner-container').innerHTML = data.tbl;
    document.getElementById('added-records-display-inner-container').innerHTML = data.addtbl;
    document.getElementById('deleted-records-display-inner-container').innerHTML = data.deltbl;
    document.getElementById('report-primary-key').textContent = `Primary key: ${context.pkeys[selectedTable].join(', ')}`;
    document.getElementById('report-counts').textContent = `${data.counts.modified} changed, ${data.counts.added} added, ${data.counts.deleted} deleted`;
    document.getElementById('report-warnings').textContent = [
        ...data.errors.map(error => error.error_message), ...data.warnings.map(warning => warning.error_message)
    ].join('\n');
    formatDataTable(report, selectedTable);
    tableNavigation();
    addTips();
    document.querySelectorAll('#changed-records-display-inner-container [contenteditable]').forEach(cell => {
        cell.addEventListener('input', () => {
            invalidateReport();
            status.textContent = 'Unsaved browser corrections.';
        });
    });
    if (report.request_type === 'delete') document.querySelector('[data-target="deleted-records-datatable-container"]').click();
}

export function renderReport(data) {
    report = data;
    dirty = false;
    selector.replaceChildren();
    Object.keys(data.tables).forEach(table => selector.add(new Option(table, table)));
    selectedTable = data.tables[selectedTable] ? selectedTable : selector.options[0].value;
    selector.value = selectedTable;
    status.textContent = [data.message, ...(data.warnings || [])].filter(Boolean).join('\n');
    document.getElementById('change-report-container').classList.remove('hidden');
    document.querySelectorAll('.clean-data-post-change-option').forEach(button => button.classList.toggle('hidden', !data.ready));
    document.getElementById('save-change-btn').classList.toggle('hidden', data.request_type === 'delete');
    document.getElementById('finalize-submission').value = data.request_type === 'delete' ? 'Finalize Deletion Request' : 'Finalize Change Request';
    document.getElementById('final-revision').value = data.revision;
    showTable();
}

selector.addEventListener('change', () => {
    captureTable();
    selectedTable = selector.value;
    showTable();
});

export async function sendComparison(url, options) {
    const loader = document.getElementById('loading-modal');
    loader.style.display = 'block';
    invalidateReport();
    try {
        const response = await fetch(url, options);
        const data = await response.json();
        if (!response.ok) throw new Error(data.message || 'The request failed.');
        renderReport(data);
        document.getElementById('change-report-container').scrollIntoView({behavior: 'smooth', block: 'start'});
    } catch (error) {
        status.textContent = error.message;
        alert(error.message);
    } finally {
        loader.style.display = 'none';
    }
}

const uploadForm = document.getElementById('upload-form');
uploadForm.addEventListener('submit', event => {
    event.preventDefault();
    sendComparison(`${root}/compare`, {method: 'POST', body: new FormData(uploadForm)});
});

document.getElementById('dismiss-omitted-sheets-notice').addEventListener('click', () => {
    document.getElementById('omitted-sheets-notice').remove();
});

const deletionButton = document.getElementById('request-deletion');
deletionButton?.addEventListener('click', () => {
    if (confirm(`Prepare a deletion request for ALL records in submission ${context.submissionid}? This replaces the current comparison.`)) {
        sendComparison(`${root}/request-deletion`, {method: 'POST'});
    }
});

['dragenter', 'dragover', 'dragleave', 'drop'].forEach(name => document.addEventListener(name, event => {
    event.preventDefault();
    event.stopPropagation();
    document.body.style.backgroundColor = ['dragenter', 'dragover'].includes(name) ? '#cccccc' : '';
}));
document.addEventListener('drop', event => {
    document.getElementById('file').files = event.dataTransfer.files;
    uploadForm.dispatchEvent(new Event('submit', {cancelable: true}));
});
window.onbeforeunload = () => dirty || report ? true : undefined;
if (deletionButton?.dataset.initial === 'true') {
    deletionButton.click();
}