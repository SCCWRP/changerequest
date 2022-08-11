(function(){
    
    uploadForm = document.querySelector("#upload-form");
    
    
    /* The routine that gets executed when the file is submitted */
    uploadForm.addEventListener("submit", async function(event){
        event.preventDefault();
        event.stopPropagation();
        document.querySelector(".records-display-inner-container").innerHTML = `<img src="/${$SCRIPT_ROOT}/static/loading.gif">`;
        //const dropped_files = event.originalEvent.dataTransfer.files;
        const dropped_files = document.querySelector('[type=file]').files;
        const formData = new FormData();
        for(let i = 0; i < dropped_files.length; ++i){
            /* submit as array to as file array - otherwise will fail */
            formData.append('files[]', dropped_files[i]);
        }
        let result = await fetch(
            `/${$SCRIPT_ROOT}/compare`,
            {
                method: 'post',
                body: formData
            }
        );
        let data = await result.json();
        console.log(data);
        console.log(data.addtbl);
        console.log(data.deltbl);

        
        /* unhide the datatable containers, only if there are changed records
            We will always unhide the changed_records container though */
        Array.prototype.slice.call(document.querySelectorAll(".datatable-container")).map(
            c => {
                if ( c.classList.contains("addedrecords") & (data.addtbl !== '') ) {
                    c.classList.remove("hidden")
                }
                if ( c.classList.contains("deletedrecords") & (data.deltbl !== '') ) {
                    c.classList.remove("hidden")
                }
                if ( c.classList.contains("changedrecords") ) {
                    c.classList.remove("hidden")
                }
            }
        )
        
        document.querySelector(".records-display-inner-container").innerHTML = data.tbl;
        document.querySelector(".added-records-display-inner-container").innerHTML = data.addtbl;
        document.querySelector(".deleted-records-display-inner-container").innerHTML = data.deltbl;

        // call function that formats the table
        formatDataTable(data);

        // show buttons
        Array.prototype.slice.call(document.querySelectorAll(".post-change-option")).map(
            b => b.classList.remove("hidden")
        )

        /* tooltip. Yes, it was directly copy pasted from stackoverflow */
        // https://stackoverflow.com/questions/33000298/creating-a-clickable-tooltip-in-javascript-or-bootstrap
        $('[data-toggle="popover"]').popover({ trigger: "manual" , html: true, animation:false})
            .on("mouseenter", function () {
                var _this = this;
                $(this).popover("show");
                $(".popover").on("mouseleave", function () {
                        $(_this).popover('hide');
                });
            }).on("mouseleave", function () {
                var _this = this;
                setTimeout(function () {
                        if (!$(".popover:hover").length) {
                                $(_this).popover("hide");
                        }
                }, 300);
            });
        return data;
    })

    // the edit submission page should warn them they might have unsaved changes
    window.onbeforeunload = () => {return true}

})()

// /* Saving changes when they edit in the browser */
// (function(){
    
// })()


// /* hit enter and go to next cell - this function lives in html_to_json.js, but it just unfocuses from the current element */
// (function(){

// })()

// /* global change */
// (function(){

// })()

