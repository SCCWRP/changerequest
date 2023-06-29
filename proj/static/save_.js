import { addTips } from "./tooltip.js";

// A handful of functions that handle html table 

// Converts the html table displayed in the 'edit_submission' page to JSON that is formatted for to work like a pandas dataframe
export const saveChanges = function() { 
   
   var table = document.querySelector("table");
   var headers = [];
   var dict = {};

   for (var i = 0; i < table.rows[0].cells.length; i++) {
      headers[i] = table.rows[0].cells[i].innerHTML.toLowerCase().replace(/ /gi, '');
   }

   for (var i = 0; i < headers.length; i++) {
      var data = [];
      var header = headers[i];
      for (let j = 1; j <= table.tBodies[0].rows.length; j++) {
         data.push(table.rows[j].cells[i].innerHTML.replace("<br>", "<div>", "</div>", ""));
      }

      dict[header] = data;
   }

   // show the loader gif
   // script root is a global, defined in script tags in the head of the HTML document
   document.querySelector(".records-display-inner-container").innerHTML = `<img src="/${$SCRIPT_ROOT}/static/loader.gif">`;

   // Send the edited records to the server
   fetch(`/${$SCRIPT_ROOT}/compare`, {
      method: "post",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(dict)
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

