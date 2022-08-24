{
    Array.from(document.querySelectorAll('button.close')).forEach(b => {
        b.addEventListener('click', function(e){
            e.preventDefault();
            this.parentElement.remove();
        })
    })
}