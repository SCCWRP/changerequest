import { addTips } from "./tooltip.js";
import { saveChanges } from "./save.js";

(function(){
    
    const uploadForm = document.querySelector("#upload-form");
    
    
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

        addTips();
        
        return data;
    })

    // the edit submission page should warn them they might have unsaved changes
    window.onbeforeunload = () => {return true}

    // now add the listener for the save changes button, now that they have made an initial change request with the excel file
    document.getElementById('save-change-btn').addEventListener('click', saveChanges)
    Array.from(document.getElementsByClassName('editable-cell')).forEach(c => {
        c.addEventListener()
    })

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

