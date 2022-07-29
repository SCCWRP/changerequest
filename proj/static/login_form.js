/* Javascript code for the change request tool login form */
{

    Array.from(document.querySelectorAll('select.login-field-element[data-index="1"]')).forEach(async function(elem) {
        let resp = await fetch(`/${$SCRIPT_ROOT}/login_values?field=${elem.getAttribute('name')}&dtype=${elem.dataset.dtype}`);
        let data = await resp.json();
        elem.innerHTML = `<option value="none" selected disabled hidden></option>`;;
        data.data.forEach(d => {
            elem.innerHTML += `
                <option value="${d}">${d}</option>
            `
        })
    })
    

    Array.from(document.querySelectorAll('.login-field-element[data-index][data-dtype]')).forEach(async function(elem, _, arr) {

        elem.addEventListener('change', async function(e){
            console.log(e)

            const ind = Number(this.dataset.index);
            const nextIndex = ind + 1;
            const dtype = this.dataset.dtype;
            const nextElement = document.querySelector(`.${dtype}-login-field-element[data-index="${nextIndex}"][data-dtype="${dtype}"]`);
            console.log(`.${dtype}-login-field-element[data-index="${nextIndex}"][data-dtype="${dtype}"]`)
            console.log("nextIndex")
            console.log(nextIndex)
            console.log("nextElement")
            console.log(nextElement)
            if (nextElement === null) {
                let qryStringArgs = arr.filter(item => ((item.dataset.dtype === dtype))).map(
                    el => `${el.getAttribute('name')}=${el.value}`
                ).join('&');
                
                let url = `/${$SCRIPT_ROOT}/submissions?${qryStringArgs}&dtype=${dtype}`;

                let resp = await fetch(url);
                let data = await resp.json();
                const submissions = data.submissions;
                console.log(submissions);

                const submissionIdSelect = document.getElementById(`${dtype}-submissionid-select`);

                submissionIdSelect.innerHTML = '';
                submissions.forEach(s => {
                    submissionIdSelect.innerHTML += `<option value="${s.submissionid}"> SubmissionID: ${s.submissionid} (Submitted on ${s.submissiondate})</option>`
                })

                return;
            }
            const field = nextElement.getAttribute("name");
    
            console.log(`.${dtype}-login-field-element[data-index="${nextIndex}"][data-dtype="${dtype}"]`)
            console.log(nextElement)
    
            // clear HTML of next items
            arr.filter(item => (Number(item.dataset.index) > ind) & (item.dataset.dtype === dtype)).forEach(
                el => el.innerHTML = `<option value="none" selected disabled hidden></option>`
            );
            
    
            let url = [
                `/${$SCRIPT_ROOT}/login_values?field=${field}`,
                `dtype=${dtype}`,
                arr.filter(item => (Number(item.dataset.index) < (nextIndex)) & (item.dataset.dtype === dtype))
                    .map(el => `${el.getAttribute('name')}=${el.value}`)
                    .join('&')
            ];
    
            url = url.join('&');
            console.log('url');
            console.log(url);
    
            
            let resp = await fetch(url);
            let data = await resp.json();
            
            if (data.data.length === 0) {
                alert("Nothing found")
            }

            // if nextElement is a select dropdown item ...
            if (nextElement.tagName === 'SELECT') {    
                nextElement.innerHTML = `<option value="none" selected disabled hidden></option>`;
                data.data.forEach(d => {
                    nextElement.innerHTML += `
                        <option value="${d}">${d}</option>
                    `
                });
            } 
        })
    })

    Array.from(document.querySelectorAll('form[data-dtype]')).forEach(f => {
        f.addEventListener('submit',  async function(e) {
            e.preventDefault();
            const dtype = f.dataset.dtype;
            const session_email = document.querySelector(`input[name="session_email"][data-dtype="${dtype}"]`).value;
            formData = new FormData();
            Array.from(document.querySelectorAll(`.${dtype}-login-field-element`)).forEach(s => {
                formData.append(s.getAttribute('name'), s.value);
            })
            formData.append('dtype',dtype)
            formData.append('session_email',session_email)
            
            document.getElementById('overlay').style.display = 'block';
            let result = await fetch(
                `/${$SCRIPT_ROOT}/post-session-data`,
                {
                    method: 'post',
                    body: formData
                }
            );
            let data = await result.json();
            console.log(data);

            if (data.message === 'success') {
                window.location = `/${$SCRIPT_ROOT}/edit-submission`;
            } else {
                document.getElementById('overlay-text-container').innerText = 'An unexpected error occurred';
                console.error('something bad happened');
            }

            
        })
    })

   

    Array.from(document.querySelectorAll('.btn-submission-preview')).forEach(btn => {
        btn.addEventListener('click', async function(e) {
            e.preventDefault();
            const a = document.createElement('a')

            submissionid = document.getElementById(`${this.dataset.dtype}-submissionid-select`).value;
            tablename = document.getElementById(`${this.dataset.dtype}-tablename-select`).value;
            
            if (!submissionid) {
                alert("No submissionid selected");
                return;
            }
            if (!tablename) {
                alert("No tablename selected");
                return;
            }

            a.href = `/changerequest/submission-download?submissionid=${submissionid}&tablename=${tablename}`;
            a.download = `${tablename}_${submissionid}.xlsx`
            document.body.appendChild(a)
            a.click()
            document.body.removeChild(a)

        })
    })

    Array.from(document.getElementsByClassName('infotab-header')).forEach((item, i, arr) => {
        item.addEventListener('click', function(e) {
            arr.forEach(x => x.classList.remove('active'));
            item.classList.add('active');
            Array.from(document.querySelectorAll('.form-container')).forEach(div => {
                div.dataset.dtype === item.dataset.dtype ? div.classList.remove('hidden') : div.classList.add('hidden') ;
            })
        })
    })
}
