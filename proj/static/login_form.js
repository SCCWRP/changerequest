{
    const root = `/${$SCRIPT_ROOT}`.replace(/\/$/, '');
    const setOptions = (element, values) => {
        element.replaceChildren(new Option('', '', true, true));
        element.options[0].disabled = true;
        values.forEach(value => element.add(new Option(value, value)));
    };
    document.querySelectorAll('form[data-dtype]').forEach(form => {
        const dtype = form.dataset.dtype;
        const fields = Array.from(form.querySelectorAll('[data-index]'));
        const submission = form.querySelector('[name="submissionid"]');
        const message = document.getElementById(`${dtype}-submission-message`);
        async function loadField(position) {
            const params = new URLSearchParams({dtype});
            fields.slice(0, position).forEach(field => params.set(field.name, field.value));
            if (position < fields.length) params.set('field', fields[position].name);
            const response = await fetch(`${root}/${position < fields.length ? 'login_values' : 'submissions'}?${params}`);
            const data = await response.json();
            if (!response.ok) throw new Error(data.user_error_msg || data.message || 'Submission search failed.');
            if (position < fields.length) {
                setOptions(fields[position], data.data);
                if (!data.data.length) message.textContent = 'No completed, non-deleted submissions were found for this datatype and login selection.';
            } else {
                submission.replaceChildren();
                data.submissions.forEach(item => submission.add(new Option(
                    `Submission ${item.submissionid} (Submitted on ${item.submissiondate})`, item.submissionid
                )));
                message.textContent = data.message || '';
            }
        }
        fields.forEach((field, position) => field.addEventListener('change', async () => {
            fields.slice(position + 1).forEach(element => setOptions(element, []));
            submission.replaceChildren();
            message.textContent = '';
            try { await loadField(position + 1); } catch (error) { message.textContent = error.message; }
        }));
        loadField(0).catch(error => { message.textContent = error.message; });
        form.addEventListener('submit', async event => {
            event.preventDefault();
            if (!submission.value || fields.some(field => !field.value)) {
                message.textContent = 'Select all login fields and a submission ID.';
                return;
            }
            const action = event.submitter?.value || 'edit';
            const body = new FormData(form);
            body.set('dtype', dtype);
            const overlay = document.getElementById('overlay');
            overlay.style.display = 'block';
            try {
                const response = await fetch(`${root}/post-session-data`, {method: 'POST', body});
                const data = await response.json();
                if (!response.ok || data.message !== 'Success') throw new Error(data.user_error_msg || 'Submission setup failed.');
                window.location = `${root}/edit-submission?action=${action}`;
            } catch (error) {
                message.textContent = error.message;
            } finally {
                overlay.style.display = 'none';
            }
        });
    });
    document.querySelectorAll('.infotab-header').forEach(item => item.addEventListener('click', () => {
        document.querySelectorAll('.infotab-header').forEach(tab => tab.classList.toggle('active', tab === item));
        document.querySelectorAll('.form-container').forEach(panel => panel.classList.toggle('hidden', panel.dataset.dtype !== item.dataset.dtype));
    }));
}