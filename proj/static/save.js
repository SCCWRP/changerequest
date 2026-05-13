import { addTips } from "./tooltip.js";
// Converts the html table displayed in the 'edit_submission' page to JSON that is formatted for to work like a pandas dataframe
export const saveChanges = function() {
    if (document.querySelector('.records-display-inner-container table tbody').children.length > 0){
        let table = document.querySelector('div.records-display-inner-container table');
        let rows = table.querySelectorAll('tr');

        // show loader gif
        const loadingModal = document.getElementById('loading-modal');
        loadingModal.style.display = 'block';

        let tableJSON = Array.from(rows).slice(1).map(row => {
            let record = new Object();
            Array.from(row.querySelectorAll('td')).forEach(
                cell => {
                    let colnameArray = Array.from(cell.classList).filter(cl => cl.includes('colname-'));

                    // The table created by the app on the backend should be following a certain class naming convention
                    console.assert(
                        colnameArray.length === 1, 
                        "table cell class naming convention not followed - there should be exactly one class that says colname-<colname> so the table can be converted to a json more efficiently"
                    );

                    let colname = colnameArray[0].replace('colname-','');
                    
                    record[colname] = cell.innerText;
                    return ;
                }
            )
            return record;
        })

        tableJSON = JSON.stringify(tableJSON);
        console.log("tableJSON")
        console.log(tableJSON);
        
        // Send the edited records to the server
        fetch(`/${$SCRIPT_ROOT}/compare`, {
            method: "post",
            headers: { "Content-Type": "application/json" },
            body: tableJSON
        })
        .then(resp => {
            //console.log(resp.json());
            return resp.json()
        })
        .then(data => {
            console.log(data);
            document.querySelector("#changed-records-display-inner-container").innerHTML = data.tbl;
            document.querySelector("#added-records-display-inner-container").innerHTML = data.addtbl;
            document.querySelector("#deleted-records-display-inner-container").innerHTML = data.deltbl;
            
            formatDataTable(data);
            tableNavigation();
            addTips();

            // show/hide post change option buttons
            Array.prototype.slice.call(document.querySelectorAll(".post-change-option")).map(
                (b) => {
                    if (data.errors.length == 0) {
                        // No errors? unhide all post change buttons
                        b.classList.remove("hidden");
                    } else {
                        // Errors? Make sure the buttons that should NOT show, dont show
                        // Only the button to save changes after editing should show so that they can fix their errors
                        b.classList.contains('clean-data-post-change-option') ? b.classList.add("hidden") : b.classList.remove("hidden");
                    }
                }
            )

            // hide loader gif
            loadingModal.style.display = 'none';
            return data;
        })
        .catch(err => {
            console.log(err);
        })
    } else {
        alert("No changes were made")
    }
}

export async function confirmFinalize(event) {

    window.onbeforeunload = undefined;

    // Ask for confirmation and store the result
    const confirmation = confirm('Are you sure you want to finalize this change request?');

    // If not confirmed, prevent further action
    if (!confirmation) {
        event.preventDefault(); // Prevent form submission
        return false;
    }

    // Prompt for a comment
    const comment = prompt('Please enter a comment about why you are requesting a change to the data:');

    // Check if a comment was entered
    if (!comment) {
        alert('You must enter a comment to proceed.');
        event.preventDefault(); // Prevent form submission
        return false;
    }

    // Send the comment to the server
    try {
        const response = await fetch('savecomment', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ comment: comment })
        });

        if (!response.ok) {
            event.preventDefault(); // Prevent form submission
            throw new Error(`Server error: ${response.statusText}`);
        }

        console.log('Comment saved successfully');
    } catch (error) {
        console.error('Failed to save comment:', error);
        alert('There was an error saving your comment. Please try again.');
        event.preventDefault(); // Prevent form submission
        return false;
    }

    // Return true to allow the form submission
    console.log("All checks passed, form will now submit."); // Debugging statement
    return true;
}

// Attach the function to the form programmatically
document.getElementById('final-submit-form').addEventListener('submit', async function(event) {
    event.preventDefault();
     
    const result = await confirmFinalize(event);
    if (!result) {
        console.log("Form submission prevented."); // Debugging statement
        return    
    } else {
        console.log("Form submission allowed."); // Debugging statement
        this.submit()
    }
});