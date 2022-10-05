function formatDataTable (data) {
    data.accepted_changes.map(kv => {
        // kv signifying that each element of the array is a key value pair
        
        /* We added one in the changed indices variable, for purposes of highlighting the excel file.
        Here we make it go back to what it "should" be */
        console.log(`tr#objectid-${Number(kv["objectid"])} td.colname-${kv["colname"]}`);
        let cell = document.querySelector(`tr#objectid-${Number(kv["objectid"])} td.colname-${kv["colname"]}`);
        cell.classList.add("accepted-change");
        cell.setAttribute("data-toggle","popover");
        cell.setAttribute("data-content","This change was accepted and can be processed.");
        cell.setAttribute("title","");
        cell.setAttribute("data-original-title","All set!");
        cell.setAttribute("data-placement","top");
    })
    data.rejected_changes.map(kv => {
        // kv signifying that each element of the array is a key value pair

        
        /* We added one in the changed indices variable, for purposes of highlighting the excel file.
        Here we make it go back to what it "should" be */
        console.log(`tr#objectid-${Number(kv["objectid"])} td.colname-${kv["colname"]}`);
        document.querySelector(`tr#objectid-${Number(kv["objectid"])} td.colname-${kv["colname"]}`).classList.add("rejected-change");
    })
    data.errors.map(error => {
        /* each element of the array is an object 
            column, core_error, dtype, error_message, rows            
        */

        // Here is where we add the data-toggle and title attributes for the tooltip
        error.rows.map(row => {    
            console.log(`tr#objectid-${Number(row.objectid)} td.colname-${error.columns}`);
            let cell = document.querySelector(`tr#objectid-${Number(row.objectid)} td.colname-${error.columns}`);
            cell.setAttribute("data-toggle","popover");
            cell.setAttribute("data-content",`${error.error_message}`);
            cell.setAttribute("title","");
            cell.setAttribute("data-original-title",`${error.error_type}`);
            cell.setAttribute("data-placement","top");
        })
    })
}