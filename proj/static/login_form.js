{
    const root = `/${$SCRIPT_ROOT}`.replace(/\/$/, '');
    const setOptions = (element, values, placeholder = 'Select an option') => {
        element.replaceChildren(new Option(placeholder, '', true, true));
        element.options[0].disabled = true;
        values.forEach(value => element.add(new Option(value, value)));
        element.disabled = values.length === 0;
    };
    document.querySelectorAll('form[data-dtype]').forEach(form => {
        const dtype = form.dataset.dtype;
        const fields = Array.from(form.querySelectorAll('[data-index]'));
        const submission = form.querySelector('[name="submissionid"]');
        const submissionPrompt = submission.options[0].text;
        const message = document.getElementById(`${dtype}-submission-message`);
        const submitButton = form.querySelector('[type="submit"]');
        let selectionVersion = 0;
        async function loadField(position) {
            const version = selectionVersion;
            const params = new URLSearchParams({dtype});
            fields.slice(0, position).forEach(field => params.set(field.name, field.value));
            if (position < fields.length) params.set('field', fields[position].name);
            const response = await fetch(`${root}/${position < fields.length ? 'login_values' : 'submissions'}?${params}`);
            const data = await response.json();
            if (version !== selectionVersion) return;
            if (!response.ok) throw new Error(data.user_error_msg || data.message || 'Submission search failed.');
            if (position < fields.length) {
                setOptions(fields[position], data.data, `Select ${fields[position].name}`);
                if (!data.data.length) message.textContent = 'No completed, non-deleted submissions were found for this datatype and login selection.';
            } else {
                submission.replaceChildren();
                if (!data.submissions.length) submission.add(new Option('No matching submissions', ''));
                data.submissions.forEach(item => submission.add(new Option(
                    `Submission ${item.submissionid} (Submitted on ${item.submissiondate})`, item.submissionid
                )));
                message.textContent = data.message || '';
                submission.disabled = data.submissions.length === 0;
                submitButton.disabled = data.submissions.length === 0;
            }
        }
        fields.forEach((field, position) => field.addEventListener('change', async () => {
            selectionVersion++;
            fields.slice(position + 1).forEach(element => setOptions(element, [], 'Select previous field first'));
            setOptions(submission, [], submissionPrompt);
            submitButton.disabled = true;
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
            const body = new FormData(form);
            body.set('dtype', dtype);
            const overlay = document.getElementById('overlay');
            overlay.style.display = 'block';
            submitButton.disabled = true;
            try {
                const response = await fetch(`${root}/post-session-data`, {method: 'POST', body});
                const data = await response.json();
                if (!response.ok || data.message !== 'Success') throw new Error(data.user_error_msg || 'Submission setup failed.');
                window.location = `${root}/edit-submission`;
            } catch (error) {
                message.textContent = error.message;
            } finally {
                overlay.style.display = 'none';
                submitButton.disabled = !submission.value;
            }
        });
    });
    document.querySelectorAll('.infotab-header').forEach(item => item.addEventListener('click', () => {
        document.querySelectorAll('.infotab-header').forEach(tab => {
            tab.classList.toggle('active', tab === item);
            tab.setAttribute('aria-pressed', String(tab === item));
        });
        document.querySelectorAll('.form-container').forEach(panel => panel.classList.toggle('hidden', panel.dataset.dtype !== item.dataset.dtype));
    }));
}