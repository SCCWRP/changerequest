function formatDataTable (data) {
    data.accepted_changes.map(kv => {
        // kv signifying that each element of the array is a key value pair
        
        /* We added one in the changed indices variable, for purposes of highlighting the excel file.
        Here we make it go back to what it "should" be */
        console.log(`tr#objectid-${Number(kv["objectid"])} td.colname-${kv["colname"]}`);
        let cell = document.querySelector(`tr#objectid-${Number(kv["objectid"])} td.colname-${kv["colname"]}`);
        cell.classList.add("accepted-change");
        cell.classList.add("changed-cell");
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
        document.querySelector(`tr#objectid-${Number(kv["objectid"])} td.colname-${kv["colname"]}`).classList.add("changed-cell");
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

function tableNavigation(){
    // /* hit enter and go to next cell - this function lives in html_to_json.js, but it just unfocuses from the current element */
    // The table doesnt exist until the data gets returned to the browser from the server after comparing the data
    const cells = Array.from(document.querySelectorAll('table#changes-display-table td[contenteditable]'));

    const ncols = document.querySelectorAll('table#changes-display-table tr')[1].querySelectorAll('td[contenteditable]').length

    cells.forEach((cell, i) => {
        cell.addEventListener('keydown', (e) => {
            
            const focusedElement = document.activeElement;
            
            // move left if they press shift+tab, dont check for anything else after that
            if (e.shiftKey && e.key === 'Tab') {
                e.preventDefault();
                focusCell(cells, i - 1);
                return;
            }
            
            // to later be used for text selection
            let selection; 
            let range;
            
            switch (e.key) {
                case 'Enter':
                    e.preventDefault();
                    cell.blur();
                    focusCell(cells, i + ncols); // Assuming "Enter" is equivalent to "ArrowDown"
                    break;
                case 'ArrowDown':
                    e.preventDefault();
                    focusCell(cells, i + ncols); 
                    break;
                case 'ArrowUp':
                    e.preventDefault();
                    focusCell(cells, i - ncols);
                    break;
                case 'Tab':
                    e.preventDefault();
                    focusCell(cells, i + 1);
                    break;
                case 'ArrowRight':
                    // Get current selection
                    selection = window.getSelection();
                    
                    if (selection.rangeCount > 0) {
                        range = selection.getRangeAt(0);
                        
                        // Check if the whole content of the cell is selected
                        if (range.toString().length === focusedElement.textContent.length) {
                            e.preventDefault();  // Prevent default behavior
                            focusCell(cells, i + 1);
                        }
                    }
                    break;
                case 'ArrowLeft':
                    // Get current selection
                    selection = window.getSelection();
                    
                    if (selection.rangeCount > 0) {
                        range = selection.getRangeAt(0);
                        
                        // Check if the whole content of the cell is selected
                        if (range.toString().length === focusedElement.textContent.length) {
                            e.preventDefault();  // Prevent default behavior
                            focusCell(cells, i - 1);
                        }
                    }
                    break;

                case 'F2':
                    e.preventDefault();
                    
                    // Get the current selection.
                    selection = window.getSelection();
                    let caretPos = 0;

                    if (selection.rangeCount > 0) {
                        // Get the first range of the selection.
                        const range = selection.getRangeAt(0);
                        
                        // Create a new range that goes from the start of the cell to the end of the selection.
                        const preCaretRange = range.cloneRange();
                        preCaretRange.selectNodeContents(document.activeElement);
                        preCaretRange.setEnd(range.endContainer, range.endOffset);
                        
                        // The length of the pre-caret range is the desired caret position.
                        caretPos = preCaretRange.toString().length;
                    }

                    // Remove the selection.
                    selection.removeAllRanges();

                    // Set the caret position.
                    const newRange = document.createRange();
                    const textNode = document.activeElement.firstChild;  // assumes there is a single text node
                    if(textNode){
                        newRange.setStart(textNode, caretPos);
                        newRange.setEnd(textNode, caretPos);
                        selection.addRange(newRange);
                    }
                    break;
            }
        });
        
        // Select/Highlight cell's content to be typed over
        cell.addEventListener('focus', function(event) {
            let range = document.createRange(); // create a new range
            range.selectNodeContents(this); // set range to cell contents
            let sel = window.getSelection(); // get the current selection
            sel.removeAllRanges(); // remove all ranges from the selection
            sel.addRange(range); // add the range to the selection
        });
    });

    function focusCell(cells, i) {
        if (i >= 0 && i < cells.length) {
            cells[i].focus();
        }
    }
}