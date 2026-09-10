import { addTips } from './tooltip.js';

export const root = `/${$SCRIPT_ROOT}`.replace(/\/$/, '');
export const context = JSON.parse(document.getElementById('submission-context').textContent);
export let report = null;
let selectedTable = null;
let dirty = false;
let busy = false;
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
    const state = document.getElementById('workflow-status');
    state.textContent = 'Changes not saved';
    state.className = 'workflow-status needs-review';
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
    document.getElementById('changed-count').textContent = data.errors.length ? data.edit_rows.length : data.counts.modified;
    document.getElementById('added-count').textContent = data.counts.added;
    document.getElementById('deleted-count').textContent = data.counts.deleted;
    document.getElementById('report-warnings').textContent = [
        ...data.errors.map(error => error.error_message), ...data.warnings.map(warning => warning.error_message)
    ].join('\n');
    formatDataTable(report, selectedTable);
    tableNavigation();
    addTips();
    ['changed', 'added', 'deleted'].forEach(kind => {
        const container = document.getElementById(`${kind}-records-display-inner-container`);
        if (!container.querySelector('tbody tr') && !container.querySelector('.table-empty')) {
            const empty = document.createElement('p');
            empty.className = 'table-empty';
            empty.textContent = `No ${kind} records in this table.`;
            container.append(empty);
        }
    });
    document.querySelectorAll('#changed-records-display-inner-container [contenteditable]').forEach(cell => {
        cell.addEventListener('input', () => {
            invalidateReport();
            status.textContent = 'Unsaved browser corrections.';
        });
    });
    if (report.request_type === 'delete' || (!data.errors.length && !data.counts.modified && data.counts.deleted)) {
        document.getElementById('deleted-tab').onclick();
    } else if (!data.errors.length && !data.counts.modified && data.counts.added) {
        document.getElementById('added-tab').onclick();
    }
}

export function renderReport(data) {
    report = data;
    dirty = false;
    selector.replaceChildren();
    Object.entries(data.tables).forEach(([table, details]) => {
        const count = Object.values(details.counts).reduce((total, value) => total + value, 0);
        selector.add(new Option(`${table} (${details.errors.length ? 'needs correction' : count + ' changes'})`, table));
    });
    selectedTable = data.tables[selectedTable] ? selectedTable : selector.options[0].value;
    selector.value = selectedTable;
    status.textContent = [data.message, ...(data.warnings || [])].filter(Boolean).join('\n');
    status.classList.remove('is-error');
    document.getElementById('review-placeholder').classList.add('hidden');
    document.getElementById('review-legend').classList.remove('hidden');
    document.getElementById('review-actions').classList.remove('hidden');
    document.getElementById('change-report-container').classList.remove('hidden');
    document.querySelectorAll('.clean-data-post-change-option').forEach(button => button.classList.toggle('hidden', !data.ready));
    document.getElementById('save-change-btn').classList.toggle('hidden', data.request_type === 'delete');
    document.getElementById('finalize-label').textContent = data.request_type === 'delete' ? 'Submit deletion request' : 'Submit change request';
    document.getElementById('finalize-submission').classList.toggle('btn-danger', data.request_type === 'delete');
    const state = document.getElementById('workflow-status');
    const hasErrors = Object.values(data.tables).some(table => table.errors.length);
    state.textContent = hasErrors ? 'Needs correction' : data.ready ? 'Ready for review' : 'No changes';
    state.className = `workflow-status ${hasErrors ? 'needs-review' : data.ready ? 'ready' : ''}`;
    document.getElementById('final-revision').value = data.revision;
    showTable();
}

selector.addEventListener('change', () => {
    captureTable();
    selectedTable = selector.value;
    showTable();
});

export async function sendComparison(url, options) {
    if (busy) return;
    busy = true;
    const loader = document.getElementById('loading-modal');
    loader.style.display = 'block';
    invalidateReport();
    document.querySelectorAll('.editor-workspace button, .editor-workspace input, #report-table-selector').forEach(control => { control.disabled = true; });
    document.getElementById('workflow-status').textContent = 'Processing';
    try {
        const response = await fetch(url, options);
        const data = await response.json();
        if (!response.ok) throw new Error(data.message || 'The request failed.');
        renderReport(data);
        document.getElementById('change-report-container').scrollIntoView({behavior: 'smooth', block: 'start'});
    } catch (error) {
        status.textContent = error.message;
        status.classList.add('is-error');
        document.getElementById('workflow-status').textContent = 'Comparison incomplete';
    } finally {
        loader.style.display = 'none';
        busy = false;
        document.querySelectorAll('.editor-workspace button, .editor-workspace input, #report-table-selector').forEach(control => { control.disabled = false; });
    }
}

const uploadForm = document.getElementById('upload-form');
const fileInput = document.getElementById('file');
function updateFilename() {
    document.getElementById('selected-filename').textContent = fileInput.files[0]?.name || 'No workbook selected';
}
fileInput.addEventListener('change', updateFilename);
uploadForm.addEventListener('submit', event => {
    event.preventDefault();
    updateFilename();
    if (fileInput.files.length !== 1 || !fileInput.files[0].name.toLowerCase().endsWith('.xlsx')) {
        status.textContent = 'Choose one .xlsx workbook.';
        status.classList.add('is-error');
        return;
    }
    sendComparison(`${root}/compare`, {method: 'POST', body: new FormData(uploadForm)});
});

const deletionButton = document.getElementById('request-deletion');
const deletionDialog = document.getElementById('deletion-dialog');
deletionButton?.addEventListener('click', () => {
    if (!busy) {
        deletionDialog.returnValue = '';
        deletionDialog.showModal();
    }
});
deletionDialog.addEventListener('close', () => {
    if (deletionDialog.returnValue === 'prepare') {
        sendComparison(`${root}/request-deletion`, {method: 'POST'});
    }
});

['dragenter', 'dragover', 'dragleave', 'drop'].forEach(name => document.addEventListener(name, event => {
    event.preventDefault();
    event.stopPropagation();
    document.body.classList.toggle('file-dragging', ['dragenter', 'dragover'].includes(name));
}));
document.addEventListener('drop', event => {
    if (busy || document.querySelector('dialog[open]')) return;
    document.getElementById('file').files = event.dataTransfer.files;
    uploadForm.dispatchEvent(new Event('submit', {cancelable: true}));
});
window.onbeforeunload = () => dirty || report ? true : undefined;