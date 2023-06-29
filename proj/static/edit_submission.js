import { addTips } from "./tooltip.js";
import { saveChanges } from "./save.js";

(function(){
    
    const uploadForm = document.querySelector("#upload-form");
    
    
    /* The routine that gets executed when the file is submitted */
    uploadForm.addEventListener("submit", async function(event){
        event.preventDefault();
        event.stopPropagation();

        // show loader gif
        const loadingModal = document.getElementById('loading-modal');
        loadingModal.style.display = 'block';

        /* unhide the datatable containers */
        Array.prototype.slice.call(document.querySelectorAll(".datatable-container")).map(
            c => {
                c.classList.remove("hidden")
            }
        )
        document.getElementById('change-report-container').classList.remove('hidden');


        document.querySelector(".records-display-inner-container").innerHTML = `<img src="/${$SCRIPT_ROOT}/static/loader.gif">`;

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
        
        document.querySelector("#changed-records-display-inner-container").innerHTML = data.tbl;
        document.querySelector("#added-records-display-inner-container").innerHTML = data.addtbl;
        document.querySelector("#deleted-records-display-inner-container").innerHTML = data.deltbl;

        // call function that formats the table
        formatDataTable(data);

        // Add table navigation listeners since elements are being created when the "changed records" table gets created
        tableNavigation()

        // Scroll it into view
        document.getElementById('change-report-container').scrollIntoView({ behavior: 'smooth', block: 'start' });

        // show buttons
        Array.prototype.slice.call(document.querySelectorAll(".post-change-option")).map(
            b => b.classList.remove("hidden")
        )

        addTips();
        
        // hide loader gif
        loadingModal.style.display = 'none';
        
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


// (function(){

// })()


window.addEventListener("load", function(){

    // select the uploadForm that we are going to be submitting the user's file with
    const uploadForm = document.querySelector("#upload-form");

    // Drag and Drop listener
    // Prevent defaults on drag events
    ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
        document.addEventListener(eventName, preventDefaults, false);
    });

    function preventDefaults(e) {
        e.preventDefault();
        e.stopPropagation();
    }
    
    // Highlight drop area when item is dragged over it
    ['dragenter', 'dragover'].forEach(eventName => {
        document.addEventListener(eventName, highlight, false);
    });

    ['dragleave', 'drop'].forEach(eventName => {
        document.addEventListener(eventName, unhighlight, false);
    });

    function highlight(e) {
        document.body.style.backgroundColor = '#cccccc'; // Use your own highlight style
    }

    function unhighlight(e) {
        document.body.style.backgroundColor = ''; // Reset the highlight style
    }

    // Handle dropped files
    document.addEventListener('drop', handleDrop, false);

    function handleDrop(e) {
        let files = e.dataTransfer.files;

        // Get the file input and set its files property
        let fileInput = document.querySelector('input#file');
        fileInput.files = files;

        // Submit the form
        // uploadForm.submit();
        const event = new Event('submit', {cancelable: true});
        uploadForm.dispatchEvent(event);

    }
})



// /* Saving changes when they edit in the browser */
// (function(){
    
// })()



// /* global change */
// (function(){

// })()

