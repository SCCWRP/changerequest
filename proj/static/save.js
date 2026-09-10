import { browserEdits, context, report, root, sendComparison } from './edit_submission.js';

export async function saveChanges() {
    if (!report || report.request_type === 'delete') return;
    await sendComparison(`${root}/compare`, {
        method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(browserEdits())
    });
}

document.getElementById('save-change-btn').addEventListener('click', saveChanges);
document.getElementById('final-submit-form').addEventListener('submit', async function(event) {
    event.preventDefault();
    if (!report?.ready || document.getElementById('finalize-submission').classList.contains('hidden')) return;
    const deleting = report.request_type === 'delete';
    let confirmation = '';
    if (deleting) {
        confirmation = prompt(`Deletion is irreversible once SCCWRP staff run the SQL. Type submission ID ${context.submissionid} to confirm:`);
        if (confirmation?.trim() !== String(context.submissionid)) {
            alert('The submission ID did not match. No deletion request was finalized.');
            return;
        }
    } else if (!confirm('Finalize this submission edit request for SCCWRP review?')) {
        return;
    }
    const comment = prompt(`Please explain why you are requesting ${deleting ? 'deletion of this submission' : 'these changes'}:`);
    if (!comment?.trim()) {
        alert('A non-empty comment is required.');
        return;
    }
    document.getElementById('final-comment').value = comment.trim();
    document.getElementById('final-confirmation').value = confirmation || '';
    const loader = document.getElementById('loading-modal');
    loader.style.display = 'block';
    try {
        const response = await fetch(this.action, {method: 'POST', body: new FormData(this)});
        if (!response.ok) {
            const data = await response.json();
            throw new Error(data.message || 'Finalization failed.');
        }
        const page = await response.text();
        window.onbeforeunload = undefined;
        document.open();
        document.write(page);
        document.close();
    } catch (error) {
        alert(error.message);
    } finally {
        loader.style.display = 'none';
    }
});