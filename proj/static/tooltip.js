export const addTips = function () {
        const tooltip = document.querySelector('.tooltip#changed-cell-tooltip');
        const cells = document.querySelectorAll('.changed-cell');
        const changedRecordsTable = document.getElementById('changed-records-datatable-container')

        cells.forEach(function (cell) {
                cell.addEventListener('mouseenter', function (event) {
                        const rect = cell.getBoundingClientRect();
                        const title = cell.getAttribute('data-original-title');
                        const content = cell.getAttribute('data-content');

                        tooltip.querySelector('.title').textContent = title;
                        tooltip.querySelector('.content').innerHTML = content;

                        tooltip.style.left = `${rect.left + window.pageXOffset + 5}px`;
                        tooltip.style.top = `${rect.top + window.pageYOffset - (rect.height/1.4)}px`;
                        // tooltip.style.top = `${rect.top + window.pageYOffset}px`;


                        tooltip.style.display = 'block';
                });

                // changedRecordsTable.addEventListener('mouseleave', function (event) {
                //         tooltip.style.display = 'none';
                // });
                changedRecordsTable.addEventListener('mouseout', function(event) {
                        if (!event.target.classList.contains('changed-cell')) return;
                        let relatedTarget = event.relatedTarget;
                        while (relatedTarget) {
                            if (relatedTarget === tooltip) return;  // Ignore if the cursor moved to the tooltip
                            relatedTarget = relatedTarget.parentNode;
                        }
                        tooltip.style.display = 'none';
                    });
                    
        });
}