{
    const signUpForm = document.getElementById('sign-up-form');
    const signInForm = document.getElementById('sign-in-form');

    const authFormSubmit = async function(event, form) {
        console.log("FORM SUBMITTED")
        console.log("form.dataset.route")
        console.log(form.dataset.route)
        event.preventDefault();
        const formData = new FormData(form);

        let response = await fetch(
            form.dataset.route, 
            {
                method : 'post',
                body   : formData
            }
        );
        let result = await response.json();
        console.log(result);

    }

    signInForm?.addEventListener('submit', function(e){
        authFormSubmit(e, this);
    })
    signUpForm?.addEventListener('submit', function(e){
        authFormSubmit(e, this);
    })
}