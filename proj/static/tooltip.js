export const addTips = function() {    
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
}