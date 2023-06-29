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
            document.querySelector(".records-display-inner-container").innerHTML = data.tbl;
            formatDataTable(data);
            tableNavigation();
            addTips();
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