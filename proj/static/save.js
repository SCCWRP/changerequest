import { browserEdits, context, report, root, sendComparison } from './edit_submission.js';

export async function saveChanges() {
    if (!report || report.request_type === 'delete') return;
    await sendComparison(`${root}/compare`, {
        method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(browserEdits())
    });
}

const dialog = document.getElementById('finalize-dialog');
const detailsForm = document.getElementById('finalize-details-form');
const finalForm = document.getElementById('final-submit-form');
const commentInput = document.getElementById('request-comment');
const confirmationInput = document.getElementById('deletion-confirmation');
const errorMessage = document.getElementById('finalize-error');
let sending = false;

document.getElementById('save-change-btn').addEventListener('click', saveChanges);
document.querySelectorAll('[data-close-finalize]').forEach(button => button.addEventListener('click', () => {
    if (!sending) dialog.close();
}));
dialog.addEventListener('cancel', event => {
    if (sending) event.preventDefault();
});
commentInput.addEventListener('input', () => commentInput.setCustomValidity(''));
confirmationInput.addEventListener('input', () => confirmationInput.setCustomValidity(''));

finalForm.addEventListener('submit', event => {
    event.preventDefault();
    if (!report?.ready || document.getElementById('finalize-submission').classList.contains('hidden')) return;
    const deleting = report.request_type === 'delete';
    document.getElementById('finalize-title').textContent = deleting ? 'Submit deletion request' : 'Submit change request';
    document.getElementById('finalize-description').textContent = deleting
        ? 'Deletion is irreversible once SCCWRP staff run the SQL. All records in this submission will be removed.'
        : 'SCCWRP staff will review this request before applying changes.';
    document.getElementById('deletion-confirmation-field').classList.toggle('hidden', !deleting);
    document.getElementById('send-request-button').classList.toggle('btn-danger', deleting);
    confirmationInput.required = deleting;
    confirmationInput.value = '';
    confirmationInput.setCustomValidity('');
    commentInput.setCustomValidity('');
    errorMessage.textContent = '';
    dialog.showModal();
    commentInput.focus();
});

detailsForm.addEventListener('submit', async event => {
    event.preventDefault();
    if (sending || !report?.ready) return;
    if (!commentInput.value.trim()) {
        commentInput.setCustomValidity('Enter a reason for this request.');
        commentInput.reportValidity();
        return;
    }
    if (report.request_type === 'delete' && confirmationInput.value.trim() !== String(context.submissionid)) {
        confirmationInput.setCustomValidity('The submission ID does not match.');
        confirmationInput.reportValidity();
        return;
    }
    document.getElementById('final-comment').value = commentInput.value.trim();
    document.getElementById('final-confirmation').value = confirmationInput.value.trim();
    const sendButton = document.getElementById('send-request-button');
    const label = sendButton.innerHTML;
    sending = true;
    dialog.setAttribute('aria-busy', 'true');
    detailsForm.querySelectorAll('button, input, textarea').forEach(control => { control.disabled = true; });
    sendButton.textContent = 'Sending request...';
    errorMessage.textContent = '';
    try {
        const response = await fetch(finalForm.action, {method: 'POST', body: new FormData(finalForm)});
        if (!response.ok) {
            const data = await response.json();
            throw new Error(data.message || 'Finalization failed. Please try again.');
        }
        const page = await response.text();
        window.onbeforeunload = undefined;
        document.open();
        document.write(page);
        document.close();
    } catch (error) {
        errorMessage.textContent = error.message;
    } finally {
        sending = false;
        dialog.removeAttribute('aria-busy');
        detailsForm.querySelectorAll('button, input, textarea').forEach(control => { control.disabled = false; });
        sendButton.innerHTML = label;
    }
});