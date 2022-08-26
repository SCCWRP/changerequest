import { addTips } from "./tooltip.js";
// Converts the html table displayed in the 'edit_submission' page to JSON that is formatted for to work like a pandas dataframe
export const saveChanges = function() {
    let table = document.querySelector('table#changes-display-table');
    let rows = table.querySelectorAll('tr');

    // show the loader gif
    // script root is a global, defined in script tags in the head of the HTML document
    document.querySelector(".records-display-inner-container").innerHTML = `<img src="/${$SCRIPT_ROOT}/static/loading.gif">`;

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
        addTips();
        return data;
    })
    .catch(err => {
        console.log(err);
    })

}